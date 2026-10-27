"""Los adaptadores del LLM y la composicion de produccion.

Cambiar de proveedor es crear `ia/adaptadores/<proveedor>.py`, agregar UNA
linea en `PROVEEDORES` y pasar la suite de contrato del puerto
(`tests/ia/test_contrato_llm.py`). Nada fuera de `ia/` se entera.

El orden de los decoradores no es arbitrario:
  - la cache va AFUERA: un acierto no gasta presupuesto ni pasa por reintentos;
  - el presupuesto va ADENTRO de los reintentos: cuenta cada intento real.
"""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from umarket.ia.adaptadores.cache import CachingLlm
from umarket.ia.adaptadores.fake import FakeLlm
from umarket.ia.adaptadores.presupuesto import ConPresupuesto
from umarket.ia.adaptadores.reintentos import RetryingLlm
from umarket.ia.puerto import LlmPort, LlmTerminalError


@dataclass(frozen=True)
class ConfigLlm:
    """Lo que la composicion necesita saber. Lo arma `config.Settings`."""

    proveedor: str
    modelo: str
    gemini_api_key: str = ""
    replay_path: Path | None = None
    reintentos: int = 2
    tope_total_s: float = 3.0
    presupuesto_diario_usd: float = 1.0
    cache_dir: Path | None = None


def _gemini(config: ConfigLlm) -> LlmPort:
    # Import diferido: sin la clave ni el SDK, el resto del sistema arranca igual.
    from umarket.ia.adaptadores.gemini import GeminiAdapter

    return GeminiAdapter(api_key=config.gemini_api_key, model=config.modelo)


def _fake(config: ConfigLlm) -> LlmPort:
    if config.replay_path is None:
        raise LlmTerminalError(
            "LLM_PROVIDER=fake necesita LLM_REPLAY_PATH (un crudo.json de evals)."
        )
    return FakeLlm.desde_archivo(config.replay_path, model=config.modelo or "replay")


PROVEEDORES: dict[str, Callable[[ConfigLlm], LlmPort]] = {
    "gemini": _gemini,
    "fake": _fake,
}


def build_llm(config: ConfigLlm) -> LlmPort:
    """La composicion de produccion, en un solo sitio."""
    if config.proveedor not in PROVEEDORES:
        raise LlmTerminalError(
            f"Proveedor de LLM desconocido: {config.proveedor!r}. "
            f"Disponibles: {sorted(PROVEEDORES)}"
        )
    base = PROVEEDORES[config.proveedor](config)
    llm: LlmPort = RetryingLlm(
        ConPresupuesto(base, limite_usd=config.presupuesto_diario_usd),
        retries=config.reintentos,
        tope_total_s=config.tope_total_s,
    )
    if config.cache_dir is not None:
        llm = CachingLlm(llm, cache_dir=config.cache_dir, model=config.modelo)
    return llm


__all__ = [
    "PROVEEDORES",
    "CachingLlm",
    "ConPresupuesto",
    "ConfigLlm",
    "FakeLlm",
    "RetryingLlm",
    "build_llm",
]
