"""Lo que ven el comprador y el vendedor de un pedido."""

from dataclasses import dataclass, field, replace
from datetime import date, datetime
from uuid import UUID

from umarket.pedidos.dominio.estados import Accion, Actor, Estado, acciones_posibles


@dataclass(frozen=True)
class ItemVista:
    producto_id: UUID
    nombre: str
    precio_unitario_cop: int
    cantidad: int


@dataclass(frozen=True)
class VistaPedido:
    id: UUID
    codigo: str
    estado: Estado
    tienda_id: UUID
    tienda_nombre: str
    tienda_slug: str
    vendedor_id: UUID
    comprador_id: UUID
    comprador_nombre: str
    fecha: date
    franja_id: str
    franja_etiqueta: str
    punto_id: str
    punto_nombre: str
    items: tuple[ItemVista, ...]
    total_cop: int
    creado_en: datetime
    vence_en: datetime
    llegada_en: datetime | None = None
    motivo: str | None = None
    calificado: bool = False
    acciones: tuple[Accion, ...] = field(default_factory=tuple[Accion, ...])

    def para(self, actor: Actor, ahora: datetime) -> "VistaPedido":
        """El estado efectivo y las acciones que ESE actor puede tomar ahora."""
        estado = self.estado
        if estado is Estado.PENDIENTE and ahora >= self.vence_en:
            estado = Estado.VENCIDO
        return replace(self, estado=estado, acciones=tuple(acciones_posibles(estado, actor)))
