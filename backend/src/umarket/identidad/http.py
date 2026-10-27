"""Rutas de acceso. Solo traducen HTTP a casos de uso."""

from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response, status
from pydantic import BaseModel, EmailStr, Field

from umarket.contenedor import Contenedor
from umarket.http.sesion import (
    COOKIE_SESION,
    contenedor,
    poner_cookie,
    quitar_cookie,
    usuario_requerido,
)
from umarket.identidad import UsuarioSesion

router = APIRouter(prefix="/v1", tags=["acceso"])


class PedirCodigo(BaseModel):
    correo: EmailStr


class Verificar(BaseModel):
    correo: EmailStr
    codigo: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")
    nombre: str | None = Field(default=None, max_length=60)
    acepta_terminos: bool = False


class UsuarioDTO(BaseModel):
    id: UUID
    campus_id: str
    correo: str
    nombre: str
    tienda_slug: str | None = None


def _dto(usuario: UsuarioSesion, tienda_slug: str | None = None) -> UsuarioDTO:
    return UsuarioDTO(
        id=usuario.id,
        campus_id=usuario.campus_id,
        correo=usuario.correo,
        nombre=usuario.nombre,
        tienda_slug=tienda_slug,
    )


@router.post("/auth/codigo", status_code=status.HTTP_202_ACCEPTED)
def pedir_codigo(datos: PedirCodigo, c: Contenedor = Depends(contenedor)) -> dict[str, str]:
    c.solicitar_codigo.ejecutar(datos.correo)
    return {"estado": "enviado"}


@router.post("/auth/verificar")
def verificar(
    datos: Verificar, response: Response, c: Contenedor = Depends(contenedor)
) -> UsuarioDTO:
    iniciada = c.verificar_codigo.ejecutar(
        datos.correo, datos.codigo, datos.nombre, datos.acepta_terminos
    )
    poner_cookie(response, c, iniciada.token)
    return _dto(iniciada.usuario, c.tienda_de_usuario(iniciada.usuario.id))


@router.post("/auth/salir", status_code=status.HTTP_204_NO_CONTENT)
def salir(request: Request, response: Response, c: Contenedor = Depends(contenedor)) -> None:
    token = request.cookies.get(COOKIE_SESION)
    if token:
        c.cerrar_sesion.ejecutar(token)
    quitar_cookie(response, c)


@router.get("/yo")
def yo(
    usuario: UsuarioSesion = Depends(usuario_requerido), c: Contenedor = Depends(contenedor)
) -> UsuarioDTO:
    return _dto(usuario, c.tienda_de_usuario(usuario.id))
