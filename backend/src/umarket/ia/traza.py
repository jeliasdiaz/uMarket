"""La traza de una ejecucion de un componente de IA (de QuickDev, con costo).

Responsabilidad: registrar que paso, en que orden, con que decision, y cuanto
costo. Las versiones (prompt, reglas, esquema, modelo, proveedor) son lo que hace
comparable una medicion: una fila sin ese estampado no se puede contrastar.

Lo que NO le corresponde: guardarse. La aplicacion la entrega a su repositorio,
que la persiste en `trazas_ia`.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from umarket.ia.precios import costo_usd
from umarket.ia.puerto import LlmResponse


def _ahora_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds")


@dataclass(frozen=True)
class PasoTraza:
    """`decision` es para personas: que se decidio y por que."""

    nombre: str
    decision: str
    duracion_s: float = 0.0
    metadatos: dict[str, Any] = field(default_factory=dict[str, Any])

    def a_dict(self) -> dict[str, Any]:
        return {
            "nombre": self.nombre,
            "decision": self.decision,
            "duracion_s": round(self.duracion_s, 4),
            "metadatos": self.metadatos,
        }


@dataclass
class Traza:
    componente: str
    prompt_version: str = ""
    schema_version: str = ""
    rules_version: str = ""
    modelo: str = ""
    proveedor: str = ""
    run_id: str = field(default_factory=lambda: uuid4().hex[:12])
    iniciada_en: str = field(default_factory=_ahora_iso)
    pasos: list[PasoTraza] = field(default_factory=list[PasoTraza])
    tokens_entrada: int = 0
    tokens_salida: int = 0
    tokens_razonamiento: int = 0
    costo_usd: float | None = 0.0

    def paso(
        self, nombre: str, decision: str, duracion_s: float = 0.0, **metadatos: Any
    ) -> PasoTraza:
        registrado = PasoTraza(nombre, decision, duracion_s, dict(metadatos))
        self.pasos.append(registrado)
        return registrado

    def registrar_llamada(self, respuesta: LlmResponse) -> None:
        """Suma tokens y costo. Un costo desconocido contamina el total a None, a proposito."""
        self.modelo = respuesta.model or self.modelo
        self.proveedor = respuesta.provider or self.proveedor
        if respuesta.from_cache:
            return
        self.tokens_entrada += respuesta.usage.entrada
        self.tokens_salida += respuesta.usage.salida
        self.tokens_razonamiento += respuesta.usage.razonamiento
        costo = costo_usd(respuesta.model, respuesta.usage)
        self.costo_usd = (
            None if (costo is None or self.costo_usd is None) else self.costo_usd + costo
        )

    @property
    def duracion_s(self) -> float:
        return sum(p.duracion_s for p in self.pasos)

    def a_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "componente": self.componente,
            "iniciada_en": self.iniciada_en,
            "prompt_version": self.prompt_version,
            "schema_version": self.schema_version,
            "rules_version": self.rules_version,
            "modelo": self.modelo,
            "proveedor": self.proveedor,
            "tokens": {
                "entrada": self.tokens_entrada,
                "salida": self.tokens_salida,
                "razonamiento": self.tokens_razonamiento,
            },
            "costo_usd": self.costo_usd,
            "pasos": [p.a_dict() for p in self.pasos],
        }
