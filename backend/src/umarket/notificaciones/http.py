from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field

from umarket.contenedor import Contenedor
from umarket.http.sesion import contenedor, usuario_requerido
from umarket.identidad import UsuarioSesion

router = APIRouter(prefix="/v1/push", tags=["avisos"])


class Claves(BaseModel):
    p256dh: str = Field(min_length=10, max_length=200)
    auth: str = Field(min_length=10, max_length=100)


class SuscripcionDTO(BaseModel):
    """La forma de `PushSubscription.toJSON()` del navegador."""

    endpoint: str = Field(max_length=1000)
    keys: Claves


class Desuscribir(BaseModel):
    endpoint: str = Field(max_length=1000)


@router.get("/clave-publica")
def clave_publica(c: Contenedor = Depends(contenedor)) -> dict[str, str]:
    return {"clave": c.settings.vapid_clave_publica}


@router.post("/suscripciones", status_code=status.HTTP_201_CREATED)
def suscribir(
    datos: SuscripcionDTO,
    usuario: UsuarioSesion = Depends(usuario_requerido),
    c: Contenedor = Depends(contenedor),
) -> dict[str, str]:
    c.suscripciones.suscribir(usuario.id, datos.endpoint, datos.keys.p256dh, datos.keys.auth)
    return {"estado": "suscrito"}


@router.post("/desuscribir", status_code=status.HTTP_204_NO_CONTENT)
def desuscribir(
    datos: Desuscribir,
    usuario: UsuarioSesion = Depends(usuario_requerido),
    c: Contenedor = Depends(contenedor),
) -> None:
    c.suscripciones.desuscribir(usuario.id, datos.endpoint)
