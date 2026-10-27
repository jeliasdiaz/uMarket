"""Casos de uso del vendedor: su tienda, sus productos y sus turnos."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, timedelta
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from umarket.catalogo.aplicacion.vistas import (
    OfertaTurno,
    ProductoVista,
    TurnoVista,
)
from umarket.catalogo.dominio.modelos import Producto, StockTurno, Tienda, Turno, slug_de
from umarket.catalogo.dominio.vocabulario import Categoria, Etiqueta
from umarket.catalogo.puertos import UnidadCatalogo
from umarket.compartido.dominio.errores import (
    Conflicto,
    NoAutorizado,
    NoEncontrado,
    ReglaIncumplida,
)
from umarket.compartido.dominio.reloj import Reloj

DIAS_HACIA_ADELANTE = 14

type FabricaUnidad = Callable[[], UnidadCatalogo]


def _tienda_de(u: UnidadCatalogo, vendedor_id: UUID) -> Tienda:
    tienda = u.tiendas.por_vendedor(vendedor_id)
    if tienda is None:
        raise NoEncontrado("sin_tienda", "Todavia no tienes una tienda. Crea una para vender.")
    return tienda


def hoy_en(reloj: Reloj, zona_horaria: str) -> date:
    return reloj.ahora().astimezone(ZoneInfo(zona_horaria)).date()


class CrearTienda:
    def __init__(self, unidad: FabricaUnidad, reloj: Reloj) -> None:
        self._unidad = unidad
        self._reloj = reloj

    def ejecutar(self, vendedor_id: UUID, campus_id: str, nombre: str, descripcion: str) -> Tienda:
        with self._unidad() as u:
            if u.tiendas.por_vendedor(vendedor_id) is not None:
                raise Conflicto("ya_tienes_tienda", "Ya tienes una tienda.")
            base = slug_de(nombre)
            ocupados = u.tiendas.slugs_que_empiezan(base)
            slug, n = base, 2
            while slug in ocupados:
                slug, n = f"{base}-{n}", n + 1
            tienda = Tienda.nueva(
                uuid4(), campus_id, vendedor_id, nombre, slug, descripcion, self._reloj.ahora()
            )
            u.tiendas.agregar(tienda)
            u.confirmar()
            return tienda


@dataclass(frozen=True)
class DatosProducto:
    nombre: str
    descripcion: str
    categoria: Categoria
    etiquetas: tuple[Etiqueta, ...]
    precio_cop: int
    activo: bool = True


class GuardarProducto:
    """Crea un producto, o edita uno de la propia tienda si llega `producto_id`."""

    def __init__(self, unidad: FabricaUnidad) -> None:
        self._unidad = unidad

    def ejecutar(
        self, vendedor_id: UUID, datos: DatosProducto, producto_id: UUID | None = None
    ) -> Producto:
        with self._unidad() as u:
            tienda = _tienda_de(u, vendedor_id)
            if producto_id is not None:
                existente = u.productos.por_id(producto_id)
                if existente is None or existente.tienda_id != tienda.id:
                    raise NoEncontrado("producto_no_encontrado", "Ese producto no es de tu tienda.")
            producto = Producto(
                id=producto_id or uuid4(),
                tienda_id=tienda.id,
                nombre=datos.nombre,
                descripcion=datos.descripcion,
                categoria=datos.categoria,
                etiquetas=datos.etiquetas,
                precio_cop=datos.precio_cop,
                activo=datos.activo,
            )
            u.productos.guardar(producto)
            u.confirmar()
            return producto


class PublicarTurno:
    def __init__(self, unidad: FabricaUnidad, reloj: Reloj) -> None:
        self._unidad = unidad
        self._reloj = reloj

    def ejecutar(
        self,
        vendedor_id: UUID,
        fecha: date,
        franja_id: str,
        punto_id: str,
        stock: dict[UUID, int],
    ) -> Turno:
        with self._unidad() as u:
            tienda = _tienda_de(u, vendedor_id)
            _validar_lugar_y_hora(u, tienda, fecha, franja_id, punto_id, self._reloj)
            if u.turnos.existe(tienda.id, fecha, franja_id):
                raise Conflicto(
                    "turno_repetido", "Ya publicaste un turno para esa franja de ese dia."
                )
            _validar_productos(u, tienda, stock)
            turno = Turno(uuid4(), tienda.id, fecha, franja_id, punto_id).con_stock(stock)
            u.turnos.agregar(turno)
            u.confirmar()
            return turno


class EditarStock:
    def __init__(self, unidad: FabricaUnidad) -> None:
        self._unidad = unidad

    def ejecutar(self, vendedor_id: UUID, turno_id: UUID, stock: dict[UUID, int]) -> Turno:
        with self._unidad() as u:
            tienda = _tienda_de(u, vendedor_id)
            turno = u.turnos.por_id(turno_id)
            if turno is None or turno.tienda_id != tienda.id:
                raise NoEncontrado("turno_no_encontrado", "Ese turno no es de tu tienda.")
            _validar_productos(u, tienda, stock)
            actualizado = turno.con_stock(stock)
            u.turnos.guardar_stock(actualizado)
            u.confirmar()
            return actualizado


class DuplicarTurnos:
    """Copia los turnos de un dia a otro, con el mismo stock y sin reservas.

    Publicar turnos tiene que tomar menos de un minuto (riesgo de PLAN-Y-DECISIONES
    §9): "lo mismo que ayer" es un toque.
    """

    def __init__(self, unidad: FabricaUnidad, reloj: Reloj) -> None:
        self._unidad = unidad
        self._reloj = reloj

    def ejecutar(self, vendedor_id: UUID, desde: date, hacia: date) -> list[Turno]:
        with self._unidad() as u:
            tienda = _tienda_de(u, vendedor_id)
            creados: list[Turno] = []
            for origen in u.turnos.de_tienda(tienda.id, desde, desde):
                if u.turnos.existe(tienda.id, hacia, origen.franja_id):
                    continue
                _validar_lugar_y_hora(
                    u, tienda, hacia, origen.franja_id, origen.punto_id, self._reloj
                )
                nuevo = Turno(
                    uuid4(),
                    tienda.id,
                    hacia,
                    origen.franja_id,
                    origen.punto_id,
                    tuple(StockTurno(s.producto_id, s.total) for s in origen.stock),
                )
                u.turnos.agregar(nuevo)
                creados.append(nuevo)
            u.confirmar()
            return creados


@dataclass(frozen=True)
class VistaMiTienda:
    tienda: Tienda
    productos: tuple[ProductoVista, ...]
    turnos: tuple[TurnoVista, ...]
    hoy: date


class VerMiTienda:
    def __init__(self, unidad: FabricaUnidad, reloj: Reloj) -> None:
        self._unidad = unidad
        self._reloj = reloj

    def ejecutar(self, vendedor_id: UUID) -> VistaMiTienda:
        with self._unidad() as u:
            tienda = _tienda_de(u, vendedor_id)
            zona = u.campus.zona_horaria(tienda.campus_id)
            hoy = hoy_en(self._reloj, zona)
            productos = u.productos.de_tienda(tienda.id)
            turnos: list[TurnoVista] = []
            for t in u.turnos.de_tienda(tienda.id, hoy, hoy + timedelta(days=7)):
                franja = u.campus.franja(tienda.campus_id, t.franja_id)
                punto = u.campus.punto(tienda.campus_id, t.punto_id)
                abierto = franja is not None and not franja.ha_pasado(
                    t.fecha, self._reloj.ahora(), ZoneInfo(zona)
                )
                turnos.append(
                    TurnoVista(
                        id=t.id,
                        fecha=t.fecha,
                        franja_id=t.franja_id,
                        franja_etiqueta=franja.etiqueta if franja else t.franja_id,
                        punto_id=t.punto_id,
                        punto_nombre=punto.nombre if punto else t.punto_id,
                        abierto=abierto,
                        ofertas=tuple(
                            OfertaTurno(s.producto_id, s.total, s.disponible) for s in t.stock
                        ),
                    )
                )
            return VistaMiTienda(
                tienda=tienda,
                productos=tuple(
                    ProductoVista(
                        p.id,
                        p.nombre,
                        p.descripcion,
                        p.categoria.value,
                        tuple(e.value for e in p.etiquetas),
                        p.precio_cop,
                        p.activo,
                    )
                    for p in productos
                ),
                turnos=tuple(turnos),
                hoy=hoy,
            )


def _validar_lugar_y_hora(
    u: UnidadCatalogo, tienda: Tienda, fecha: date, franja_id: str, punto_id: str, reloj: Reloj
) -> None:
    franja = u.campus.franja(tienda.campus_id, franja_id)
    if franja is None:
        raise ReglaIncumplida("franja_desconocida", "Esa franja no existe en tu campus.")
    punto = u.campus.punto(tienda.campus_id, punto_id)
    if punto is None or not punto.activo:
        raise ReglaIncumplida("punto_desconocido", "Ese punto de encuentro no existe.")
    zona = u.campus.zona_horaria(tienda.campus_id)
    hoy = hoy_en(reloj, zona)
    if franja.ha_pasado(fecha, reloj.ahora(), ZoneInfo(zona)):
        raise ReglaIncumplida("franja_pasada", "Esa franja ya paso.")
    if fecha > hoy + timedelta(days=DIAS_HACIA_ADELANTE):
        raise ReglaIncumplida(
            "fecha_lejana", f"Publica turnos hasta {DIAS_HACIA_ADELANTE} dias adelante."
        )


def _validar_productos(u: UnidadCatalogo, tienda: Tienda, stock: dict[UUID, int]) -> None:
    if not stock:
        raise ReglaIncumplida("turno_sin_productos", "Un turno necesita al menos un producto.")
    for producto_id in stock:
        producto = u.productos.por_id(producto_id)
        if producto is None or producto.tienda_id != tienda.id:
            raise NoAutorizado("producto_ajeno", "Solo puedes ofrecer productos de tu tienda.")
