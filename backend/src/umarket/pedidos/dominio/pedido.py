"""El pedido.

El precio de cada item lo pone el servidor desde el catalogo y el total lo
calcula esta entidad: el comando de crear pedido NO tiene campo de precio
(PLAN-TECNICO.md §5.2). Igual que con el contrato del modelo de lenguaje, el
campo que se podria manipular simplemente no existe.
"""

from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta
from enum import StrEnum
from uuid import UUID

from umarket.compartido.dominio.errores import Conflicto, NoAutorizado, ReglaIncumplida
from umarket.pedidos.dominio.estados import TRANSICIONES, Accion, Actor, Estado, Transicion

# Sin 0/O, 1/I/L, 2/Z, 5/S, 8/B: el codigo se dice en voz alta en el punto de encuentro.
ALFABETO_CODIGO = "ACDEFHJKMNPRTUVWXY34679"


class Origen(StrEnum):
    TIENDA = "tienda"
    BUSQUEDA = "busqueda"


@dataclass(frozen=True)
class ItemPedido:
    producto_id: UUID
    nombre: str
    precio_unitario_cop: int
    cantidad: int

    @property
    def subtotal_cop(self) -> int:
        return self.precio_unitario_cop * self.cantidad


@dataclass(frozen=True)
class Pedido:
    id: UUID
    codigo: str
    campus_id: str
    tienda_id: UUID
    vendedor_id: UUID
    comprador_id: UUID
    turno_id: UUID
    fecha: date
    franja_id: str
    punto_id: str
    items: tuple[ItemPedido, ...]
    estado: Estado
    creado_en: datetime
    vence_en: datetime
    actualizado_en: datetime
    origen: Origen = Origen.TIENDA
    busqueda_id: UUID | None = None
    llegada_en: datetime | None = None
    motivo: str | None = None

    def __post_init__(self) -> None:
        if not self.items:
            raise ReglaIncumplida("pedido_vacio", "Un pedido necesita al menos un producto.")

    @property
    def total_cop(self) -> int:
        return sum(i.subtotal_cop for i in self.items)

    def actor_de(self, usuario_id: UUID) -> Actor:
        if usuario_id == self.vendedor_id:
            return Actor.VENDEDOR
        if usuario_id == self.comprador_id:
            return Actor.COMPRADOR
        raise NoAutorizado("pedido_ajeno", "Ese pedido no es tuyo.")

    def estado_efectivo(self, ahora: datetime) -> Estado:
        """Un pendiente que ya vencio ES vencido, aunque el worker no haya pasado todavia."""
        if self.estado is Estado.PENDIENTE and ahora >= self.vence_en:
            return Estado.VENCIDO
        return self.estado

    def aplicar(
        self,
        accion: Accion,
        actor: Actor,
        ahora: datetime,
        motivo: str | None = None,
        espera_no_asistio: timedelta = timedelta(minutes=10),
    ) -> tuple["Pedido", Transicion]:
        transicion = TRANSICIONES.get((self.estado, accion))
        if transicion is None:
            raise Conflicto(
                "transicion_invalida",
                f"No se puede {accion.value} un pedido {self.estado.value}.",
                estado=self.estado.value,
            )
        if actor not in transicion.actores:
            raise NoAutorizado(
                "accion_no_permitida", f"El {actor.value} no puede {accion.value} este pedido."
            )
        if accion is Accion.APROBAR and ahora >= self.vence_en:
            raise Conflicto("pedido_vencido", "Pasaron los 30 minutos: el pedido se cancelo solo.")
        if accion is Accion.NO_ASISTIO and (
            self.llegada_en is None or ahora < self.llegada_en + espera_no_asistio
        ):
            minutos = int(espera_no_asistio.total_seconds() // 60)
            raise ReglaIncumplida(
                "espera_insuficiente",
                f"Espera al comprador al menos {minutos} minutos despues de llegar.",
            )
        nuevo = replace(
            self,
            estado=transicion.hacia,
            actualizado_en=ahora,
            llegada_en=ahora if accion is Accion.LLEGUE else self.llegada_en,
            motivo=(motivo or None) if transicion.libera_stock else self.motivo,
        )
        return nuevo, transicion
