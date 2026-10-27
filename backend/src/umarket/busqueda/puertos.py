from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol
from uuid import UUID

from umarket.busqueda.aplicacion.vistas import Oferta, RegistroBusqueda
from umarket.busqueda.dominio.contrato import ConsultaInterpretada, EntradaInterprete
from umarket.campus import Franja, PuntoEncuentro
from umarket.ia.traza import Traza


class ErrorInterprete(RuntimeError):
    """El interprete no pudo producir una consulta valida. Quien llama usa el respaldo."""


@dataclass(frozen=True)
class Interpretacion:
    consulta: ConsultaInterpretada
    origen: str


class InterpreteConsulta(Protocol):
    """Punto de extension: palabras clave, Gemini, embeddings... (PLAN-TECNICO.md §3)."""

    @property
    def nombre(self) -> str: ...

    def interpretar(self, entrada: EntradaInterprete, traza: Traza) -> Interpretacion:
        """Raises: ErrorInterprete (o un LlmError) si no pudo."""
        ...


@dataclass(frozen=True)
class ContextoCampusBusqueda:
    campus_id: str
    zona_horaria: str
    fecha: date
    puntos: list[PuntoEncuentro]
    franjas_abiertas: list[Franja]
    productos_hoy: list[str]


class LectorContextoBusqueda(Protocol):
    def contexto(self, campus_id: str, ahora: datetime) -> ContextoCampusBusqueda: ...


class BuscadorOfertas(Protocol):
    def buscar(
        self,
        consulta: ConsultaInterpretada,
        campus_id: str,
        fecha: date,
        ahora: datetime,
        limite: int,
    ) -> list[Oferta]: ...


class RegistroBusquedas(Protocol):
    def registrar(self, registro: RegistroBusqueda, traza: Traza) -> None: ...

    def texto_de(self, busqueda_id: UUID) -> str | None: ...

    def registrar_clic(
        self,
        busqueda_id: UUID,
        tienda_id: UUID,
        producto_id: UUID | None,
        posicion: int,
        en: datetime,
    ) -> None: ...
