"""Eventos de dominio.

Responsabilidad: describir que paso ("pedido.aprobado") con datos serializables,
para que otros modulos reaccionen sin que el modulo que lo emite los conozca.

Lo que NO le corresponde: entregarlos. Los casos de uso los dejan en el buzon
(outbox) dentro de su misma transaccion y el worker los despacha. Agregar una
reaccion es registrar un manejador; el emisor no cambia (PLAN-TECNICO.md §2.6).
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime

type Json = str | int | float | bool | list[Json] | Mapping[str, Json] | None


@dataclass(frozen=True)
class Evento:
    """Algo que ya ocurrio. `tipo` es estable: es la clave de los manejadores."""

    tipo: str
    datos: Mapping[str, Json]
    ocurrido_en: datetime
