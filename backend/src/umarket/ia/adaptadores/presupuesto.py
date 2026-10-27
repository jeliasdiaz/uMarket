"""Presupuesto diario de gasto, como decorador del puerto.

Responsabilidad: dejar de llamar al proveedor cuando el gasto del dia supera el
limite. Lanza `LlmPresupuestoAgotado` (terminal), y quien llama usa su respaldo:
en la busqueda, el interprete por palabras clave.

Va DENTRO del decorador de reintentos para contar cada intento real contra el
proveedor, y FUERA del adaptador para no depender de ninguno.

Limite conocido: el acumulado vive en memoria del proceso. Con un solo proceso
de API (el prototipo) es exacto; con varios, cada uno tendria su propio
acumulado. El disparador para llevarlo a la base de datos esta en
PLAN-TECNICO.md §17.
"""

from collections.abc import Callable
from datetime import UTC, date, datetime

from umarket.ia.precios import costo_usd
from umarket.ia.puerto import LlmPort, LlmPresupuestoAgotado, LlmRequest, LlmResponse


class ConPresupuesto:
    def __init__(
        self,
        inner: LlmPort,
        limite_usd: float,
        hoy: Callable[[], date] = lambda: datetime.now(UTC).date(),
    ) -> None:
        self.inner = inner
        self.limite_usd = limite_usd
        self._hoy = hoy
        self._dia = hoy()
        self._gastado = 0.0

    @property
    def gastado_hoy_usd(self) -> float:
        self._reiniciar_si_cambio_el_dia()
        return self._gastado

    def complete_json(self, request: LlmRequest) -> LlmResponse:
        self._reiniciar_si_cambio_el_dia()
        if self._gastado >= self.limite_usd:
            raise LlmPresupuestoAgotado(
                f"Presupuesto diario agotado: {self._gastado:.4f} USD de {self.limite_usd:.4f}."
            )
        respuesta = self.inner.complete_json(request)
        self._gastado += costo_usd(respuesta.model, respuesta.usage) or 0.0
        return respuesta

    def _reiniciar_si_cambio_el_dia(self) -> None:
        hoy = self._hoy()
        if hoy != self._dia:
            self._dia = hoy
            self._gastado = 0.0
