"""Calificar, recalcular metricas, leer resenas y ordenar tiendas."""

from collections.abc import Callable
from uuid import UUID, uuid4

from umarket.compartido.dominio.errores import Conflicto, NoEncontrado, ReglaIncumplida
from umarket.compartido.dominio.eventos import Evento
from umarket.compartido.dominio.reloj import Reloj
from umarket.reputacion.dominio.modelos import Calificacion, Metricas
from umarket.reputacion.puertos import ResenaVista, UnidadReputacion

type FabricaUnidad = Callable[[], UnidadReputacion]


class Calificar:
    """Solo califica quien recibio el pedido, y una sola vez (PDF: manipulacion de resenas)."""

    def __init__(self, unidad: FabricaUnidad, reloj: Reloj) -> None:
        self._unidad = unidad
        self._reloj = reloj

    def ejecutar(self, pedido_id: UUID, usuario_id: UUID, estrellas: int, comentario: str) -> None:
        ahora = self._reloj.ahora()
        with self._unidad() as u:
            pedido = u.reputacion.pedido(pedido_id)
            if pedido is None or pedido.comprador_id != usuario_id:
                raise NoEncontrado("pedido_no_encontrado", "Ese pedido no existe.")
            if pedido.estado != "entregado":
                raise ReglaIncumplida(
                    "aun_no_entregado", "Solo puedes calificar despues de recibir el pedido."
                )
            if u.reputacion.ya_calificado(pedido_id):
                raise Conflicto("ya_calificado", "Ya calificaste este pedido.")
            u.reputacion.agregar(
                Calificacion(
                    uuid4(), pedido_id, pedido.tienda_id, usuario_id, estrellas, comentario, ahora
                )
            )
            u.eventos.publicar(
                Evento(
                    "calificacion.registrada",
                    {"pedido_id": str(pedido_id), "tienda_id": str(pedido.tienda_id)},
                    ahora,
                )
            )
            u.confirmar()


class RecalcularMetricas:
    """Manejador de eventos. Recalcula en vez de sumar: entregar el evento dos veces no duplica."""

    EVENTOS = (
        "pedido.entregado",
        "pedido.vencido",
        "pedido.cancelado",
        "calificacion.registrada",
    )

    def __init__(self, unidad: FabricaUnidad, reloj: Reloj) -> None:
        self._unidad = unidad
        self._reloj = reloj

    def ejecutar(self, tienda_id: UUID) -> Metricas:
        with self._unidad() as u:
            metricas = u.reputacion.contar(tienda_id)
            u.reputacion.guardar_metricas(tienda_id, metricas, self._reloj.ahora())
            u.confirmar()
            return metricas

    def manejar(self, evento: Evento) -> None:
        tienda_id = evento.datos.get("tienda_id")
        if isinstance(tienda_id, str):
            self.ejecutar(UUID(tienda_id))


class ResenasDeTienda:
    def __init__(self, unidad: FabricaUnidad) -> None:
        self._unidad = unidad

    def ejecutar(self, slug: str, limite: int = 20) -> list[ResenaVista]:
        with self._unidad() as u:
            return u.reputacion.resenas_por_slug(slug, limite)
