"""Rutas de pedidos."""

from datetime import date, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Header, status
from pydantic import BaseModel, Field

from umarket.contenedor import Contenedor
from umarket.http.sesion import contenedor, usuario_requerido
from umarket.identidad import UsuarioSesion
from umarket.pedidos import Accion, ComandoCrearPedido, Estado, LineaSolicitada, Origen, VistaPedido

router = APIRouter(prefix="/v1", tags=["pedidos"])


class LineaDTO(BaseModel):
    producto_id: UUID
    cantidad: int = Field(ge=1, le=50)


class NuevoPedido(BaseModel):
    """Sin precios ni total: los pone el servidor desde el catalogo (PLAN-TECNICO.md §5.2)."""

    turno_id: UUID
    items: list[LineaDTO] = Field(min_length=1, max_length=20)
    origen: Origen = Origen.TIENDA
    busqueda_id: UUID | None = None


class Motivo(BaseModel):
    motivo: str | None = Field(default=None, max_length=200)


class ItemDTO(BaseModel):
    producto_id: UUID
    nombre: str
    precio_unitario_cop: int
    cantidad: int


class PedidoDTO(BaseModel):
    id: UUID
    codigo: str
    estado: Estado
    tienda_nombre: str
    tienda_slug: str
    comprador_nombre: str
    fecha: date
    franja_etiqueta: str
    punto_nombre: str
    items: list[ItemDTO]
    total_cop: int
    creado_en: datetime
    vence_en: datetime
    llegada_en: datetime | None
    motivo: str | None
    calificado: bool
    acciones: list[Accion]


def _dto(v: VistaPedido) -> PedidoDTO:
    return PedidoDTO(
        id=v.id,
        codigo=v.codigo,
        estado=v.estado,
        tienda_nombre=v.tienda_nombre,
        tienda_slug=v.tienda_slug,
        comprador_nombre=v.comprador_nombre,
        fecha=v.fecha,
        franja_etiqueta=v.franja_etiqueta,
        punto_nombre=v.punto_nombre,
        items=[ItemDTO(**i.__dict__) for i in v.items],
        total_cop=v.total_cop,
        creado_en=v.creado_en,
        vence_en=v.vence_en,
        llegada_en=v.llegada_en,
        motivo=v.motivo,
        calificado=v.calificado,
        acciones=list(v.acciones),
    )


@router.post("/pedidos", status_code=status.HTTP_201_CREATED)
def crear_pedido(
    datos: NuevoPedido,
    idempotency_key: str = Header(min_length=8, max_length=80),
    usuario: UsuarioSesion = Depends(usuario_requerido),
    c: Contenedor = Depends(contenedor),
) -> PedidoDTO:
    pedido = c.crear_pedido.ejecutar(
        ComandoCrearPedido(
            comprador_id=usuario.id,
            turno_id=datos.turno_id,
            lineas=tuple(LineaSolicitada(i.producto_id, i.cantidad) for i in datos.items),
            clave_idempotencia=idempotency_key,
            origen=datos.origen,
            busqueda_id=datos.busqueda_id,
        )
    )
    return _dto(c.consultar_pedidos.uno(pedido.id, usuario.id))


@router.get("/pedidos")
def mis_pedidos(
    usuario: UsuarioSesion = Depends(usuario_requerido), c: Contenedor = Depends(contenedor)
) -> list[PedidoDTO]:
    return [_dto(v) for v in c.consultar_pedidos.del_comprador(usuario.id)]


@router.get("/pedidos/{pedido_id}")
def ver_pedido(
    pedido_id: UUID,
    usuario: UsuarioSesion = Depends(usuario_requerido),
    c: Contenedor = Depends(contenedor),
) -> PedidoDTO:
    return _dto(c.consultar_pedidos.uno(pedido_id, usuario.id))


@router.post("/pedidos/{pedido_id}/{accion}")
def actuar(
    pedido_id: UUID,
    accion: Accion,
    datos: Motivo | None = None,
    usuario: UsuarioSesion = Depends(usuario_requerido),
    c: Contenedor = Depends(contenedor),
) -> PedidoDTO:
    c.actuar_sobre_pedido.ejecutar(pedido_id, usuario.id, accion, datos.motivo if datos else None)
    return _dto(c.consultar_pedidos.uno(pedido_id, usuario.id))


@router.get("/vendedor/pedidos")
def bandeja(
    usuario: UsuarioSesion = Depends(usuario_requerido), c: Contenedor = Depends(contenedor)
) -> list[PedidoDTO]:
    return [_dto(v) for v in c.consultar_pedidos.bandeja(usuario.id)]
