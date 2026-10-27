"""Calificaciones, metricas y la politica de ranking.

Nada de esto es IA, a proposito (PDF, "Lo que no es IA"): el ranking es una
formula, el porcentaje cumplido es un conteo y la reputacion del comprador es un
conteo de inasistencias. Saber explicar por que suma tanto como la busqueda.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from umarket.compartido.dominio.errores import ReglaIncumplida

LARGO_COMENTARIO = 280


@dataclass(frozen=True)
class Calificacion:
    id: UUID
    pedido_id: UUID
    tienda_id: UUID
    comprador_id: UUID
    estrellas: int
    comentario: str
    creada_en: datetime

    def __post_init__(self) -> None:
        if not 1 <= self.estrellas <= 5:
            raise ReglaIncumplida("estrellas_invalidas", "La calificacion va de 1 a 5 estrellas.")
        object.__setattr__(self, "comentario", " ".join(self.comentario.split())[:LARGO_COMENTARIO])


@dataclass(frozen=True)
class Metricas:
    """Conteos de una tienda. Se RECALCULAN desde las tablas de origen (idempotente)."""

    resenas: int = 0
    suma_estrellas: int = 0
    entregas: int = 0
    vencidos: int = 0
    cancelados_por_vendedor: int = 0

    @property
    def promedio(self) -> float | None:
        return round(self.suma_estrellas / self.resenas, 2) if self.resenas else None

    @property
    def porcentaje_cumplido(self) -> float | None:
        """Entregados sobre lo que el vendedor debia atender: entregados, vencidos sin
        respuesta y cancelados por el. Las inasistencias del comprador no cuentan contra el."""
        atendibles = self.entregas + self.vencidos + self.cancelados_por_vendedor
        return round(100 * self.entregas / atendibles, 1) if atendibles else None


class PoliticaRanking(Protocol):
    """Punto de extension: una formula nueva es una clase nueva y `RANKING_VERSION`."""

    @property
    def version(self) -> str: ...

    def rankeable(self, m: Metricas) -> bool: ...

    def clave(self, m: Metricas) -> tuple[float, ...]:
        """Clave de orden ascendente: lo primero en la lista va primero en la pagina."""
        ...


@dataclass(frozen=True)
class RankingV1:
    """Con 5 resenas o mas se ordena por promedio; sin ellas, despues, por entregas.

    El minimo evita que una tienda con una sola resena de 5 estrellas (quizas de
    un amigo) quede primera. Lo patrocinado, cuando exista, va SEPARADO de esta
    lista: el ranking no se compra.
    """

    minimo_resenas: int = 5
    version: str = "ranking-v1"

    def rankeable(self, m: Metricas) -> bool:
        return m.resenas >= self.minimo_resenas

    def clave(self, m: Metricas) -> tuple[float, ...]:
        if self.rankeable(m) and m.promedio is not None:
            return (0, -m.promedio, -m.resenas)
        return (1, -m.entregas, 0)


RANKINGS: dict[str, type[RankingV1]] = {"ranking-v1": RankingV1}


def politica_ranking(version: str, minimo_resenas: int) -> PoliticaRanking:
    if version not in RANKINGS:
        raise KeyError(f"No existe el ranking '{version}'. Disponibles: {sorted(RANKINGS)}")
    return RANKINGS[version](minimo_resenas=minimo_resenas)
