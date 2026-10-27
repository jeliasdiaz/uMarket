"""La puerta de regresiones: el validador sigue detectando lo mismo que la medicion commiteada.

    python scripts/gate_regresiones.py              # compara con el CSV esperado
    python scripts/gate_regresiones.py --escribir   # regenera el CSV (decision consciente)

Sale con codigo 1 si algo difiere. Regenerar el CSV es cambiar lo medido: se
anota en docs/DECISIONES.md.
"""

import csv
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(RAIZ / "src"), str(RAIZ)]

from evals.regresiones import correr_regresiones

ESPERADAS = RAIZ / "evals" / "regresiones_esperadas.csv"


def main() -> int:
    filas = correr_regresiones()
    if "--escribir" in sys.argv:
        with ESPERADAS.open("w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerows([("version", "caso", "reglas_esperadas", "resultado"), *filas])
        print(f"Escrito {ESPERADAS} ({len(filas)} casos)")
        return 0
    with ESPERADAS.open(encoding="utf-8") as f:
        esperadas = [tuple(fila) for fila in list(csv.reader(f))[1:]]
    diferencias = [(e, o) for e, o in zip(esperadas, filas, strict=False) if e != o]
    if len(esperadas) != len(filas):
        diferencias.append(
            (("total", "", str(len(esperadas)), ""), ("total", "", str(len(filas)), ""))
        )
    for esperada, obtenida in diferencias:
        print(f"  DIFIERE: esperado {esperada} | obtenido {obtenida}")
    aprobadas = sum(1 for *_, r in filas if r == "PASS")
    estado = "ABIERTA" if not diferencias else "CERRADA"
    print(f"{aprobadas}/{len(filas)} PASS · puerta {estado}")
    return 0 if not diferencias else 1


if __name__ == "__main__":
    sys.exit(main())
