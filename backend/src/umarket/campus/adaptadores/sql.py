from sqlalchemy import select
from sqlalchemy.orm import Session

from umarket.bd.uow import UnidadSql
from umarket.campus.adaptadores.tablas import campus, franjas, puntos_encuentro
from umarket.campus.dominio.modelos import Campus, Franja, PuntoEncuentro


class RepositorioCampusSql:
    def __init__(self, sesion: Session) -> None:
        self._s = sesion

    def obtener(self, campus_id: str) -> Campus | None:
        fila = self._s.execute(select(campus).where(campus.c.id == campus_id)).mappings().first()
        if fila is None:
            return None
        return Campus(
            id=fila["id"],
            nombre=fila["nombre"],
            zona_horaria=fila["zona_horaria"],
            dominios_correo=tuple(fila["dominios_correo"]),
        )

    def puntos(self, campus_id: str) -> list[PuntoEncuentro]:
        filas = self._s.execute(
            select(puntos_encuentro)
            .where(puntos_encuentro.c.campus_id == campus_id)
            .order_by(puntos_encuentro.c.nombre)
        ).mappings()
        return [
            PuntoEncuentro(
                id=f["id"],
                campus_id=f["campus_id"],
                nombre=f["nombre"],
                descripcion=f["descripcion"],
                foto_url=f["foto_url"],
                alias=tuple(f["alias"]),
                activo=f["activo"],
            )
            for f in filas
        ]

    def franjas(self, campus_id: str) -> list[Franja]:
        filas = self._s.execute(select(franjas).where(franjas.c.campus_id == campus_id)).mappings()
        return [
            Franja(
                id=f["id"],
                campus_id=f["campus_id"],
                hora_inicio=f["hora_inicio"],
                hora_fin=f["hora_fin"],
            )
            for f in filas
        ]


class UnidadCampusSql(UnidadSql):
    def _al_abrir(self, sesion: Session) -> None:
        self.campus = RepositorioCampusSql(sesion)
