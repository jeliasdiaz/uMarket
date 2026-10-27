"""El adaptador que no llama a nadie: reproduce respuestas grabadas (de QuickDev).

Responsabilidad: ante la misma entrada, devolver exactamente el JSON que el
modelo devolvio el dia que se midio. Con el, el pipeline completo corre en CI
sin red, sin clave y sin cuota.

Lo que NO le corresponde: inventar respuestas. Si le piden algo que no tiene
grabado, falla ruidosamente: un replay que se encoge en silencio produce tasas
que se leen igual de bien y no significan lo mismo.

La clave es el JSON canonico del payload (`sort_keys`). El runner de evals usa
la misma funcion para grabar y el adaptador para buscar: asi una corrida medida
hoy se reproduce manana.
"""

import json
from pathlib import Path
from typing import Any

from umarket.ia.puerto import LlmRequest, LlmResponse, LlmTerminalError, UsoTokens


class SinRespuestaGrabada(LlmTerminalError):
    """Se pidio una respuesta que no esta grabada, o ya se consumieron todas."""


def clave_de_payload(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


class FakeLlm:
    """Cada clave guarda la LISTA de corridas en orden; cada llamada consume la siguiente.

    Asi n llamadas reproducen las n corridas medidas, con su variabilidad.
    """

    def __init__(self, respuestas: dict[str, list[dict[str, Any]]], model: str = "replay") -> None:
        self.respuestas = respuestas
        self.model = model
        self._consumidas: dict[str, int] = {}

    @classmethod
    def desde_archivo(cls, archivo: Path, model: str = "replay") -> "FakeLlm":
        """Carga un `crudo.json` de evals.

        Formato: `{"<id>_run<i>": {"payload": ..., "output_crudo": ...}}`.
        """
        crudo = json.loads(Path(archivo).read_text(encoding="utf-8"))
        respuestas: dict[str, list[dict[str, Any]]] = {}
        for _clave, registro in sorted(crudo.items(), key=lambda kv: _orden_de_corrida(kv[0])):
            payload = registro.get("payload")
            salida = registro.get("output_crudo")
            if payload is None or salida is None:
                continue
            respuestas.setdefault(clave_de_payload(payload), []).append(salida)
        if not respuestas:
            raise SinRespuestaGrabada(
                f"{archivo} no tiene ninguna corrida con payload y output_crudo."
            )
        return cls(respuestas, model=model)

    @classmethod
    def con_respuesta_fija(cls, salida: dict[str, Any], model: str = "fake") -> "FakeLlm":
        """Un fake que responde siempre lo mismo, para tests de aplicacion."""
        return _FakeFijo(salida, model)

    def complete_json(self, request: LlmRequest) -> LlmResponse:
        clave = clave_de_payload(request.payload)
        grabadas = self.respuestas.get(clave)
        if grabadas is None:
            raise SinRespuestaGrabada(
                f"No hay corrida grabada para este payload ({len(self.respuestas)} disponibles). "
                f"Empieza por: {clave[:100]!r}"
            )
        i = self._consumidas.get(clave, 0)
        if i >= len(grabadas):
            raise SinRespuestaGrabada(
                f"Se pidieron {i + 1} corridas pero solo hay {len(grabadas)} grabadas. "
                f"En replay, n no puede superar las corridas medidas."
            )
        self._consumidas[clave] = i + 1
        salida = grabadas[i]
        return LlmResponse(
            data=salida,
            raw_text=json.dumps(salida, ensure_ascii=False),
            model=self.model,
            provider="fake",
        )

    def reset(self) -> None:
        self._consumidas.clear()


class _FakeFijo(FakeLlm):
    def __init__(self, salida: dict[str, Any], model: str) -> None:
        super().__init__({}, model=model)
        self.salida = salida
        self.llamadas: list[LlmRequest] = []

    def complete_json(self, request: LlmRequest) -> LlmResponse:
        self.llamadas.append(request)
        return LlmResponse(
            data=self.salida,
            raw_text=json.dumps(self.salida, ensure_ascii=False),
            model=self.model,
            provider="fake",
            usage=UsoTokens(entrada=100, salida=50),
        )


def _orden_de_corrida(clave: str) -> tuple[str, int]:
    """`caso_run2` antes que `caso_run10`, que alfabeticamente van al reves."""
    caso, _, corrida = clave.rpartition("_run")
    if not caso or not corrida.isdigit():
        return (clave, 0)
    return (caso, int(corrida))
