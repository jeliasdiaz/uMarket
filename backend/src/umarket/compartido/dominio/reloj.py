"""El tiempo, como puerto.

Responsabilidad: que ninguna regla llame a `datetime.now()` por su cuenta. El
vencimiento a los 30 minutos, las franjas que ya pasaron y la expiracion de los
codigos de acceso dependen de la hora; con un reloj inyectado, los tests no
esperan 30 minutos, mueven el reloj.
"""

from datetime import UTC, datetime, timedelta
from typing import Protocol


class Reloj(Protocol):
    def ahora(self) -> datetime:
        """El instante actual, siempre con zona horaria (UTC)."""
        ...


class RelojSistema:
    """El reloj real."""

    def ahora(self) -> datetime:
        return datetime.now(UTC)


class RelojFijo:
    """Un reloj que solo avanza cuando se le pide. Para tests y evals."""

    def __init__(self, instante: datetime) -> None:
        if instante.tzinfo is None:
            raise ValueError("RelojFijo necesita un instante con zona horaria.")
        self._instante = instante

    def ahora(self) -> datetime:
        return self._instante

    def avanzar(self, delta: timedelta) -> None:
        self._instante += delta
