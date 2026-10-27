"""El interprete con modelo de lenguaje. No sabe que proveedor hay debajo: usa `LlmPort`.

Una sola llamada por busqueda, con salida JSON forzada por el esquema del contrato
(`response_schema`), razonamiento al minimo y tiempo limite. Si el modelo devuelve
algo que no valida contra `ConsultaInterpretada` (un campo inventado, un enum que
no existe), lanza `ErrorInterprete` y la busqueda sigue con el respaldo.
"""

import time

from pydantic import ValidationError

from umarket.busqueda.dominio.contrato import ConsultaInterpretada, EntradaInterprete
from umarket.busqueda.puertos import ErrorInterprete, Interpretacion
from umarket.ia.prompts import RegistroPrompts
from umarket.ia.puerto import LlmPort, LlmRequest, Razonamiento
from umarket.ia.traza import Traza

COMPONENTE = "busqueda"


class InterpreteLlm:
    nombre = "intencion"

    def __init__(
        self,
        llm: LlmPort,
        prompts: RegistroPrompts,
        version: str,
        timeout_s: float = 3.0,
        max_output_tokens: int = 512,
    ) -> None:
        self._llm = llm
        self._sistema = prompts.texto(COMPONENTE, version)
        self._version = version
        self._timeout_s = timeout_s
        self._max_output_tokens = max_output_tokens

    def peticion(self, entrada: EntradaInterprete) -> LlmRequest:
        """La peticion exacta. El runner de evals la usa para grabar y reproducir."""
        return LlmRequest(
            system_prompt=self._sistema,
            payload=entrada.model_dump(mode="json"),
            response_schema=ConsultaInterpretada,
            max_output_tokens=self._max_output_tokens,
            temperature=0.0,
            timeout_s=self._timeout_s,
            razonamiento=Razonamiento.NINGUNO,
        )

    def interpretar(self, entrada: EntradaInterprete, traza: Traza) -> Interpretacion:
        inicio = time.perf_counter()
        traza.prompt_version = self._version
        respuesta = self._llm.complete_json(self.peticion(entrada))
        traza.registrar_llamada(respuesta)
        try:
            consulta = ConsultaInterpretada.model_validate(respuesta.data)
        except ValidationError as exc:
            traza.paso(
                "interpretar",
                "el modelo devolvio una forma invalida",
                time.perf_counter() - inicio,
                crudo=respuesta.data,
            )
            raise ErrorInterprete(
                f"Salida invalida del modelo: {exc.error_count()} errores"
            ) from exc
        traza.paso(
            "interpretar",
            f"{respuesta.model} en {respuesta.latency_s:.2f}s, {respuesta.attempts} intento(s)",
            time.perf_counter() - inicio,
            interprete=self.nombre,
            crudo=respuesta.data,
            tokens=respuesta.usage.total,
            from_cache=respuesta.from_cache,
        )
        return Interpretacion(consulta, self.nombre)
