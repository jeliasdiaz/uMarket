"""El puerto del modelo de lenguaje.

Viene de QuickDev (`ports/llm.py`, ADR-0006) con tres agregados que el plan
tecnico pide (§7): `timeout_s`, `razonamiento` y un `uso` normalizado.

Responsabilidad: definir como se pide una respuesta JSON a un modelo, sin saber
que modelo es ni quien lo sirve. Cambiar de proveedor es escribir otro adaptador
de este puerto y registrarlo en `ia/adaptadores/__init__.py`.

Lo que NO le corresponde: importar ningun SDK, ni conocer los modelos de dominio.
`complete_json` devuelve un `dict`; el parseo al dominio ocurre en la aplicacion.
Asi el JSON crudo del modelo se conserva intacto para los evals, que evaluan las
aserciones contra el crudo y contra el corregido por separado.
"""

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Protocol

from pydantic import BaseModel


class Razonamiento(StrEnum):
    """Cuanto "piensa" el modelo antes de responder. Cada adaptador lo traduce.

    En QuickDev el razonamiento sin limite se comia el presupuesto de salida:
    respuestas truncadas y 28 a 74 segundos de espera. Para interpretar una
    busqueda, NINGUNO es el punto de partida; subirlo es una hipotesis a medir.
    """

    NINGUNO = "ninguno"
    BAJO = "bajo"
    MEDIO = "medio"


@dataclass(frozen=True)
class LlmRequest:
    """Una peticion al modelo.

    `response_schema` es el modelo Pydantic que el proveedor debe hacer cumplir
    (ADR-0009 de QuickDev): la forma la garantiza el proveedor, no una frase del
    prompt.
    """

    system_prompt: str
    payload: dict[str, Any]
    response_schema: type[BaseModel] | None = None
    max_output_tokens: int = 512
    temperature: float = 0.0
    timeout_s: float = 3.0
    razonamiento: Razonamiento = Razonamiento.NINGUNO


@dataclass(frozen=True)
class UsoTokens:
    """Tokens de una llamada, con los mismos nombres para todos los proveedores."""

    entrada: int = 0
    salida: int = 0
    razonamiento: int = 0

    @property
    def total(self) -> int:
        return self.entrada + self.salida + self.razonamiento


@dataclass(frozen=True)
class LlmResponse:
    """La respuesta del modelo, mas lo que hizo falta para conseguirla.

    `attempts` no significa fallo: reintentar no es fallar (QuickDev corrigio un
    diagnostico que confundia las dos cosas, ADR-0008).
    """

    data: dict[str, Any]
    raw_text: str
    attempts: int = 1
    truncated: bool = False
    latency_s: float = 0.0
    from_cache: bool = False
    model: str = ""
    provider: str = ""
    usage: UsoTokens = field(default_factory=UsoTokens)


class LlmPort(Protocol):
    """Lo unico que el resto del sistema sabe de un modelo de lenguaje.

    Implementaciones: `gemini` (real), `fake` (replay, CI sin red) y los
    decoradores `reintentos`, `cache` y `presupuesto`, que tambien implementan
    este puerto y por eso se componen.
    """

    def complete_json(self, request: LlmRequest) -> LlmResponse:
        """Pide una respuesta JSON (un objeto en la raiz).

        Raises:
            LlmTerminalError: no tiene sentido reintentar.
            LlmRetryableError: el error es transitorio.
        """
        ...


class LlmError(RuntimeError):
    """Cualquier fallo de la capa de llamada al modelo."""


class LlmRetryableError(LlmError):
    """Transitorio: 429, 5xx, timeouts. Tiene sentido reintentar con espera."""


class LlmTerminalError(LlmError):
    """Definitivo: 400, 401, esquema rechazado, sin clave. Reintentar solo pierde tiempo."""


class LlmPresupuestoAgotado(LlmTerminalError):
    """Se supero el gasto diario configurado. Quien llama debe usar su respaldo."""
