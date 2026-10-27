from fastapi import APIRouter, Depends
from pydantic import BaseModel

from umarket.campus import VistaCampus
from umarket.contenedor import Contenedor
from umarket.http.sesion import campus_de, contenedor, usuario_opcional
from umarket.identidad import UsuarioSesion

router = APIRouter(prefix="/v1", tags=["campus"])


class PuntoDTO(BaseModel):
    id: str
    nombre: str
    descripcion: str
    foto_url: str | None
    alias: list[str]


class FranjaDTO(BaseModel):
    id: str
    inicio: str
    fin: str
    etiqueta: str


class CampusDTO(BaseModel):
    id: str
    nombre: str
    zona_horaria: str
    puntos: list[PuntoDTO]
    franjas: list[FranjaDTO]


def campus_dto(vista: VistaCampus) -> CampusDTO:
    return CampusDTO(
        id=vista.campus.id,
        nombre=vista.campus.nombre,
        zona_horaria=vista.campus.zona_horaria,
        puntos=[
            PuntoDTO(
                id=p.id,
                nombre=p.nombre,
                descripcion=p.descripcion,
                foto_url=p.foto_url,
                alias=list(p.alias),
            )
            for p in vista.puntos
        ],
        franjas=[
            FranjaDTO(
                id=f.id,
                inicio=f"{f.hora_inicio:%H:%M}",
                fin=f"{f.hora_fin:%H:%M}",
                etiqueta=f.etiqueta,
            )
            for f in vista.franjas
        ],
    )


@router.get("/campus/actual")
def campus_actual(
    usuario: UsuarioSesion | None = Depends(usuario_opcional),
    c: Contenedor = Depends(contenedor),
) -> CampusDTO:
    return campus_dto(c.obtener_campus.ejecutar(campus_de(usuario, c)))
