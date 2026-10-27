"""Casos de uso de pedidos: crear, actuar (aprobar, llegue, entregar...), vencer y consultar."""

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from umarket.compartido.dominio.errores import (
    Conflicto,
    NoAutorizado,
    NoEncontrado,
    ReglaIncumplida,
)
from umarket.compartido.dominio.eventos import Evento, Json
from umarket.compartido.dominio.reglas import ConjuntoReglas, Validador
from umarket.compartido.dominio.reloj import Reloj
from umarket.pedidos.aplicacion.vistas import VistaPedido
from umarket.pedidos.dominio.estados import Accion, Actor, Estado, Transicion
from umarket.pedidos.dominio.pedido import ItemPedido, Origen, Pedido
from umarket.pedidos.dominio.reglas import (
    ContextoPedido,
    Limites,
    LineaSolicitada,
    SolicitudPedido,
)
from umarket.pedidos.puertos import (
    ConsultasPedidos,
    GeneradorCodigos,
    PedidoDuplicado,
    UnidadPedidos,
)

type FabricaUnidad = Callable[[], UnidadPedidos]


@dataclass(frozen=True)
class PoliticaPedidos:
    minutos_para_aprobar: int = 30
    minutos_espera_no_asistio: int = 10
    limites: Limites = field(default_factory=Limites)


def datos_evento(pedido: Pedido) -> dict[str, Json]:
    return {
        "pedido_id": str(pedido.id),
        "codigo": pedido.codigo,
        "estado": pedido.estado.value,
        "tienda_id": str(pedido.tienda_id),
        "vendedor_id": str(pedido.vendedor_id),
        "comprador_id": str(pedido.comprador_id),
        "total_cop": pedido.total_cop,
        "fecha": pedido.fecha.isoformat(),
        "franja_id": pedido.franja_id,
        "punto_id": pedido.punto_id,
        "motivo": pedido.motivo,
    }


def _persistir_transicion(
    u: UnidadPedidos,
    antes: Pedido,
    despues: Pedido,
    transicion: Transicion,
    accion: Accion,
    actor: Actor,
    ahora: datetime,
) -> None:
    u.pedidos.guardar_estado(despues)
    if transicion.libera_stock:
        for item in despues.items:
            u.stock.liberar(despues.turno_id, item.producto_id, item.cantidad)
    u.pedidos.registrar_transicion(
        despues.id, antes.estado, despues.estado, accion.value, actor.value, despues.motivo, ahora
    )
    datos = {**datos_evento(despues), "actor": actor.value}
    u.eventos.publicar(Evento(transicion.evento, datos, ahora))


@dataclass(frozen=True)
class ComandoCrearPedido:
    comprador_id: UUID
    turno_id: UUID
    lineas: tuple[LineaSolicitada, ...]
    clave_idempotencia: str
    origen: Origen = Origen.TIENDA
    busqueda_id: UUID | None = None


class CrearPedido:
    def __init__(
        self,
        unidad: FabricaUnidad,
        reglas: ConjuntoReglas[SolicitudPedido, ContextoPedido],
        codigos: GeneradorCodigos,
        reloj: Reloj,
        politica: PoliticaPedidos,
    ) -> None:
        self._unidad = unidad
        self._validador = Validador(reglas)
        self._codigos = codigos
        self._reloj = reloj
        self._politica = politica

    def ejecutar(self, cmd: ComandoCrearPedido) -> Pedido:
        if not cmd.clave_idempotencia.strip():
            raise ReglaIncumplida("falta_idempotencia", "Falta la clave de idempotencia.")
        try:
            return self._crear(cmd)
        except PedidoDuplicado:
            with self._unidad() as u:
                existente = u.pedidos.por_clave(cmd.comprador_id, cmd.clave_idempotencia)
            if existente is None:
                raise
            return existente

    def _crear(self, cmd: ComandoCrearPedido) -> Pedido:
        ahora = self._reloj.ahora()
        lineas = _fusionar(cmd.lineas)
        with self._unidad() as u:
            existente = u.pedidos.por_clave(cmd.comprador_id, cmd.clave_idempotencia)
            if existente is not None:
                return existente
            ctx = u.contexto.contexto(cmd.turno_id, cmd.comprador_id, ahora, self._politica.limites)
            if ctx is None:
                raise NoEncontrado("turno_no_encontrado", "Ese turno no existe.")
            solicitud = SolicitudPedido(cmd.comprador_id, cmd.turno_id, lineas)
            hallazgos = self._validador.validar(solicitud, ctx)
            if hallazgos:
                primero = hallazgos[0]
                raise ReglaIncumplida(
                    primero.regla_id,
                    primero.mensaje,
                    hallazgos=[h.regla_id for h in hallazgos],
                    reglas_version=self._validador.version,
                )
            items = tuple(
                ItemPedido(
                    producto_id=linea.producto_id,
                    nombre=ctx.ofertas[linea.producto_id].nombre,
                    precio_unitario_cop=ctx.ofertas[linea.producto_id].precio_cop,
                    cantidad=linea.cantidad,
                )
                for linea in lineas
            )
            for item in items:
                if not u.stock.reservar(cmd.turno_id, item.producto_id, item.cantidad):
                    disponible = u.stock.disponible(cmd.turno_id, item.producto_id)
                    raise Conflicto(
                        "sin_stock",
                        f"Solo quedan {disponible} de {item.nombre}.",
                        producto_id=str(item.producto_id),
                        disponible=disponible,
                    )
            pedido = Pedido(
                id=uuid4(),
                codigo=self._codigo_unico(u, ctx),
                campus_id=ctx.campus_id,
                tienda_id=ctx.tienda_id,
                vendedor_id=ctx.vendedor_id,
                comprador_id=cmd.comprador_id,
                turno_id=cmd.turno_id,
                fecha=ctx.fecha,
                franja_id=ctx.franja_id,
                punto_id=ctx.punto_id,
                items=items,
                estado=Estado.PENDIENTE,
                creado_en=ahora,
                vence_en=ahora + timedelta(minutes=self._politica.minutos_para_aprobar),
                actualizado_en=ahora,
                origen=cmd.origen,
                busqueda_id=cmd.busqueda_id,
            )
            u.pedidos.agregar(pedido, cmd.clave_idempotencia)
            u.pedidos.registrar_transicion(
                pedido.id, None, Estado.PENDIENTE, "crear", Actor.COMPRADOR.value, None, ahora
            )
            u.eventos.publicar(Evento("pedido.creado", datos_evento(pedido), ahora))
            u.confirmar()
            return pedido

    def _codigo_unico(self, u: UnidadPedidos, ctx: ContextoPedido) -> str:
        for _ in range(20):
            codigo = self._codigos.codigo()
            if not u.pedidos.codigo_usado(ctx.tienda_id, ctx.fecha, codigo):
                return codigo
        raise Conflicto("sin_codigos", "No se pudo generar un codigo de pedido. Intenta otra vez.")


