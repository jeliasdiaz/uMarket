"""La sesion en HTTP: la cookie y las dependencias de FastAPI.

La cookie es `HttpOnly` (JavaScript no la lee), `SameSite=Lax` (un sitio ajeno no
la envia en un POST) y `Secure` fuera de local. El frontend la recibe como cookie
de primera parte porque Next.js reenvia `/api/*` al backend (PLAN-TECNICO.md §10).
"""

from fastapi import Request, Response

from umarket.compartido.dominio.errores import NoAutenticado
from umarket.contenedor import Contenedor
from umarket.identidad import UsuarioSesion

COOKIE_SESION = "umarket_sesion"


def contenedor(request: Request) -> Contenedor:
    return request.app.state.contenedor


def poner_cookie(response: Response, c: Contenedor, token: str) -> None:
    response.set_cookie(
        COOKIE_SESION,
        token,
        max_age=c.settings.dias_sesion * 24 * 3600,
        httponly=True,
        secure=c.settings.cookie_segura,
        samesite="lax",
        path="/",
    )


def quitar_cookie(response: Response, c: Contenedor) -> None:
    response.delete_cookie(
        COOKIE_SESION, httponly=True, secure=c.settings.cookie_segura, samesite="lax", path="/"
    )


def usuario_opcional(request: Request) -> UsuarioSesion | None:
    token = request.cookies.get(COOKIE_SESION)
    if not token:
        return None
    return contenedor(request).resolver_sesion.ejecutar(token)


def campus_de(usuario: UsuarioSesion | None, c: Contenedor) -> str:
    """El campus de quien pregunta; sin sesion, el campus por defecto (MVP: uno solo)."""
    return usuario.campus_id if usuario else c.settings.campus_por_defecto


def usuario_requerido(request: Request) -> UsuarioSesion:
    usuario = usuario_opcional(request)
    if usuario is None:
        raise NoAutenticado("sin_sesion", "Entra con tu correo institucional para continuar.")
    return usuario
