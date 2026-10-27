"""La suite de contrato de `LlmPort`: toda implementacion debe pasarla (sustitucion de Liskov).

Un adaptador nuevo (otro proveedor) se agrega a `IMPLEMENTACIONES` y tiene que
pasar lo mismo que los existentes. El de Gemini se prueba con un cliente doble;
el smoke contra la API real esta en `test_gemini_en_vivo.py` (marcado `llm`).
"""

from collections.abc import Callable
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import BaseModel

from umarket.ia.adaptadores.fake import FakeLlm, clave_de_payload
from umarket.ia.adaptadores.gemini import GeminiAdapter
from umarket.ia.puerto import LlmPort, LlmRequest, LlmResponse

RESPUESTA = {"es_busqueda": True, "terminos": ["empanada"]}
PETICION = LlmRequest(system_prompt="sistema", payload={"texto": "empanada"})


class _Esquema(BaseModel):
    es_busqueda: bool
    terminos: list[str]


class ClienteGeminiDoble:
    """Imita `client.models.generate_content` del SDK."""

    def __init__(self, texto: str) -> None:
        self.texto = texto
        self.llamadas: list[dict[str, Any]] = []
        self.models = SimpleNamespace(generate_content=self._generar)

    def _generar(self, **kwargs: Any) -> Any:
        self.llamadas.append(kwargs)
        return SimpleNamespace(
            text=self.texto,
            candidates=[SimpleNamespace(finish_reason="STOP")],
            usage_metadata=SimpleNamespace(
                prompt_token_count=120, candidates_token_count=30, thoughts_token_count=0
            ),
        )


def _fake() -> LlmPort:
    return FakeLlm({clave_de_payload(PETICION.payload): [RESPUESTA]})


def _gemini() -> LlmPort:
    import json

    return GeminiAdapter(
        api_key="", model="gemini-3.5-flash-lite", client=ClienteGeminiDoble(json.dumps(RESPUESTA))
    )


IMPLEMENTACIONES: dict[str, Callable[[], LlmPort]] = {"fake": _fake, "gemini": _gemini}


@pytest.fixture(params=sorted(IMPLEMENTACIONES))
def llm(request: pytest.FixtureRequest) -> LlmPort:
    return IMPLEMENTACIONES[request.param]()


def test_devuelve_un_objeto_json_en_la_raiz(llm: LlmPort) -> None:
    respuesta = llm.complete_json(PETICION)
    assert isinstance(respuesta, LlmResponse)
    assert respuesta.data == RESPUESTA


def test_conserva_el_texto_crudo(llm: LlmPort) -> None:
    respuesta = llm.complete_json(PETICION)
    assert respuesta.raw_text
    assert "empanada" in respuesta.raw_text


def test_estampa_modelo_y_proveedor(llm: LlmPort) -> None:
    respuesta = llm.complete_json(PETICION)
    assert respuesta.model
    assert respuesta.provider


def test_un_intento_y_sin_cache(llm: LlmPort) -> None:
    respuesta = llm.complete_json(PETICION)
    assert respuesta.attempts == 1
    assert respuesta.from_cache is False


def test_acepta_un_esquema_de_respuesta(llm: LlmPort) -> None:
    peticion = LlmRequest(
        system_prompt="sistema", payload=PETICION.payload, response_schema=_Esquema
    )
    assert _Esquema.model_validate(llm.complete_json(peticion).data)
