"""La puerta local: lo mismo que corre la CI del backend, en un comando.

    python scripts/verificar.py            # todo
    python scripts/verificar.py --rapido   # sin pyright

Sale con codigo 1 si algo falla. Funciona igual en Windows, macOS y Linux.
"""

import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
BIN = RAIZ / ".venv" / ("Scripts" if sys.platform == "win32" else "bin")


def _bin(nombre: str) -> str:
    candidato = BIN / (nombre + (".exe" if sys.platform == "win32" else ""))
    return str(candidato) if candidato.exists() else nombre


PASOS: list[tuple[str, list[str]]] = [
    ("ruff format", [sys.executable, "-m", "ruff", "format", "--check", "."]),
    ("ruff check", [sys.executable, "-m", "ruff", "check", "."]),
    ("import-linter", [_bin("lint-imports")]),
    ("pyright", [_bin("pyright")]),
    ("pytest", [sys.executable, "-m", "pytest", "-p", "no:warnings"]),
    ("regresiones", [sys.executable, "scripts/gate_regresiones.py"]),
]


def main() -> int:
    rapido = "--rapido" in sys.argv
    resultados: list[tuple[str, bool, str]] = []
    for nombre, comando in PASOS:
        if rapido and nombre == "pyright":
            continue
        if nombre == "regresiones" and not (RAIZ / "scripts" / "gate_regresiones.py").exists():
            continue
        proceso = subprocess.run(comando, cwd=RAIZ, capture_output=True, text=True)
        salida = (proceso.stdout + proceso.stderr).strip().splitlines()
        resultados.append((nombre, proceso.returncode == 0, salida[-1] if salida else ""))
        if proceso.returncode != 0:
            print(f"\n--- {nombre} FALLO ---\n" + "\n".join(salida[-40:]))
    print("\nResumen:")
    for nombre, ok, ultima in resultados:
        print(f"  {'OK   ' if ok else 'FALLA'} {nombre:<14} {ultima[:90]}")
    return 0 if all(ok for _, ok, _ in resultados) else 1


if __name__ == "__main__":
    sys.exit(main())
