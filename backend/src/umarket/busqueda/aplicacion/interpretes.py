"""Interpretes que no dependen de un proveedor: palabras clave y el decorador de respaldo.

El interprete con LLM vive en `adaptadores/interprete_llm.py`: necesita leer el
prompt de un archivo, y eso es infraestructura.
"""

import time

from umarket.busqueda.dominio.contrato import EntradaInterprete
from umarket.busqueda.dominio.palabras import interpretar_por_palabras
from umarket.busqueda.puertos import ErrorInterprete, Interpretacion, InterpreteConsulta
from umarket.ia.puerto import LlmError
from umarket.ia.traza import Traza


class InterpretePorPalabras:
    nombre = "palabras"

    def interpretar(self, entrada: EntradaInterprete, traza: Traza) -> Interpretacion:
        inicio = time.perf_counter()
        consulta = interpretar_por_palabras(entrada)
        traza.paso(
            "interpretar",
            "palabras clave y parsers deterministas",
            time.perf_counter() - inicio,
            interprete=self.nombre,
        )
        return Interpretacion(consulta, self.nombre)


class InterpreteConRespaldo:
    """Si el principal falla, tarda o se agota el presupuesto, responde el respaldo.

    El comprador nunca se queda sin resultados por culpa del modelo. La traza dice
    por que se uso el respaldo, y eso cuenta en los evals como "% de respaldo".
    """

    def __init__(self, principal: InterpreteConsulta, respaldo: InterpreteConsulta) -> None:
        self._principal = principal
        self._respaldo = respaldo

    @property
    def nombre(self) -> str:
        return self._principal.nombre

    def interpretar(self, entrada: EntradaInterprete, traza: Traza) -> Interpretacion:
        try:
            return self._principal.interpretar(entrada, traza)
        except (ErrorInterprete, LlmError) as exc:
            traza.paso(
                "respaldo",
                f"{self._principal.nombre} fallo: {type(exc).__name__}",
                error=str(exc)[:300],
            )
            return self._respaldo.interpretar(entrada, traza)
