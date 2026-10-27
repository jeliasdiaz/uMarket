"""La maquina de estados del pedido, como TABLA declarativa (PLAN-TECNICO.md §5.1).

Agregar un estado o una accion es agregar filas aqui (y la migracion de la
restriccion CHECK), sin tocar los casos de uso: `ActuarSobrePedido` solo consulta
la tabla. Es el punto de extension de "estados del pedido" del plan (§3).
"""

from dataclasses import dataclass
from enum import StrEnum


class Estado(StrEnum):
    PENDIENTE = "pendiente"
    APROBADO = "aprobado"
    RECHAZADO = "rechazado"
    VENCIDO = "vencido"
    CANCELADO = "cancelado"
    EN_PUNTO = "en_punto"
    ENTREGADO = "entregado"
    NO_ASISTIO = "no_asistio"


class Accion(StrEnum):
    APROBAR = "aprobar"
    RECHAZAR = "rechazar"
    VENCER = "vencer"
    CANCELAR = "cancelar"
    LLEGUE = "llegue"
    ENTREGAR = "entregar"
    NO_ASISTIO = "no_asistio"


class Actor(StrEnum):
    COMPRADOR = "comprador"
    VENDEDOR = "vendedor"
    SISTEMA = "sistema"


@dataclass(frozen=True)
class Transicion:
    hacia: Estado
    actores: frozenset[Actor]
    libera_stock: bool
    evento: str


def _t(hacia: Estado, *actores: Actor, libera: bool = False, evento: str) -> Transicion:
    return Transicion(hacia, frozenset(actores), libera, evento)


TRANSICIONES: dict[tuple[Estado, Accion], Transicion] = {
    (Estado.PENDIENTE, Accion.APROBAR): _t(
        Estado.APROBADO, Actor.VENDEDOR, evento="pedido.aprobado"
    ),
    (Estado.PENDIENTE, Accion.RECHAZAR): _t(
        Estado.RECHAZADO, Actor.VENDEDOR, libera=True, evento="pedido.rechazado"
    ),
    (Estado.PENDIENTE, Accion.VENCER): _t(
        Estado.VENCIDO, Actor.SISTEMA, libera=True, evento="pedido.vencido"
    ),
    (Estado.PENDIENTE, Accion.CANCELAR): _t(
        Estado.CANCELADO, Actor.COMPRADOR, libera=True, evento="pedido.cancelado"
    ),
    (Estado.APROBADO, Accion.CANCELAR): _t(
        Estado.CANCELADO, Actor.COMPRADOR, Actor.VENDEDOR, libera=True, evento="pedido.cancelado"
    ),
    (Estado.APROBADO, Accion.LLEGUE): _t(
        Estado.EN_PUNTO, Actor.VENDEDOR, evento="pedido.vendedor_llego"
    ),
    (Estado.EN_PUNTO, Accion.ENTREGAR): _t(
        Estado.ENTREGADO, Actor.VENDEDOR, evento="pedido.entregado"
    ),
    (Estado.EN_PUNTO, Accion.NO_ASISTIO): _t(
        Estado.NO_ASISTIO, Actor.VENDEDOR, libera=True, evento="pedido.no_asistio"
    ),
}

ABIERTOS: frozenset[Estado] = frozenset({Estado.PENDIENTE, Estado.APROBADO, Estado.EN_PUNTO})
FINALES: frozenset[Estado] = frozenset(set(Estado) - ABIERTOS)


def acciones_posibles(estado: Estado, actor: Actor) -> list[Accion]:
    """Lo que ese actor puede hacer ahora. La UI muestra solo estos botones."""
    return [a for (e, a), t in TRANSICIONES.items() if e == estado and actor in t.actores]
