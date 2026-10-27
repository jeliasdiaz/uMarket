"""El adaptador de Gemini sin red: esquema, razonamiento, timeout, errores y uso."""

import json
from types import SimpleNamespace
from typing import Any

import pytest
from google.genai import errors as genai_errors
from google.genai import types
from pydantic import BaseModel, ConfigDict

from tests.ia.test_contrato_llm import ClienteGeminiDoble
from umarket.ia.adaptadores.gemini import GeminiAdapter, _clasificar, esquema_para_gemini
from umarket.ia.puerto import LlmRequest, LlmRetryableError, LlmTerminalError, Razonamiento


class _Estricto(BaseModel):
    model_config = ConfigDict(extra="forbid")
    a: int
    hijos: list["_Estricto"] = []


def _config_enviada(cliente: ClienteGeminiDoble) -> types.GenerateContentConfig:
    return cliente.llamadas[-1]["config"]


def test_el_esquema_enviado_no_tiene_additional_properties() -> None:
    """ADR-0014 de QuickDev: con additionalProperties, Gemini respondia 400 siempre."""
    esquema = esquema_para_gemini(_Estricto)
    assert "additionalProperties" not in json.dumps(esquema)
    assert "additionalProperties" in json.dumps(_Estricto.model_json_schema())


def test_sin_clave_falla_al_construir() -> None:
    with pytest.raises(LlmTerminalError, match="GEMINI_API_KEY"):
        GeminiAdapter(api_key="", model="gemini-3.5-flash-lite")


@pytest.mark.parametrize(
    ("modelo", "nivel", "campo", "esperado"),
    [
        (
            "gemini-3.5-flash-lite",
            Razonamiento.NINGUNO,
            "thinking_level",
            types.ThinkingLevel.MINIMAL,
        ),
        ("gemini-3.5-flash-lite", Razonamiento.MEDIO, "thinking_level", types.ThinkingLevel.MEDIUM),
        ("gemini-2.5-flash-lite", Razonamiento.NINGUNO, "thinking_budget", 0),
        ("gemini-2.5-flash", Razonamiento.BAJO, "thinking_budget", 512),
    ],
)
def test_traduce_el_razonamiento_segun_la_familia(
    modelo: str, nivel: Razonamiento, campo: str, esperado: Any
) -> None:
    cliente = ClienteGeminiDoble('{"ok": true}')
    GeminiAdapter(api_key="", model=modelo, client=cliente).complete_json(
        LlmRequest(system_prompt="s", payload={}, razonamiento=nivel)
    )
    thinking = _config_enviada(cliente).thinking_config
    assert thinking is not None
    assert getattr(thinking, campo) == esperado


def test_envia_el_timeout_en_milisegundos() -> None:
    cliente = ClienteGeminiDoble('{"ok": true}')
    GeminiAdapter(api_key="", model="gemini-3.5-flash-lite", client=cliente).complete_json(
        LlmRequest(system_prompt="s", payload={}, timeout_s=2.5)
    )
    opciones = _config_enviada(cliente).http_options
    assert opciones is not None
    assert opciones.timeout == 2500


def test_lee_el_uso_de_tokens() -> None:
    cliente = ClienteGeminiDoble('{"ok": true}')
    respuesta = GeminiAdapter(
        api_key="", model="gemini-3.5-flash-lite", client=cliente
    ).complete_json(LlmRequest(system_prompt="s", payload={}))
    assert (respuesta.usage.entrada, respuesta.usage.salida) == (120, 30)


def test_quita_la_valla_de_markdown() -> None:
    cliente = ClienteGeminiDoble('```json\n{"ok": true}\n```')
    respuesta = GeminiAdapter(api_key="", model="m", client=cliente).complete_json(
        LlmRequest(system_prompt="s", payload={})
    )
    assert respuesta.data == {"ok": True}


def test_una_lista_en_la_raiz_es_terminal() -> None:
    cliente = ClienteGeminiDoble("[1, 2]")
    with pytest.raises(LlmTerminalError):
        GeminiAdapter(api_key="", model="m", client=cliente).complete_json(
            LlmRequest(system_prompt="s", payload={})
        )


def test_json_truncado_es_terminal_y_roto_sin_truncar_es_reintentable() -> None:
    truncado = ClienteGeminiDoble('{"ok": ')
    truncado.models = SimpleNamespace(
        generate_content=lambda **_: SimpleNamespace(
            text='{"ok": ',
            candidates=[SimpleNamespace(finish_reason="MAX_TOKENS")],
            usage_metadata=None,
        )
    )
    with pytest.raises(LlmTerminalError, match="truncada"):
        GeminiAdapter(api_key="", model="m", client=truncado).complete_json(
            LlmRequest(system_prompt="s", payload={})
        )
    with pytest.raises(LlmRetryableError):
        GeminiAdapter(api_key="", model="m", client=ClienteGeminiDoble('{"ok": ')).complete_json(
            LlmRequest(system_prompt="s", payload={})
        )


@pytest.mark.parametrize(
    ("excepcion", "esperada"),
    [
        (genai_errors.ServerError(503, {"error": {"message": "caido"}}), LlmRetryableError),
        (genai_errors.ClientError(429, {"error": {"message": "cuota"}}), LlmRetryableError),
        (genai_errors.ClientError(400, {"error": {"message": "esquema"}}), LlmTerminalError),
        (genai_errors.ClientError(401, {"error": {"message": "clave"}}), LlmTerminalError),
        (TimeoutError("lento"), LlmRetryableError),
        (KeyError("bug nuestro"), LlmTerminalError),
    ],
)
def test_clasifica_los_errores(excepcion: Exception, esperada: type[Exception]) -> None:
    assert isinstance(_clasificar(excepcion), esperada)
