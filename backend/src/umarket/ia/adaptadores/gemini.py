"""El adaptador real: Gemini (de QuickDev, con timeout y razonamiento).

Responsabilidad: traducir un `LlmRequest` a una llamada del SDK de Google, la
respuesta a un `LlmResponse`, y los errores del proveedor a la jerarquia del
puerto. Es el UNICO archivo del repo que importa `google.genai`; import-linter
lo comprueba (regla 4).

Lo que NO le corresponde: reintentar, cachear, controlar el gasto ni saber que
es una `ConsultaInterpretada`.

Lo que cambia entre proveedores vive aqui y en ningun otro sitio:
  - el esquema: Gemini rechaza `additionalProperties` (ADR-0014 de QuickDev:
    con el, el 100% de las llamadas daba 400 y ningun test lo vio);
  - la clasificacion de errores en reintentable o terminal;
  - el razonamiento: los modelos 2.x usan `thinking_budget`, los 3.x
    `thinking_level`;
  - la lectura del uso de tokens.
"""

import json
import re
import time
from typing import Any

from google import genai
from google.genai import errors as genai_errors
from google.genai import types
from pydantic import BaseModel

from umarket.ia.puerto import (
    LlmRequest,
    LlmResponse,
    LlmRetryableError,
    LlmTerminalError,
    Razonamiento,
    UsoTokens,
)

CODIGOS_REINTENTABLES = frozenset({408, 409, 429})
_VALLA_MARKDOWN = re.compile(r"^\x60{3}(?:json)?\s*|\s*\x60{3}$")

_PRESUPUESTO_2X = {Razonamiento.NINGUNO: 0, Razonamiento.BAJO: 512, Razonamiento.MEDIO: 2048}
_NIVEL_3X = {
    Razonamiento.NINGUNO: types.ThinkingLevel.MINIMAL,
    Razonamiento.BAJO: types.ThinkingLevel.LOW,
    Razonamiento.MEDIO: types.ThinkingLevel.MEDIUM,
}


class GeminiAdapter:
    def __init__(self, api_key: str, model: str, client: Any | None = None) -> None:
        """
        Args:
            client: un cliente ya construido; se inyecta en los tests.

        Raises:
            LlmTerminalError: no hay clave. Falla al construir, no a mitad de una
                corrida que ya gasto llamadas.
        """
        self.model = model
        if client is not None:
            self.client = client
            return
        if not api_key:
            raise LlmTerminalError(
                "Falta GEMINI_API_KEY. Para correr sin clave usa LLM_PROVIDER=fake, que "
                "reproduce respuestas grabadas."
            )
        self.client = genai.Client(api_key=api_key)

    def complete_json(self, request: LlmRequest) -> LlmResponse:
        """Una llamada, un intento. Los reintentos son de `RetryingLlm`."""
        inicio = time.perf_counter()
        try:
            respuesta = self.client.models.generate_content(
                model=self.model,
                contents=json.dumps(request.payload, ensure_ascii=False),
                config=self._config(request),
            )
        except Exception as exc:
            raise _clasificar(exc) from exc

        latencia = time.perf_counter() - inicio
        truncado = _truncado(respuesta)
        texto = _VALLA_MARKDOWN.sub("", (respuesta.text or "").strip())
        try:
            datos = json.loads(texto)
        except json.JSONDecodeError as exc:
            if truncado:
                raise LlmTerminalError(
                    f"Respuesta truncada por max_output_tokens: {exc}. Reintentar a "
                    f"temperatura 0 da el mismo corte; sube max_output_tokens."
                ) from exc
            raise LlmRetryableError(
                f"JSON invalido del modelo: {exc}. Muestra: {texto[:200]!r}"
            ) from exc
        if not isinstance(datos, dict):
            raise LlmTerminalError(
                f"El modelo devolvio un {type(datos).__name__}, no un objeto JSON."
            )

        return LlmResponse(
            data=datos,
            raw_text=texto,
            truncated=truncado,
            latency_s=latencia,
            model=self.model,
            provider="gemini",
            usage=_uso(respuesta),
        )

    def _config(self, request: LlmRequest) -> types.GenerateContentConfig:
        return types.GenerateContentConfig(
            system_instruction=request.system_prompt,
            temperature=request.temperature,
            max_output_tokens=request.max_output_tokens,
            response_mime_type="application/json",
            response_schema=esquema_para_gemini(request.response_schema),
            thinking_config=self._razonamiento(request.razonamiento),
            # El SDK mide el timeout en milisegundos. QuickDev no tenia timeout:
            # un proveedor colgado dejaba el spinner sin fin.
            http_options=types.HttpOptions(timeout=int(request.timeout_s * 1000)),
        )

    def _razonamiento(self, nivel: Razonamiento) -> types.ThinkingConfig:
        if self.model.removeprefix("models/").startswith("gemini-2"):
            return types.ThinkingConfig(thinking_budget=_PRESUPUESTO_2X[nivel])
        return types.ThinkingConfig(thinking_level=_NIVEL_3X[nivel])


