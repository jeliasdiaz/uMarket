from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from umarket.compartido.aplicacion.puertos import BuzonEventos, UnidadDeTrabajo
from umarket.reputacion.dominio.modelos import Calificacion, Metricas


@dataclass(frozen=True)
class PedidoCalificable:
    pedido_id: UUID
    tienda_id: UUID
    comprador_id: UUID
    estado: str


@dataclass(frozen=True)
class ResenaVista:
    estrellas: int
    comentario: str
    creada_en: datetime


class RepositorioReputacion(Protocol):
    def pedido(self, pedido_id: UUID) -> PedidoCalificable | None: ...

    def ya_calificado(self, pedido_id: UUID) -> bool: ...

    def agregar(self, calificacion: Calificacion) -> None: ...

    def contar(self, tienda_id: UUID) -> Metricas:
        """Recalcula desde pedidos, transiciones y calificaciones."""
        ...

    def guardar_metricas(self, tienda_id: UUID, metricas: Metricas, en: datetime) -> None: ...

    def resenas_por_slug(self, slug: str, limite: int) -> list[ResenaVista]: ...


class UnidadReputacion(UnidadDeTrabajo, Protocol):
    @property
    def reputacion(self) -> RepositorioReputacion: ...

    @property
    def eventos(self) -> BuzonEventos: ...
