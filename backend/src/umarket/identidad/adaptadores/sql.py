from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import delete, func, insert, select, update
from sqlalchemy.orm import Session

from umarket.bd.uow import UnidadSql
from umarket.campus.adaptadores.tablas import campus
from umarket.identidad.adaptadores.tablas import (
    codigos_acceso,
    consentimientos,
    sesiones,
    usuarios,
)
from umarket.identidad.dominio.modelos import CodigoAcceso, Sesion, Usuario


def _usuario(fila: Any) -> Usuario:
    return Usuario(
        id=fila["id"],
        campus_id=fila["campus_id"],
        correo=fila["correo"],
        nombre=fila["nombre"],
        creado_en=fila["creado_en"],
    )


class RepositorioUsuariosSql:
    def __init__(self, sesion: Session) -> None:
        self._s = sesion

    def por_correo(self, correo: str) -> Usuario | None:
        fila = self._s.execute(select(usuarios).where(usuarios.c.correo == correo))
        fila = fila.mappings().first()
        return None if fila is None else _usuario(fila)

    def por_id(self, usuario_id: UUID) -> Usuario | None:
        fila = self._s.execute(select(usuarios).where(usuarios.c.id == usuario_id))
        fila = fila.mappings().first()
        return None if fila is None else _usuario(fila)

    def agregar(self, usuario: Usuario, version_terminos: str) -> None:
        self._s.execute(
            insert(usuarios).values(
                id=usuario.id,
                campus_id=usuario.campus_id,
                correo=usuario.correo,
                nombre=usuario.nombre,
                creado_en=usuario.creado_en,
            )
        )
        self._s.execute(
            insert(consentimientos).values(
                id=uuid4(),
                usuario_id=usuario.id,
                version_terminos=version_terminos,
                aceptado_en=usuario.creado_en,
            )
        )


class RepositorioCodigosSql:
    def __init__(self, sesion: Session) -> None:
        self._s = sesion

    def agregar(self, codigo: CodigoAcceso) -> None:
        self._s.execute(
            insert(codigos_acceso).values(
                id=codigo.id,
                correo=codigo.correo,
                codigo_huella=codigo.codigo_huella,
                creado_en=codigo.creado_en,
                expira_en=codigo.expira_en,
            )
        )

    def ultimo_vigente(self, correo: str, ahora: datetime) -> CodigoAcceso | None:
        fila = (
            self._s.execute(
                select(codigos_acceso)
                .where(
                    codigos_acceso.c.correo == correo,
                    codigos_acceso.c.usado_en.is_(None),
                    codigos_acceso.c.expira_en > ahora,
                )
                .order_by(codigos_acceso.c.creado_en.desc())
                .limit(1)
                .with_for_update()
            )
            .mappings()
            .first()
        )
        if fila is None:
            return None
        return CodigoAcceso(
            id=fila["id"],
            correo=fila["correo"],
            codigo_huella=fila["codigo_huella"],
            creado_en=fila["creado_en"],
            expira_en=fila["expira_en"],
            intentos=fila["intentos"],
            usado_en=fila["usado_en"],
        )

    def guardar(self, codigo: CodigoAcceso) -> None:
        self._s.execute(
            update(codigos_acceso)
            .where(codigos_acceso.c.id == codigo.id)
            .values(intentos=codigo.intentos, usado_en=codigo.usado_en)
        )

    def emitidos_desde(self, correo: str, desde: datetime) -> int:
        return self._s.execute(
            select(func.count())
            .select_from(codigos_acceso)
            .where(codigos_acceso.c.correo == correo, codigos_acceso.c.creado_en >= desde)
        ).scalar_one()


class RepositorioSesionesSql:
    def __init__(self, sesion: Session) -> None:
        self._s = sesion

    def agregar(self, sesion: Sesion) -> None:
        self._s.execute(
            insert(sesiones).values(
                token_huella=sesion.token_huella,
                usuario_id=sesion.usuario_id,
                expira_en=sesion.expira_en,
            )
        )

    def vigente(self, token_huella: str, ahora: datetime) -> Sesion | None:
        fila = (
            self._s.execute(
                select(sesiones).where(
                    sesiones.c.token_huella == token_huella, sesiones.c.expira_en > ahora
                )
            )
            .mappings()
            .first()
        )
        if fila is None:
            return None
        return Sesion(fila["token_huella"], fila["usuario_id"], fila["expira_en"])

    def eliminar(self, token_huella: str) -> None:
        self._s.execute(delete(sesiones).where(sesiones.c.token_huella == token_huella))


class BuscadorCampusSql:
    """Lectura cruzada: identidad lee la tabla de campus (CQRS ligero, PLAN-TECNICO.md §2.6)."""

    def __init__(self, sesion: Session) -> None:
        self._s = sesion

    def por_dominio_de_correo(self, dominio: str) -> str | None:
        return self._s.execute(
            select(campus.c.id).where(campus.c.dominios_correo.any(dominio.lower()))
        ).scalar_one_or_none()


class UnidadIdentidadSql(UnidadSql):
    def _al_abrir(self, sesion: Session) -> None:
        self.usuarios = RepositorioUsuariosSql(sesion)
        self.codigos = RepositorioCodigosSql(sesion)
        self.sesiones = RepositorioSesionesSql(sesion)
        self.campus = BuscadorCampusSql(sesion)