def esquema_para_gemini(modelo: type[BaseModel] | None) -> dict[str, Any] | None:
    """El JSON Schema del modelo, sin `additionalProperties` (ADR-0014 de QuickDev).

    El dominio conserva `extra="forbid"`: un campo extra en la respuesta sigue
    siendo un error al parsear en la aplicacion. Solo cambia lo que se envia.
    """
    if modelo is None:
        return None
    limpio = _sin_additional_properties(modelo.model_json_schema())
    assert isinstance(limpio, dict)
    return limpio  # pyright: ignore[reportUnknownVariableType]


def _sin_additional_properties(nodo: object) -> object:
    if isinstance(nodo, dict):
        return {
            clave: _sin_additional_properties(valor)
            for clave, valor in nodo.items()  # pyright: ignore[reportUnknownVariableType]
            if clave != "additionalProperties"
        }
    if isinstance(nodo, list):
        return [_sin_additional_properties(v) for v in nodo]  # pyright: ignore[reportUnknownVariableType]
    return nodo


def _truncado(respuesta: Any) -> bool:
    try:
        return "MAX_TOKENS" in str(respuesta.candidates[0].finish_reason)
    except (AttributeError, IndexError, TypeError):
        return False


def _uso(respuesta: Any) -> UsoTokens:
    meta = getattr(respuesta, "usage_metadata", None)
    if meta is None:
        return UsoTokens()

    def entero(nombre: str) -> int:
        valor = getattr(meta, nombre, None)
        return valor if isinstance(valor, int) else 0

    return UsoTokens(
        entrada=entero("prompt_token_count"),
        salida=entero("candidates_token_count"),
        razonamiento=entero("thoughts_token_count"),
    )


def _clasificar(exc: Exception) -> LlmRetryableError | LlmTerminalError:
    """Lo que no se reconoce es TERMINAL: lo desconocido es mas probablemente un bug nuestro."""
    if isinstance(exc, genai_errors.ServerError):
        return LlmRetryableError(f"5xx del proveedor: {_mensaje(exc)}")
    if isinstance(exc, genai_errors.ClientError):
        codigo = getattr(exc, "code", None)
        if codigo in CODIGOS_REINTENTABLES:
            return LlmRetryableError(f"{codigo} del proveedor: {_mensaje(exc)}")
        return LlmTerminalError(f"{codigo} del proveedor: {_mensaje(exc)}")
    if isinstance(exc, TimeoutError | ConnectionError):
        return LlmRetryableError(f"fallo de red: {_mensaje(exc)}")
    if type(exc).__module__.split(".")[0] in {"httpx", "httpcore"}:
        return LlmRetryableError(f"fallo de transporte: {type(exc).__name__}: {_mensaje(exc)}")
    return LlmTerminalError(f"{type(exc).__name__}: {_mensaje(exc)}")


def _mensaje(exc: Exception) -> str:
    return str(getattr(exc, "message", None) or exc)[:300]
