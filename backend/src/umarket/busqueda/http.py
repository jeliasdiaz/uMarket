"""Rutas de la busqueda por intencion."""

import time
from collections import defaultdict, deque
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel, Field

from umarket.busqueda import ConsultaInterpretada, ResultadoBusqueda
from umarket.compartido.dominio.errores import LimiteExcedido
from umarket.contenedor import Contenedor
from umarket.http.sesion import campus_de, contenedor, usuario_opcional
from umarket.identidad import UsuarioSesion

router = APIRouter(prefix="/v1", tags=["busqueda"])

# Limite por persona o IP: cada busqueda puede costar una llamada al modelo.
MAX_POR_MINUTO = 20
_recientes: dict[str, deque[float]] = defaultdict(deque)


def _limitar(clave: str) -> None:
    ahora = time.monotonic()
    ventana = _recientes[clave]
    while ventana and ahora - ventana[0] > 60:
        ventana.popleft()
    if len(ventana) >= MAX_POR_MINUTO:
        raise LimiteExcedido("demasiadas_busquedas", "Vas muy rapido. Espera un momento.")
    ventana.append(ahora)


class NuevaBusqueda(BaseModel):
    texto: str = Field(min_length=1, max_length=200)


class Refinar(BaseModel):
    consulta: ConsultaInterpretada


class Clic(BaseModel):
    tienda_id: UUID
    producto_id: UUID | None = None
    posicion: int = Field(ge=0, le=100)


class FiltroDTO(BaseModel):
    campo: str
    etiqueta: str


class ProductoEncontradoDTO(BaseModel):
    producto_id: UUID
    nombre: str
    precio_cop: int
    disponible: int
    cantidad_sugerida: int


class TiendaEncontradaDTO(BaseModel):
    tienda_id: UUID
    slug: str
    nombre: str
    promedio: float | None
    resenas: int
    turno_id: UUID
    franja_etiqueta: str
    punto_id: str
    punto_nombre: str
    productos: list[ProductoEncontradoDTO]


class OpcionPuntoDTO(BaseModel):
    id: str
    nombre: str


class ResultadoBusquedaDTO(BaseModel):
    busqueda_id: UUID
    interprete: str
    consulta: ConsultaInterpretada
    filtros: list[FiltroDTO]
    anulados: list[str]
    relajados: list[str]
    pregunta_punto: list[OpcionPuntoDTO]
    tiendas: list[TiendaEncontradaDTO]


def _dto(r: ResultadoBusqueda) -> ResultadoBusquedaDTO:
    return ResultadoBusquedaDTO(
        busqueda_id=r.busqueda_id,
        interprete=r.interprete,
        consulta=r.consulta,
        filtros=[FiltroDTO(campo=f.campo, etiqueta=f.etiqueta) for f in r.filtros],
        anulados=list(r.anulados),
        relajados=list(r.relajados),
        pregunta_punto=[OpcionPuntoDTO(id=p.id, nombre=p.nombre) for p in r.pregunta_punto],
        tiendas=[
            TiendaEncontradaDTO(
                tienda_id=t.tienda_id,
                slug=t.slug,
                nombre=t.nombre,
                promedio=t.promedio,
                resenas=t.resenas,
                turno_id=t.turno_id,
                franja_etiqueta=t.franja_etiqueta,
                punto_id=t.punto_id,
                punto_nombre=t.punto_nombre,
                productos=[ProductoEncontradoDTO(**p.__dict__) for p in t.productos],
            )
            for t in r.tiendas
        ],
    )


@router.post("/busquedas")
def buscar(
    datos: NuevaBusqueda,
    request: Request,
    usuario: UsuarioSesion | None = Depends(usuario_opcional),
    c: Contenedor = Depends(contenedor),
) -> ResultadoBusquedaDTO:
    ip = request.client.host if request.client else "?"
    _limitar(str(usuario.id) if usuario else ip)
    resultado = c.buscar.ejecutar(
        datos.texto,
        campus_de(usuario, c),
        usuario.id if usuario else None,
        semilla=str(usuario.id) if usuario else ip,
    )
    return _dto(resultado)


@router.post("/busquedas/{busqueda_id}/filtros")
def refinar(
    busqueda_id: UUID,
    datos: Refinar,
    usuario: UsuarioSesion | None = Depends(usuario_opcional),
    c: Contenedor = Depends(contenedor),
) -> ResultadoBusquedaDTO:
    return _dto(c.refinar_busqueda.ejecutar(busqueda_id, datos.consulta, campus_de(usuario, c)))


@router.post("/busquedas/{busqueda_id}/clics", status_code=status.HTTP_204_NO_CONTENT)
def clic(busqueda_id: UUID, datos: Clic, c: Contenedor = Depends(contenedor)) -> None:
    c.registrar_clic.ejecutar(busqueda_id, datos.tienda_id, datos.producto_id, datos.posicion)
