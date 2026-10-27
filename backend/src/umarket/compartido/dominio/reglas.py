"""El contrato de una regla de validacion, generico.

Viene de QuickDev (`domain/rules/base.py`, ADR-0003): una regla por clase, y una
version del validador es una composicion distinta de reglas, no un `if` dentro
de una funcion. Aqui es generico sobre el sujeto que se revisa (un pedido, una
consulta interpretada) y el contexto contra el que se revisa (catalogo, campus).

Detectar y corregir estan separados (ADR-0004 de QuickDev): `Validador` solo
detecta; que se hace con cada hallazgo lo decide la politica de cada modulo.
"""

from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol


class Severidad(StrEnum):
    """CRITICA: no puede seguir asi. ADVERTENCIA: defendible pero sospechoso."""

    CRITICA = "critica"
    ADVERTENCIA = "advertencia"


@dataclass(frozen=True)
class Hallazgo:
    """Una regla que no se cumplio. Es un dato, no un string formateado.

    `regla_id` es estable: los tests y los evals preguntan por el, no por
    fragmentos del mensaje, que puede mejorar de redaccion sin romper nada.
    """

    regla_id: str
    campo: str
    mensaje: str
    severidad: Severidad = Severidad.CRITICA


class Regla[S, C](Protocol):
    """Una comprobacion determinista: sin modelo, sin red, sin I/O."""

    @property
    def id(self) -> str: ...

    def revisar(self, sujeto: S, contexto: C, /) -> Iterable[Hallazgo]:
        """Los hallazgos de esta regla. Vacio si se cumple.

        Parametros solo posicionales: cada regla los nombra como le sea mas claro.
        """
        ...


@dataclass(frozen=True)
class ConjuntoReglas[S, C]:
    """Reglas con nombre de version. La version se estampa en trazas y evals.

    Un conjunto ya medido no se edita: una regla nueva va en una version nueva.
    """

    version: str
    reglas: tuple[Regla[S, C], ...]

    def __iter__(self) -> Iterator[Regla[S, C]]:
        return iter(self.reglas)

    def __len__(self) -> int:
        return len(self.reglas)


class Validador[S, C]:
    """Corre un conjunto de reglas. Solo detecta: no modifica nada."""

    def __init__(self, conjunto: ConjuntoReglas[S, C]) -> None:
        self.conjunto = conjunto

    @property
    def version(self) -> str:
        return self.conjunto.version

    def validar(self, sujeto: S, contexto: C) -> list[Hallazgo]:
        hallazgos: list[Hallazgo] = []
        for regla in self.conjunto:
            hallazgos.extend(regla.revisar(sujeto, contexto))
        return hallazgos
