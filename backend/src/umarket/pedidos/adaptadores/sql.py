import secrets
from collections import defaultdict
from datetime import date, datetime
from typing import Any
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import func, insert, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from umarket.bd.uow import UnidadSql
from umarket.catalogo.adaptadores.sql import ReservaStockSql
from umarket.pedidos.adaptadores.tablas import pedido_items, pedidos, transiciones_pedido
from umarket.pedidos.aplicacion.vistas import ItemVista, VistaPedido
from umarket.pedidos.dominio.estados import ABIERTOS, Estado
from umarket.pedidos.dominio.pedido import ALFABETO_CODIGO, ItemPedido, Origen, Pedido
from umarket.pedidos.dominio.reglas import ContextoPedido, Limites, OfertaEnTurno
from umarket.pedidos.puertos import PedidoDuplicado


class GeneradorCodigosAleatorio:
    def codigo(self) -> str:
        return "".join(secrets.choice(ALFABETO_CODIGO) for _ in range(3))


class RepositorioPedidosSql:
    def __init__(self, sesion: Session) -> None:
        self._s = sesion

    def _cargar(self, filas: list[Any]) -> list[Pedido]:
        if not filas:
            return []
        items: dict[UUID, list[ItemPedido]] = defaultdict(list)
        for i in self._s.execute(
            select(pedido_items).where(pedido_items.c.pedido_id.in_([f["id"] for f in filas]))
        ).mappings():
            items[i["pedido_id"]].append(
                ItemPedido(i["producto_id"], i["nombre"], i["precio_unitario_cop"], i["cantidad"])
            )
        return [
            Pedido(
                id=f["id"],
                codigo=f["codigo"],
                campus_id=f["campus_id"],
                tienda_id=f["tienda_id"],
                vendedor_id=f["vendedor_id"],
                comprador_id=f["comprador_id"],
                turno_id=f["turno_id"],
                fecha=f["fecha"],
                franja_id=f["franja_id"],
                punto_id=f["punto_id"],
                items=tuple(items[f["id"]]),
                estado=Estado(f["estado"]),
                creado_en=f["creado_en"],
                vence_en=f["vence_en"],
                actualizado_en=f["actualizado_en"],
                origen=Origen(f["origen"]),
                busqueda_id=f["busqueda_id"],
                llegada_en=f["llegada_en"],
                motivo=f["motivo"],
            )
            for f in filas
        ]

    def por_id(self, pedido_id: UUID, bloquear: bool = False) -> Pedido | None:
        consulta = select(pedidos).where(pedidos.c.id == pedido_id)
        if bloquear:
            consulta = consulta.with_for_update()
        encontrados = self._cargar(list(self._s.execute(consulta).mappings()))
        return encontrados[0] if encontrados else None

    def por_clave(self, comprador_id: UUID, clave: str) -> Pedido | None:
        filas = self._s.execute(
            select(pedidos).where(
                pedidos.c.comprador_id == comprador_id, pedidos.c.clave_idempotencia == clave
            )
        ).mappings()
        encontrados = self._cargar(list(filas))
        return encontrados[0] if encontrados else None

    def codigo_usado(self, tienda_id: UUID, fecha: date, codigo: str) -> bool:
        return (
            self._s.execute(
                select(pedidos.c.id).where(
                    pedidos.c.tienda_id == tienda_id,
                    pedidos.c.fecha == fecha,
                    pedidos.c.codigo == codigo,
                )
            ).first()
            is not None
        )

    def agregar(self, pedido: Pedido, clave_idempotencia: str) -> None:
        try:
            with self._s.begin_nested():
                self._s.execute(
                    insert(pedidos).values(
                        id=pedido.id,
                        codigo=pedido.codigo,
                        campus_id=pedido.campus_id,
                        tienda_id=pedido.tienda_id,
                        vendedor_id=pedido.vendedor_id,
                        comprador_id=pedido.comprador_id,
                        turno_id=pedido.turno_id,
                        fecha=pedido.fecha,
                        franja_id=pedido.franja_id,
                        punto_id=pedido.punto_id,
                        estado=pedido.estado.value,
                        total_cop=pedido.total_cop,
                        origen=pedido.origen.value,
                        busqueda_id=pedido.busqueda_id,
                        clave_idempotencia=clave_idempotencia,
                        creado_en=pedido.creado_en,
                        vence_en=pedido.vence_en,
                        actualizado_en=pedido.actualizado_en,
                    )
                )
        except IntegrityError as exc:
            if "clave_idempotencia" in str(exc.orig):
                raise PedidoDuplicado() from exc
            raise
        self._s.execute(
            insert(pedido_items),
            [
                {
                    "pedido_id": pedido.id,
                    "producto_id": i.producto_id,
                    "nombre": i.nombre,
                    "precio_unitario_cop": i.precio_unitario_cop,
                    "cantidad": i.cantidad,
                }
                for i in pedido.items
            ],
        )

    def guardar_estado(self, pedido: Pedido) -> None:
        self._s.execute(
            update(pedidos)
            .where(pedidos.c.id == pedido.id)
            .values(
                estado=pedido.estado.value,
                actualizado_en=pedido.actualizado_en,
                llegada_en=pedido.llegada_en,
                motivo=pedido.motivo,
            )
        )

    def registrar_transicion(
        self,
        pedido_id: UUID,
        desde: Estado | None,
        hacia: Estado,
        accion: str,
        actor: str,
        motivo: str | None,
        en: datetime,
    ) -> None:
        self._s.execute(
            insert(transiciones_pedido).values(
                id=uuid4(),
                pedido_id=pedido_id,
                desde=desde.value if desde else None,
                hacia=hacia.value,
                accion=accion,
                actor=actor,
                motivo=motivo,
                en=en,
            )
        )

    def pendientes_vencidos(self, ahora: datetime, limite: int) -> list[Pedido]:
        filas = self._s.execute(
            select(pedidos)
            .where(pedidos.c.estado == Estado.PENDIENTE.value, pedidos.c.vence_en <= ahora)
            .order_by(pedidos.c.vence_en)
            .limit(limite)
            .with_for_update(skip_locked=True)
        ).mappings()
        return self._cargar(list(filas))


