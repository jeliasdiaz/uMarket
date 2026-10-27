"""Reintentos, como decorador del puerto (de QuickDev, ADR-0006).

Responsabilidad: decidir cuantas veces se reintenta y cuanto se espera. Nada mas.

Lo que NO le corresponde: interpretar errores del proveedor. Eso lo hace cada
adaptador; aqui solo se mira si lo que subio es `LlmRetryableError` o
`LlmTerminalError`. Un terminal se propaga de inmediato, sin dormir.

Agregado en uMarket: `tope_total_s`. Una busqueda tiene un limite de tiempo; un
reintento que empezaria despues de ese limite ya no le sirve a nadie, asi que no
se hace.
"""

import time
from collections.abc import Callable
from dataclasses import replace

from umarket.ia.puerto import LlmPort, LlmRequest, LlmResponse, LlmRetryableError


class RetryingLlm:
    def __init__(
        self,
        inner: LlmPort,
        retries: int = 2,
        backoff_base_s: float = 0.5,
        tope_total_s: float | None = None,
        sleep: Callable[[float], None] = time.sleep,
        reloj: Callable[[], float] = time.monotonic,
    ) -> None:
        """
        Args:
            retries: numero TOTAL de intentos, no de reintentos extra.
            backoff_base_s: espera del primer reintento; se duplica en cada uno.
            tope_total_s: si la proxima espera terminaria despues de este tope
                (contado desde la primera llamada), no se reintenta.
            sleep, reloj: se inyectan para que los tests no duerman de verdad.
        """
        if retries < 1:
            raise ValueError("retries es el numero total de intentos: minimo 1.")
        self.inner = inner
        self.retries = retries
        self.backoff_base_s = backoff_base_s
        self.tope_total_s = tope_total_s
        self._sleep = sleep
        self._reloj = reloj

    def complete_json(self, request: LlmRequest) -> LlmResponse:
        inicio = self._reloj()
        ultimo: LlmRetryableError | None = None

        for intento in range(1, self.retries + 1):
            try:
                respuesta = self.inner.complete_json(request)
            except LlmRetryableError as exc:
                ultimo = exc
                if intento == self.retries:
                    break
                espera = self.backoff_base_s * (2 ** (intento - 1))
                if self._excede_tope(inicio, espera):
                    break
                self._sleep(espera)
                continue
            return _con_intentos(respuesta, intento)

        raise LlmRetryableError(f"Agotados los intentos. Ultimo error: {ultimo}") from ultimo

    def _excede_tope(self, inicio: float, espera: float) -> bool:
        if self.tope_total_s is None:
            return False
        return (self._reloj() - inicio) + espera >= self.tope_total_s


def _con_intentos(respuesta: LlmResponse, intentos: int) -> LlmResponse:
    """Una copia con el intento en que salio; si un decorador interno reporto mas, se conserva."""
    if respuesta.attempts >= intentos:
        return respuesta
    return replace(respuesta, attempts=intentos)
