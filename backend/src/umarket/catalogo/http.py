"""Rutas del catalogo: publicas (comprador) y del vendedor."""

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field

from umarket.catalogo import (
    CATEGORIAS,
    ETIQUETAS,
    Categoria,
    DatosProducto,
    Etiqueta,
    Producto,
    Reputacion,
    ResumenTienda,
    Turno,
    VistaMiTienda,
    VistaTienda,
)
from umarket.contenedor import Contenedor
from umarket.http.sesion import campus_de, contenedor, usuario_opcional, usuario_requerido
from umarket.identidad import UsuarioSesion

router = APIRouter(prefix="/v1", tags=["catalogo"])


# -- DTOs --------------------------------------------------------------------


class ReputacionDTO(BaseModel):
    promedio: float | None
    resenas: int
    entregas: int
    porcentaje_cumplido: float | None
    rankeable: bool


def _reputacion(r: Reputacion) -> ReputacionDTO:
    return ReputacionDTO(
        promedio=r.promedio,
        resenas=r.resenas,
        entregas=r.entregas,
        porcentaje_cumplido=r.porcentaje_cumplido,
        rankeable=r.rankeable,
    )


class ProductoDTO(BaseModel):
    id: UUID
    nombre: str
    descripcion: str
    categoria: Categoria
    etiquetas: list[Etiqueta]
    precio_cop: int
    activo: bool


class OfertaDTO(BaseModel):
    producto_id: UUID
    total: int
    disponible: int


class TurnoDTO(BaseModel):
    id: UUID
    fecha: date
    franja_id: str
    franja_etiqueta: str
    punto_id: str
    punto_nombre: str
    abierto: bool
    ofertas: list[OfertaDTO]


class TurnoCreadoDTO(BaseModel):
    id: UUID
    fecha: date
    franja_id: str
    punto_id: str
    ofertas: list[OfertaDTO]


class ResumenTiendaDTO(BaseModel):
    id: UUID
    slug: str
    nombre: str
    descripcion: str
    productos_activos: int
    turnos_abiertos_hoy: int
    reputacion: ReputacionDTO


class TiendaDTO(BaseModel):
    id: UUID
    slug: str
    nombre: str
    descripcion: str
    productos: list[ProductoDTO]
    turnos: list[TurnoDTO]
    reputacion: ReputacionDTO


class MiTiendaDTO(TiendaDTO):
    hoy: date


class VocabularioDTO(BaseModel):
    categorias: list[Categoria]
    etiquetas: list[Etiqueta]


class NuevaTienda(BaseModel):
    nombre: str = Field(min_length=2, max_length=60)
    descripcion: str = Field(default="", max_length=280)


class DatosProductoDTO(BaseModel):
    nombre: str = Field(min_length=2, max_length=60)
    descripcion: str = Field(default="", max_length=280)
    categoria: Categoria
    etiquetas: list[Etiqueta] = Field(default_factory=list[Etiqueta], max_length=4)
    precio_cop: int = Field(gt=0)
    activo: bool = True


class LineaStock(BaseModel):
    producto_id: UUID
    total: int = Field(ge=0, le=500)


class NuevoTurno(BaseModel):
    fecha: date
    franja_id: str
    punto_id: str
    stock: list[LineaStock] = Field(min_length=1)


class CambioStock(BaseModel):
    stock: list[LineaStock] = Field(min_length=1)


class Duplicar(BaseModel):
    desde: date
    hacia: date


# -- traduccion ----------------------------------------------------------------


def _producto(p: Producto) -> ProductoDTO:
    return ProductoDTO(
        id=p.id,
        nombre=p.nombre,
        descripcion=p.descripcion,
        categoria=p.categoria,
        etiquetas=list(p.etiquetas),
        precio_cop=p.precio_cop,
        activo=p.activo,
    )


def _turno_simple(t: Turno) -> TurnoCreadoDTO:
    return TurnoCreadoDTO(
        id=t.id,
        fecha=t.fecha,
        franja_id=t.franja_id,
        punto_id=t.punto_id,
        ofertas=[
            OfertaDTO(producto_id=s.producto_id, total=s.total, disponible=s.disponible)
            for s in t.stock
        ],
    )


def _vista_a_dto(v: VistaTienda | VistaMiTienda) -> dict[str, object]:
    if isinstance(v, VistaMiTienda):
        cabecera = v.tienda
        reputacion = ReputacionDTO(
            promedio=None, resenas=0, entregas=0, porcentaje_cumplido=None, rankeable=False
        )
    else:
        cabecera = v
        reputacion = _reputacion(v.reputacion)
    return {
        "id": cabecera.id,
        "slug": cabecera.slug,
        "nombre": cabecera.nombre,
        "descripcion": cabecera.descripcion,
        "productos": [
            ProductoDTO(
                id=p.id,
                nombre=p.nombre,
                descripcion=p.descripcion,
                categoria=Categoria(p.categoria),
                etiquetas=[Etiqueta(e) for e in p.etiquetas],
                precio_cop=p.precio_cop,
                activo=p.activo,
            )
            for p in v.productos
        ],
        "turnos": [
            TurnoDTO(
                id=t.id,
                fecha=t.fecha,
                franja_id=t.franja_id,
                franja_etiqueta=t.franja_etiqueta,
                punto_id=t.punto_id,
                punto_nombre=t.punto_nombre,
                abierto=t.abierto,
                ofertas=[OfertaDTO(**o.__dict__) for o in t.ofertas],
            )
            for t in v.turnos
        ],
        "reputacion": reputacion,
    }


