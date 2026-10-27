"""Cache en disco, como decorador (de QuickDev).

Responsabilidad: no volver a pagar por una respuesta que ya tenemos.

Para lo que NO sirve: medir. Un eval manda la misma peticion n veces; con cache,
la corrida 1 llama al modelo y las otras n-1 salen del disco. n pedidas, una
muestra. Por eso los evals en vivo la apagan (ADR-0012 de QuickDev).

La clave incluye modelo, prompt, payload, temperatura, razonamiento y esquema:
todo lo que puede cambiar la respuesta. Lo que no entra es el codigo del
adaptador: si cambia como se parsea, hay que borrar `.cache/` a mano.
"""

import hashlib
import json
from dataclasses import asdict, replace
from pathlib import Path

from umarket.ia.puerto import LlmPort, LlmRequest, LlmResponse, UsoTokens

VERSION_DE_CACHE = "v1"


class CachingLlm:
    def __init__(
        self, inner: LlmPort, cache_dir: Path, model: str = "", enabled: bool = True
    ) -> None:
        self.inner = inner
        self.cache_dir = Path(cache_dir)
        self.model = model
        self.enabled = enabled

    def complete_json(self, request: LlmRequest) -> LlmResponse:
        if not self.enabled:
            return self.inner.complete_json(request)
        archivo = self.ruta_de(request)
        guardada = self._leer(archivo)
        if guardada is not None:
            return guardada
        respuesta = self.inner.complete_json(request)
        self._escribir(archivo, respuesta)
        return respuesta

    def key(self, request: LlmRequest) -> str:
        material = json.dumps(
            {
                "v": VERSION_DE_CACHE,
                "model": self.model,
                "system_prompt": request.system_prompt,
                "payload": request.payload,
                "temperature": request.temperature,
                "max_output_tokens": request.max_output_tokens,
                "razonamiento": request.razonamiento.value,
                "schema": getattr(request.response_schema, "__name__", None),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    def ruta_de(self, request: LlmRequest) -> Path:
        subdir = self.model.replace("/", "_") or "sin-modelo"
        return self.cache_dir / subdir / f"{self.key(request)}.json"

    def _leer(self, archivo: Path) -> LlmResponse | None:
        """La entrada guardada, o None si no existe o esta corrupta: es un cache, no una fuente."""
        if not archivo.exists():
            return None
        try:
            datos = json.loads(archivo.read_text(encoding="utf-8"))["respuesta"]
            datos["usage"] = UsoTokens(**datos.get("usage", {}))
            respuesta = LlmResponse(**datos)
        except (OSError, json.JSONDecodeError, KeyError, TypeError):
            return None
        return replace(respuesta, from_cache=True)

    def _escribir(self, archivo: Path, respuesta: LlmResponse) -> None:
        archivo.parent.mkdir(parents=True, exist_ok=True)
        contenido = {"respuesta": {**asdict(respuesta), "from_cache": False}}
        archivo.write_text(json.dumps(contenido, ensure_ascii=False, indent=2), encoding="utf-8")
