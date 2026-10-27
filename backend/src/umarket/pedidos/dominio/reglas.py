"""Reglas para crear un pedido (conjunto `pedido-v1`), una clase por regla.

El stock NO es una regla: lo garantiza la base de datos con una reserva atomica
(D-14). Una regla revisa una foto del momento; la transaccion es la garantia.

Cada regla tiene dos tests: uno que la dispara y otro que confirma que no da
falso positivo (`tests/pedidos/test_reglas.py`).
"""

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date, datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from umarket.compartido.dominio.reglas import ConjuntoReglas, Hallazgo, Regla


@dataclass(frozen=True)
class LineaSolicitada:
    producto_id: UUID
    cantidad: int


@dataclass(frozen=True)
class SolicitudPedido:
    comprador_id: UUID
    turno_id: UUID
    lineas: tuple[LineaSolicitada, ...]


@dataclass(frozen=True)
class OfertaEnTurno:
    producto_id: UUID
    nombre: str
    precio_cop: int
    activo: bool
    disponible: int


@dataclass(frozen=True)
class Limites:
    max_unidades_por_item: int = 20
    pedidos_abiertos: int = 2
    inasistencias: int = 3


@dataclass(frozen=True)
class ContextoPedido:
    """Todo lo que las reglas necesitan saber, leido en la misma transaccion."""

    tienda_id: UUID
    vendedor_id: UUID
    campus_id: str
    fecha: date
    franja_id: str
    franja_fin: datetime
    punto_id: str
    ofertas: dict[UUID, OfertaEnTurno]
    pedidos_abiertos_del_comprador: int
    inasistencias_del_comprador: int
    ahora: datetime
    zona: ZoneInfo
    limites: Limites = field(default_factory=Limites)


class ProductoDelTurno:
    id = "producto_del_turno"

    def revisar(self, s: SolicitudPedido, c: ContextoPedido) -> Iterable[Hallazgo]:
        for linea in s.lineas:
            oferta = c.ofertas.get(linea.producto_id)
            if oferta is None or not oferta.activo:
                yield Hallazgo(
                    self.id, str(linea.producto_id), "Ese producto no se ofrece en este turno."
                )


class TurnoVigente:
    id = "turno_vencido"

    def revisar(self, s: SolicitudPedido, c: ContextoPedido) -> Iterable[Hallazgo]:
        if c.ahora >= c.franja_fin:
            yield Hallazgo(self.id, "turno_id", "Esa franja ya paso. Elige otra.")


class CantidadRazonable:
    id = "cantidad_invalida"

    def revisar(self, s: SolicitudPedido, c: ContextoPedido) -> Iterable[Hallazgo]:
        maximo = c.limites.max_unidades_por_item
        for linea in s.lineas:
            if not 1 <= linea.cantidad <= maximo:
                yield Hallazgo(
                    self.id, str(linea.producto_id), f"Pide entre 1 y {maximo} unidades."
                )


class NoEsSuPropiaTienda:
    id = "pedido_a_si_mismo"

    def revisar(self, s: SolicitudPedido, c: ContextoPedido) -> Iterable[Hallazgo]:
        if s.comprador_id == c.vendedor_id:
            yield Hallazgo(self.id, "comprador_id", "No puedes pedirle a tu propia tienda.")


class LimitePedidosAbiertos:
    id = "demasiados_pedidos_abiertos"

    def revisar(self, s: SolicitudPedido, c: ContextoPedido) -> Iterable[Hallazgo]:
        if c.pedidos_abiertos_del_comprador >= c.limites.pedidos_abiertos:
            yield Hallazgo(
                self.id,
                "comprador_id",
                f"Ya tienes {c.pedidos_abiertos_del_comprador} pedidos abiertos. "
                f"Recibe o cancela uno antes de pedir otro.",
            )


class CompradorHabilitado:
    id = "comprador_bloqueado"

    def revisar(self, s: SolicitudPedido, c: ContextoPedido) -> Iterable[Hallazgo]:
        if c.inasistencias_del_comprador >= c.limites.inasistencias:
            yield Hallazgo(
                self.id,
                "comprador_id",
                "Tienes varias inasistencias a pedidos aprobados. Habla con soporte.",
            )


type ReglaPedido = Regla[SolicitudPedido, ContextoPedido]

_VERSIONES: dict[str, tuple[ReglaPedido, ...]] = {
    "pedido-v1": (
        ProductoDelTurno(),
        TurnoVigente(),
        CantidadRazonable(),
        NoEsSuPropiaTienda(),
        LimitePedidosAbiertos(),
        CompradorHabilitado(),
    ),
}


def reglas_pedido(version: str) -> ConjuntoReglas[SolicitudPedido, ContextoPedido]:
    """Un conjunto ya medido no se edita: una regla nueva va en una version nueva."""
    if version not in _VERSIONES:
        raise KeyError(f"No existe el conjunto '{version}'. Disponibles: {sorted(_VERSIONES)}")
    return ConjuntoReglas(version, _VERSIONES[version])
