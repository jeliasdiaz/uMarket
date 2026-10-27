"""La aplicacion FastAPI.

Responsabilidad: montar los routers de cada modulo, el manejo de errores, la
verificacion de origen y la salud. No decide nada de negocio: cada router solo
traduce HTTP a un caso de uso del contenedor.
"""

from collections.abc import Iterable

from fastapi import APIRouter, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from umarket.contenedor import Contenedor
from umarket.http.errores import registrar_manejadores

METODOS_QUE_MODIFICAN = frozenset({"POST", "PUT", "PATCH", "DELETE"})


def crear_app(contenedor: Contenedor, routers: Iterable[APIRouter] = ()) -> FastAPI:
    app = FastAPI(title="uMarket API", version="0.1.0", openapi_url="/v1/openapi.json")
    app.state.contenedor = contenedor
    registrar_manejadores(app)
    for router in routers:
        app.include_router(router)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=contenedor.settings.origenes_permitidos,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def verificar_origen(request: Request, call_next):  # type: ignore[no-untyped-def]
        """Defensa CSRF: una peticion que modifica datos solo se acepta desde un origen permitido.

        Sin cabecera Origin (curl, tests, el proxy de Next.js del mismo sitio) se
        deja pasar: la cookie es SameSite=Lax, asi que un sitio ajeno no la envia
        en un POST.
        """
        origen = request.headers.get("origin")
        if (
            request.method in METODOS_QUE_MODIFICAN
            and origen is not None
            and origen not in contenedor.settings.origenes_permitidos
        ):
            return JSONResponse(
                status_code=403,
                media_type="application/problem+json",
                content={
                    "tipo": "origen_no_permitido",
                    "status": 403,
                    "detail": "Origen no permitido.",
                },
            )
        return await call_next(request)

    @app.get("/salud", tags=["salud"])
    def salud() -> dict[str, str]:
        return {"estado": "ok", "entorno": contenedor.settings.entorno}

    @app.get("/salud/bd", tags=["salud"])
    def salud_bd() -> dict[str, str]:
        return {"estado": "ok", "postgres": contenedor.verificar_bd()}

    return app
