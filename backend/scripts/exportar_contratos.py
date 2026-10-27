"""Exporta los contratos generados desde el codigo a `contratos/` (PLAN-TECNICO.md §8).

    python scripts/exportar_contratos.py              # escribe
    python scripts/exportar_contratos.py --verificar  # sale con 1 si difieren (CI)

Los contratos se GENERAN, nunca se mantienen a mano en paralelo: en QuickDev,
`contract_frozen.json` termino contradiciendo al codigo (ADR-0013). La unica
excepcion es el contrato de producto (`busqueda/producto.json`), escrito a mano
y protegido por un test que lo cruza con el modelo y las reglas.
"""

import json
import sys
from pathlib import Path
from typing import Any

RAIZ = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(RAIZ / "src"), str(RAIZ)]

from umarket.arranque import crear
from umarket.busqueda.dominio.contrato import ConsultaInterpretada, EntradaInterprete
from umarket.config import Settings
from umarket.ia.adaptadores.gemini import esquema_para_gemini

CONTRATOS = RAIZ / "contratos"


def generar() -> dict[str, Any]:
    app = crear(Settings(entorno="test"))
    return {
        "openapi.json": app.openapi(),
        "busqueda/consulta.v1.schema.json": ConsultaInterpretada.model_json_schema(),
        "busqueda/consulta.v1.gemini.schema.json": esquema_para_gemini(ConsultaInterpretada),
        "busqueda/entrada.v1.schema.json": EntradaInterprete.model_json_schema(),
    }


def serializar(valor: Any) -> str:
    return json.dumps(valor, indent=2, ensure_ascii=False) + "\n"


def main() -> int:
    verificar = "--verificar" in sys.argv
    diferentes: list[str] = []
    for nombre, contenido in generar().items():
        ruta = CONTRATOS / nombre
        texto = serializar(contenido)
        if verificar:
            actual = ruta.read_text("utf-8") if ruta.exists() else ""
            if actual != texto:
                diferentes.append(nombre)
        else:
            ruta.parent.mkdir(parents=True, exist_ok=True)
            ruta.write_text(texto, "utf-8")
            print(f"escrito {ruta.relative_to(RAIZ)}")
    if diferentes:
        print("Contratos desactualizados (corre scripts/exportar_contratos.py):", diferentes)
        return 1
    if verificar:
        print("Contratos al dia.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
