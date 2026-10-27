"""La traduccion de errores de dominio a HTTP, en un solo lugar.

Formato RFC 9457 (`application/problem+json`). El frontend decide que mostrar a
partir de `tipo`, que es estable; `detail` es para personas.
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from umarket.compartido.dominio.errores import (
    Conflicto,
    ErrorDominio,
    LimiteExcedido,
    NoAutenticado,
    NoAutorizado,
    NoEncontrado,
    ReglaIncumplida,
)

ESTADO_POR_FAMILIA: tuple[tuple[type[ErrorDominio], int], ...] = (
    (NoEncontrado, 404),
    (NoAutenticado, 401),
    (NoAutorizado, 403),
    (Conflicto, 409),
    (ReglaIncumplida, 422),
    (LimiteExcedido, 429),
)


def estado_de(error: ErrorDominio) -> int:
    for familia, estado in ESTADO_POR_FAMILIA:
        if isinstance(error, familia):
            return estado
    return 400


def problema(error: ErrorDominio) -> JSONResponse:
    estado = estado_de(error)
    return JSONResponse(
        status_code=estado,
        media_type="application/problem+json",
        content={
            "type": f"https://umarket.local/errores/{error.tipo}",
            "tipo": error.tipo,
            "title": error.tipo.replace("_", " "),
            "status": estado,
            "detail": error.mensaje,
            "detalles": {
                k: str(v) if not isinstance(v, int | float | bool) else v
                for k, v in error.detalles.items()
            },
        },
    )


def registrar_manejadores(app: FastAPI) -> None:
    async def _manejar(_request: Request, exc: Exception) -> JSONResponse:
        assert isinstance(exc, ErrorDominio)
        return problema(exc)

    app.add_exception_handler(ErrorDominio, _manejar)
