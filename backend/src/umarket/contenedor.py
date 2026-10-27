"""El contenedor: los casos de uso ya armados.

Solo es un dataclass. Lo llena `arranque.py` (la raiz de composicion) y lo leen
los routers HTTP y el worker. Los tests arman el suyo con otros adaptadores.
Sin framework de inyeccion de dependencias (PLAN-TECNICO.md §2.5).
"""

from collections.abc import Callable
from dataclasses import dataclass
from uuid import UUID

from umarket.busqueda import Buscar, RefinarBusqueda, RegistrarClic
from umarket.campus import ObtenerCampus
from umarket.catalogo import (
    CrearTienda,
    DuplicarTurnos,
    EditarStock,
    GuardarProducto,
    ListarTiendas,
    PublicarTurno,
    VerMiTienda,
    VerTienda,
)
from umarket.config import Settings
from umarket.identidad import CerrarSesion, ResolverSesion, SolicitarCodigo, VerificarCodigo
from umarket.notificaciones import GestionarSuscripciones
from umarket.pedidos import ActuarSobrePedido, ConsultarPedidos, CrearPedido
from umarket.reputacion import Calificar, ResenasDeTienda


@dataclass
class Contenedor:
    settings: Settings
    verificar_bd: Callable[[], str]
    # campus
    obtener_campus: ObtenerCampus
    # identidad
    solicitar_codigo: SolicitarCodigo
    verificar_codigo: VerificarCodigo
    resolver_sesion: ResolverSesion
    cerrar_sesion: CerrarSesion
    # El slug de la tienda de un usuario, si vende. Lo provee catalogo.
    tienda_de_usuario: Callable[[UUID], str | None]
    # catalogo
    listar_tiendas: ListarTiendas
    ver_tienda: VerTienda
    crear_tienda: CrearTienda
    ver_mi_tienda: VerMiTienda
    guardar_producto: GuardarProducto
    publicar_turno: PublicarTurno
    editar_stock: EditarStock
    duplicar_turnos: DuplicarTurnos
    # pedidos
    crear_pedido: CrearPedido
    actuar_sobre_pedido: ActuarSobrePedido
    consultar_pedidos: ConsultarPedidos
    # reputacion
    calificar: Calificar
    resenas_de_tienda: ResenasDeTienda
    # avisos
    suscripciones: GestionarSuscripciones
    # busqueda
    buscar: Buscar
    refinar_busqueda: RefinarBusqueda
    registrar_clic: RegistrarClic
