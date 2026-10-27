from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field

from umarket.contenedor import Contenedor
from umarket.http.sesion import contenedor, usuario_requerido
from umarket.identidad import UsuarioSesion

router = APIRouter(prefix="/v1", tags=["reputacion"])


class NuevaCalificacion(BaseModel):
    pedido_id: UUID
    estrellas: int = Field(ge=1, le=5)
    comentario: str = Field(default="", max_length=280)


class ResenaDTO(BaseModel):
    estrellas: int
    comentario: str
    creada_en: datetime


@router.post("/calificaciones", status_code=status.HTTP_201_CREATED)
def calificar(
    datos: NuevaCalificacion,
    usuario: UsuarioSesion = Depends(usuario_requerido),
    c: Contenedor = Depends(contenedor),
) -> dict[str, str]:
    c.calificar.ejecutar(datos.pedido_id, usuario.id, datos.estrellas, datos.comentario)
    return {"estado": "registrada"}


@router.get("/tiendas/{slug}/resenas")
def resenas(slug: str, c: Contenedor = Depends(contenedor)) -> list[ResenaDTO]:
    return [ResenaDTO(**r.__dict__) for r in c.resenas_de_tienda.ejecutar(slug)]