def _resumen(r: ResumenTienda) -> ResumenTiendaDTO:
    return ResumenTiendaDTO(
        id=r.id,
        slug=r.slug,
        nombre=r.nombre,
        descripcion=r.descripcion,
        productos_activos=r.productos_activos,
        turnos_abiertos_hoy=r.turnos_abiertos_hoy,
        reputacion=_reputacion(r.reputacion),
    )


# -- publicas ------------------------------------------------------------------


@router.get("/vocabulario")
def vocabulario() -> VocabularioDTO:
    return VocabularioDTO(
        categorias=[Categoria(c) for c in CATEGORIAS], etiquetas=[Etiqueta(e) for e in ETIQUETAS]
    )


@router.get("/tiendas")
def listar_tiendas(
    usuario: UsuarioSesion | None = Depends(usuario_opcional),
    c: Contenedor = Depends(contenedor),
) -> list[ResumenTiendaDTO]:
    return [_resumen(r) for r in c.listar_tiendas.ejecutar(campus_de(usuario, c))]


@router.get("/tiendas/{slug}")
def ver_tienda(slug: str, c: Contenedor = Depends(contenedor)) -> TiendaDTO:
    return TiendaDTO.model_validate(_vista_a_dto(c.ver_tienda.ejecutar(slug)))


# -- vendedor ------------------------------------------------------------------


@router.post("/vendedor/tienda", status_code=status.HTTP_201_CREATED)
def crear_tienda(
    datos: NuevaTienda,
    usuario: UsuarioSesion = Depends(usuario_requerido),
    c: Contenedor = Depends(contenedor),
) -> MiTiendaDTO:
    c.crear_tienda.ejecutar(usuario.id, usuario.campus_id, datos.nombre, datos.descripcion)
    return mi_tienda(usuario, c)


@router.get("/vendedor/tienda")
def mi_tienda(
    usuario: UsuarioSesion = Depends(usuario_requerido), c: Contenedor = Depends(contenedor)
) -> MiTiendaDTO:
    vista = c.ver_mi_tienda.ejecutar(usuario.id)
    return MiTiendaDTO.model_validate({**_vista_a_dto(vista), "hoy": vista.hoy})


@router.post("/vendedor/productos", status_code=status.HTTP_201_CREATED)
def crear_producto(
    datos: DatosProductoDTO,
    usuario: UsuarioSesion = Depends(usuario_requerido),
    c: Contenedor = Depends(contenedor),
) -> ProductoDTO:
    return _producto(c.guardar_producto.ejecutar(usuario.id, _datos(datos)))


@router.put("/vendedor/productos/{producto_id}")
def editar_producto(
    producto_id: UUID,
    datos: DatosProductoDTO,
    usuario: UsuarioSesion = Depends(usuario_requerido),
    c: Contenedor = Depends(contenedor),
) -> ProductoDTO:
    return _producto(c.guardar_producto.ejecutar(usuario.id, _datos(datos), producto_id))


@router.post("/vendedor/turnos", status_code=status.HTTP_201_CREATED)
def publicar_turno(
    datos: NuevoTurno,
    usuario: UsuarioSesion = Depends(usuario_requerido),
    c: Contenedor = Depends(contenedor),
) -> TurnoCreadoDTO:
    turno = c.publicar_turno.ejecutar(
        usuario.id, datos.fecha, datos.franja_id, datos.punto_id, _stock(datos.stock)
    )
    return _turno_simple(turno)


@router.put("/vendedor/turnos/{turno_id}/stock")
def editar_stock(
    turno_id: UUID,
    datos: CambioStock,
    usuario: UsuarioSesion = Depends(usuario_requerido),
    c: Contenedor = Depends(contenedor),
) -> TurnoCreadoDTO:
    return _turno_simple(c.editar_stock.ejecutar(usuario.id, turno_id, _stock(datos.stock)))


@router.post("/vendedor/turnos/duplicar")
def duplicar_turnos(
    datos: Duplicar,
    usuario: UsuarioSesion = Depends(usuario_requerido),
    c: Contenedor = Depends(contenedor),
) -> list[TurnoCreadoDTO]:
    return [
        _turno_simple(t) for t in c.duplicar_turnos.ejecutar(usuario.id, datos.desde, datos.hacia)
    ]


def _datos(d: DatosProductoDTO) -> DatosProducto:
    return DatosProducto(
        nombre=d.nombre,
        descripcion=d.descripcion,
        categoria=d.categoria,
        etiquetas=tuple(d.etiquetas),
        precio_cop=d.precio_cop,
        activo=d.activo,
    )


def _stock(lineas: list[LineaStock]) -> dict[UUID, int]:
    return {linea.producto_id: linea.total for linea in lineas}