def _fusionar(lineas: tuple[LineaSolicitada, ...]) -> tuple[LineaSolicitada, ...]:
    """Dos lineas del mismo producto son una sola con la suma: el carrito no duplica."""
    total: dict[UUID, int] = {}
    for linea in lineas:
        total[linea.producto_id] = total.get(linea.producto_id, 0) + linea.cantidad
    if not total:
        raise ReglaIncumplida("pedido_vacio", "Agrega al menos un producto.")
    return tuple(LineaSolicitada(p, c) for p, c in total.items())


class ActuarSobrePedido:
    """Aprobar, rechazar, cancelar, llegue, entregar, no asistio: una sola puerta.

    Que se puede hacer y quien lo decide la tabla `TRANSICIONES`; una accion
    nueva es una fila nueva, no un caso de uso nuevo.
    """

    def __init__(self, unidad: FabricaUnidad, reloj: Reloj, politica: PoliticaPedidos) -> None:
        self._unidad = unidad
        self._reloj = reloj
        self._politica = politica

    def ejecutar(
        self, pedido_id: UUID, usuario_id: UUID, accion: Accion, motivo: str | None = None
    ) -> Pedido:
        if accion is Accion.VENCER:
            raise NoAutorizado("accion_no_permitida", "Solo el sistema vence pedidos.")
        ahora = self._reloj.ahora()
        with self._unidad() as u:
            pedido = u.pedidos.por_id(pedido_id, bloquear=True)
            if pedido is None:
                raise NoEncontrado("pedido_no_encontrado", "Ese pedido no existe.")
            actor = pedido.actor_de(usuario_id)
            despues, transicion = pedido.aplicar(
                accion,
                actor,
                ahora,
                (motivo or "").strip()[:200] or None,
                timedelta(minutes=self._politica.minutos_espera_no_asistio),
            )
            _persistir_transicion(u, pedido, despues, transicion, accion, actor, ahora)
            u.confirmar()
            return despues


class VencerPedidos:
    """Lo corre el worker cada minuto. La correccion no depende de el: ver `estado_efectivo`."""

    def __init__(self, unidad: FabricaUnidad, reloj: Reloj) -> None:
        self._unidad = unidad
        self._reloj = reloj

    def ejecutar(self, limite: int = 100) -> int:
        ahora = self._reloj.ahora()
        with self._unidad() as u:
            vencidos = u.pedidos.pendientes_vencidos(ahora, limite)
            for pedido in vencidos:
                despues, transicion = pedido.aplicar(Accion.VENCER, Actor.SISTEMA, ahora)
                _persistir_transicion(
                    u, pedido, despues, transicion, Accion.VENCER, Actor.SISTEMA, ahora
                )
            u.confirmar()
            return len(vencidos)


class ConsultarPedidos:
    def __init__(self, consultas: ConsultasPedidos, reloj: Reloj, zona_horaria: str) -> None:
        self._consultas = consultas
        self._reloj = reloj
        self._zona = ZoneInfo(zona_horaria)

    def uno(self, pedido_id: UUID, usuario_id: UUID) -> VistaPedido:
        vista = self._consultas.vista(pedido_id)
        if vista is None:
            raise NoEncontrado("pedido_no_encontrado", "Ese pedido no existe.")
        if usuario_id == vista.vendedor_id:
            actor = Actor.VENDEDOR
        elif usuario_id == vista.comprador_id:
            actor = Actor.COMPRADOR
        else:
            raise NoEncontrado("pedido_no_encontrado", "Ese pedido no existe.")
        return vista.para(actor, self._reloj.ahora())

    def del_comprador(self, comprador_id: UUID) -> list[VistaPedido]:
        ahora = self._reloj.ahora()
        return [v.para(Actor.COMPRADOR, ahora) for v in self._consultas.del_comprador(comprador_id)]

    def bandeja(self, vendedor_id: UUID) -> list[VistaPedido]:
        """Desde ayer en adelante: lo abierto primero, por franja."""
        ahora = self._reloj.ahora()
        desde: date = ahora.astimezone(self._zona).date() - timedelta(days=1)
        vistas = [
            v.para(Actor.VENDEDOR, ahora) for v in self._consultas.de_vendedor(vendedor_id, desde)
        ]
        return sorted(
            vistas, key=lambda v: (not v.acciones, v.fecha, v.franja_etiqueta, v.creado_en)
        )
