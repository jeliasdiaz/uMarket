from datetime import date, datetime
from typing import Protocol
from uuid import UUID

from umarket.compartido.aplicacion.puertos import BuzonEventos, UnidadDeTrabajo
from umarket.compartido.dominio.errores import Conflicto
from umarket.pedidos.aplicacion.vistas import VistaPedido
from umarket.pedidos.dominio.estados import Estado
from umarket.pedidos.dominio.pedido import Pedido
from umarket.pedidos.dominio.reglas import ContextoPedido, Limites


class PedidoDuplicado(Conflicto):
    """Otro request con la misma clave de idempotencia gano la carrera."""

    def __init__(self) -> None:
        super().__init__("pedido_duplicado", "Ese pedido ya se habia enviado.")


class RepositorioPedidos(Protocol):
    def por_id(self, pedido_id: UUID, bloquear: bool = False) -> Pedido | None: ...

    def por_clave(self, comprador_id: UUID, clave: str) -> Pedido | None: ...

    def codigo_usado(self, tienda_id: UUID, fecha: date, codigo: str) -> bool: ...

    def agregar(self, pedido: Pedido, clave_idempotencia: str) -> None:
        """Raises: PedidoDuplicado si la clave ya existe para ese comprador."""
        ...

    def guardar_estado(self, pedido: Pedido) -> None: ...

    def registrar_transicion(
        self,
        pedido_id: UUID,
        desde: Estado | None,
        hacia: Estado,
        accion: str,
        actor: str,
        motivo: str | None,
        en: datetime,
    ) -> None: ...

    def pendientes_vencidos(self, ahora: datetime, limite: int) -> list[Pedido]:
        """Bloqueados con SKIP LOCKED: dos workers no vencen el mismo pedido."""
        ...


class LectorContextoPedido(Protocol):
    def contexto(
        self, turno_id: UUID, comprador_id: UUID, ahora: datetime, limites: Limites
    ) -> ContextoPedido | None: ...


class ReservaStock(Protocol):
    """Lo implementa el catalogo, dueno de `stock_turno` (inversion de dependencias)."""

    def reservar(self, turno_id: UUID, producto_id: UUID, cantidad: int) -> bool:
        """Atomico: True si habia stock y quedo reservado; False si no alcanzaba."""
        ...

    def disponible(self, turno_id: UUID, producto_id: UUID) -> int: ...

    def liberar(self, turno_id: UUID, producto_id: UUID, cantidad: int) -> None: ...


class GeneradorCodigos(Protocol):
    def codigo(self) -> str: ...


class UnidadPedidos(UnidadDeTrabajo, Protocol):
    @property
    def pedidos(self) -> RepositorioPedidos: ...

    @property
    def contexto(self) -> LectorContextoPedido: ...

    @property
    def stock(self) -> ReservaStock: ...

    @property
    def eventos(self) -> BuzonEventos: ...


class ConsultasPedidos(Protocol):
    def vista(self, pedido_id: UUID) -> VistaPedido | None: ...

    def del_comprador(self, comprador_id: UUID) -> list[VistaPedido]: ...

    def de_vendedor(self, vendedor_id: UUID, desde: date) -> list[VistaPedido]: ...
