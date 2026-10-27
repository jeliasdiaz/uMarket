from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from umarket.compartido.aplicacion.puertos import UnidadDeTrabajo
from umarket.notificaciones.dominio.avisos import Aviso


class CanalNotificacion(Protocol):
    """Un canal de aviso. Uno nuevo (correo, WhatsApp) es otra clase registrada en arranque."""

    def enviar(self, aviso: Aviso) -> None: ...


@dataclass(frozen=True)
class Suscripcion:
    usuario_id: UUID
    endpoint: str
    p256dh: str
    auth: str


class RepositorioSuscripciones(Protocol):
    def guardar(self, suscripcion: Suscripcion) -> None: ...

    def eliminar(self, usuario_id: UUID, endpoint: str) -> None: ...


class UnidadNotificaciones(UnidadDeTrabajo, Protocol):
    @property
    def suscripciones(self) -> RepositorioSuscripciones: ...
