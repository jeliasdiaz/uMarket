from collections.abc import Callable, Sequence
from uuid import UUID

from umarket.compartido.dominio.errores import ReglaIncumplida
from umarket.compartido.dominio.eventos import Evento
from umarket.notificaciones.dominio.avisos import avisos_de
from umarket.notificaciones.puertos import CanalNotificacion, Suscripcion, UnidadNotificaciones


class NotificarEvento:
    """Manejador de eventos: arma los avisos y los manda por todos los canales registrados."""

    def __init__(self, canales: Sequence[CanalNotificacion]) -> None:
        self._canales = canales

    def manejar(self, evento: Evento) -> None:
        for aviso in avisos_de(evento):
            for canal in self._canales:
                canal.enviar(aviso)


class GestionarSuscripciones:
    def __init__(self, unidad: Callable[[], UnidadNotificaciones]) -> None:
        self._unidad = unidad

    def suscribir(self, usuario_id: UUID, endpoint: str, p256dh: str, auth: str) -> None:
        if not endpoint.startswith("https://"):
            raise ReglaIncumplida("suscripcion_invalida", "La suscripcion push no es valida.")
        with self._unidad() as u:
            u.suscripciones.guardar(Suscripcion(usuario_id, endpoint, p256dh, auth))
            u.confirmar()

    def desuscribir(self, usuario_id: UUID, endpoint: str) -> None:
        with self._unidad() as u:
            u.suscripciones.eliminar(usuario_id, endpoint)
            u.confirmar()