class LectorContextoPedidoSql:
    """Lectura cruzada en la misma transaccion: turno, franja, tienda, ofertas y comprador."""

    def __init__(self, sesion: Session) -> None:
        self._s = sesion

    def contexto(
        self, turno_id: UUID, comprador_id: UUID, ahora: datetime, limites: Limites
    ) -> ContextoPedido | None:
        t = (
            self._s.execute(
                text(
                    """
                    select tu.id, tu.fecha, tu.franja_id, tu.punto_id, ti.id as tienda_id,
                           ti.vendedor_id, ti.campus_id, c.zona_horaria,
                           timezone(c.zona_horaria, tu.fecha + f.hora_fin) as franja_fin
                    from turnos tu
                      join tiendas ti on ti.id = tu.tienda_id and ti.activa
                      join franjas f on f.id = tu.franja_id
                      join campus c on c.id = ti.campus_id
                    where tu.id = :turno
                    """
                ),
                {"turno": turno_id},
            )
            .mappings()
            .first()
        )
        if t is None:
            return None
        ofertas = {
            o["producto_id"]: OfertaEnTurno(
                o["producto_id"], o["nombre"], o["precio_cop"], o["activo"], o["disponible"]
            )
            for o in self._s.execute(
                text(
                    """
                    select s.producto_id, p.nombre, p.precio_cop, p.activo,
                           s.total - s.reservado as disponible
                    from stock_turno s join productos p on p.id = s.producto_id
                    where s.turno_id = :turno
                    """
                ),
                {"turno": turno_id},
            ).mappings()
        }
        abiertos = self._s.execute(
            select(func.count())
            .select_from(pedidos)
            .where(
                pedidos.c.comprador_id == comprador_id,
                pedidos.c.estado.in_([e.value for e in ABIERTOS]),
                # Un pendiente vencido ya no cuenta como abierto (estado efectivo).
                ~((pedidos.c.estado == Estado.PENDIENTE.value) & (pedidos.c.vence_en <= ahora)),
            )
        ).scalar_one()
        inasistencias = self._s.execute(
            select(func.count())
            .select_from(pedidos)
            .where(
                pedidos.c.comprador_id == comprador_id,
                pedidos.c.estado == Estado.NO_ASISTIO.value,
            )
        ).scalar_one()
        return ContextoPedido(
            tienda_id=t["tienda_id"],
            vendedor_id=t["vendedor_id"],
            campus_id=t["campus_id"],
            fecha=t["fecha"],
            franja_id=t["franja_id"],
            franja_fin=t["franja_fin"],
            punto_id=t["punto_id"],
            ofertas=ofertas,
            pedidos_abiertos_del_comprador=abiertos,
            inasistencias_del_comprador=inasistencias,
            ahora=ahora,
            zona=ZoneInfo(t["zona_horaria"]),
            limites=limites,
        )


