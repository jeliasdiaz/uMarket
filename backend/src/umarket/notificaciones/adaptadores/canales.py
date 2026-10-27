"""Canales de aviso y el repositorio de suscripciones push."""

import json
import logging
from collections.abc import Callable
from typing import Any
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session, sessionmaker

from umarket.bd.uow import UnidadSql
from umarket.notificaciones.adaptadores.tablas import suscripciones_push
from umarket.notificaciones.dominio.avisos import Aviso
from umarket.notificaciones.puertos import Suscripcion

log = logging.getLogger("umarket.avisos")


class RepositorioSuscripcionesSql:
    def __init__(self, sesion: Session) -> None:
        self._s = sesion

    def guardar(self, suscripcion: Suscripcion) -> None:
        valores = {
            "usuario_id": suscripcion.usuario_id,
            "p256dh": suscripcion.p256dh,
            "auth": suscripcion.auth,
        }
        self._s.execute(
            pg_insert(suscripciones_push)
            .values(endpoint=suscripcion.endpoint, **valores)
            .on_conflict_do_update(index_elements=["endpoint"], set_=valores)
        )

    def eliminar(self, usuario_id: UUID, endpoint: str) -> None:
        self._s.execute(
            delete(suscripciones_push).where(
                suscripciones_push.c.endpoint == endpoint,
                suscripciones_push.c.usuario_id == usuario_id,
            )
        )


class UnidadNotificacionesSql(UnidadSql):
    def _al_abrir(self, sesion: Session) -> None:
        self.suscripciones = RepositorioSuscripcionesSql(sesion)


class CanalRegistro:
    """Para desarrollo y tests: guarda los avisos en memoria y los escribe en el log."""

    def __init__(self) -> None:
        self.enviados: list[Aviso] = []

    def enviar(self, aviso: Aviso) -> None:
        self.enviados.append(aviso)
        log.info("AVISO a %s: %s - %s", aviso.usuario_id, aviso.titulo, aviso.cuerpo)


type EnviarPush = Callable[[dict[str, Any], str], int]
"""(subscription_info, datos_json) -> codigo HTTP del servicio de push."""


def _enviar_con_pywebpush(clave_privada: str, contacto: str) -> EnviarPush:
    from pywebpush import WebPushException, webpush

    def enviar(suscripcion: dict[str, Any], datos: str) -> int:
        try:
            webpush(
                subscription_info=suscripcion,
                data=datos,
                vapid_private_key=clave_privada,
                vapid_claims={"sub": contacto},
                timeout=5,
            )
        except WebPushException as exc:
            respuesta = getattr(exc, "response", None)
            return int(getattr(respuesta, "status_code", 500) or 500)
        return 201

    return enviar


class CanalWebPush:
    """Web Push con VAPID. Una suscripcion que responde 404 o 410 ya no existe: se borra.

    En iPhone, el push solo llega si la PWA esta instalada en la pantalla de inicio
    (riesgo de PLAN-Y-DECISIONES §9): el frontend guia esa instalacion.
    """

    def __init__(
        self,
        fabrica: sessionmaker[Session],
        clave_privada: str,
        contacto: str,
        enviar: EnviarPush | None = None,
    ) -> None:
        self._fabrica = fabrica
        self._enviar = enviar or _enviar_con_pywebpush(clave_privada, contacto)

    def enviar(self, aviso: Aviso) -> None:
        datos = json.dumps(
            {"titulo": aviso.titulo, "cuerpo": aviso.cuerpo, "url": aviso.url}, ensure_ascii=False
        )
        with self._fabrica() as s:
            filas = list(
                s.execute(
                    select(suscripciones_push).where(
                        suscripciones_push.c.usuario_id == aviso.usuario_id
                    )
                ).mappings()
            )
            muertas: list[str] = []
            for f in filas:
                codigo = self._enviar(
                    {"endpoint": f["endpoint"], "keys": {"p256dh": f["p256dh"], "auth": f["auth"]}},
                    datos,
                )
                if codigo in (404, 410):
                    muertas.append(f["endpoint"])
                elif codigo >= 400:
                    log.warning("Push fallo (%s) para %s", codigo, aviso.usuario_id)
            if muertas:
                s.execute(
                    delete(suscripciones_push).where(suscripciones_push.c.endpoint.in_(muertas))
                )
                s.commit()