class UnidadPedidosSql(UnidadSql):
    def _al_abrir(self, sesion: Session) -> None:
        self.pedidos = RepositorioPedidosSql(sesion)
        self.contexto = LectorContextoPedidoSql(sesion)
        self.stock = ReservaStockSql(sesion)


# ---------------------------------------------------------------------------
# Lado de lectura
# ---------------------------------------------------------------------------

_SQL_VISTA = """
select pe.id, pe.codigo, pe.estado, pe.tienda_id, ti.nombre as tienda_nombre,
       ti.slug as tienda_slug, pe.vendedor_id, pe.comprador_id, u.nombre as comprador_nombre,
       pe.fecha, pe.franja_id, f.hora_inicio, f.hora_fin, pe.punto_id,
       pt.nombre as punto_nombre, pe.total_cop, pe.creado_en, pe.vence_en, pe.llegada_en,
       pe.motivo,
       exists(select 1 from calificaciones ca where ca.pedido_id = pe.id) as calificado
from pedidos pe
  join tiendas ti on ti.id = pe.tienda_id
  join usuarios u on u.id = pe.comprador_id
  join franjas f on f.id = pe.franja_id
  join puntos_encuentro pt on pt.id = pe.punto_id
"""


class ConsultasPedidosSql:
    def __init__(self, fabrica: sessionmaker[Session]) -> None:
        self._fabrica = fabrica

    def _vistas(self, s: Session, filtro: str, params: dict[str, object]) -> list[VistaPedido]:
        filas = list(s.execute(text(_SQL_VISTA + filtro), params).mappings())
        if not filas:
            return []
        items: dict[UUID, list[ItemVista]] = defaultdict(list)
        for i in s.execute(
            select(pedido_items).where(pedido_items.c.pedido_id.in_([f["id"] for f in filas]))
        ).mappings():
            items[i["pedido_id"]].append(
                ItemVista(i["producto_id"], i["nombre"], i["precio_unitario_cop"], i["cantidad"])
            )
        return [
            VistaPedido(
                id=f["id"],
                codigo=f["codigo"],
                estado=Estado(f["estado"]),
                tienda_id=f["tienda_id"],
                tienda_nombre=f["tienda_nombre"],
                tienda_slug=f["tienda_slug"],
                vendedor_id=f["vendedor_id"],
                comprador_id=f["comprador_id"],
                comprador_nombre=f["comprador_nombre"],
                fecha=f["fecha"],
                franja_id=f["franja_id"],
                franja_etiqueta=f"{f['hora_inicio']:%H:%M}–{f['hora_fin']:%H:%M}",
                punto_id=f["punto_id"],
                punto_nombre=f["punto_nombre"],
                items=tuple(items[f["id"]]),
                total_cop=f["total_cop"],
                creado_en=f["creado_en"],
                vence_en=f["vence_en"],
                llegada_en=f["llegada_en"],
                motivo=f["motivo"],
                calificado=f["calificado"],
            )
            for f in filas
        ]

    def vista(self, pedido_id: UUID) -> VistaPedido | None:
        with self._fabrica() as s:
            encontradas = self._vistas(s, "where pe.id = :id", {"id": pedido_id})
        return encontradas[0] if encontradas else None

    def del_comprador(self, comprador_id: UUID) -> list[VistaPedido]:
        with self._fabrica() as s:
            return self._vistas(
                s,
                "where pe.comprador_id = :c order by pe.creado_en desc limit 50",
                {"c": comprador_id},
            )

    def de_vendedor(self, vendedor_id: UUID, desde: date) -> list[VistaPedido]:
        with self._fabrica() as s:
            return self._vistas(
                s,
                "where pe.vendedor_id = :v and pe.fecha >= :desde order by pe.fecha, f.hora_inicio",
                {"v": vendedor_id, "desde": desde},
            )
