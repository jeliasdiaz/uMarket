"""Sella un prompt: calcula el sha256 de su cuerpo y lo escribe en el front matter.

    python scripts/sellar_prompt.py prompts/busqueda/v2.md

Solo se sella un prompt NUEVO. Uno medido no se re-sella: si cambia, es otra
version (otro archivo) y se mide (ADR-0011 de QuickDev).
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from umarket.ia.prompts import leer_prompt, sha256_de


def sellar(archivo: Path) -> str:
    meta, cuerpo = leer_prompt(archivo)
    if meta.get("estado") == "medido":
        raise SystemExit(
            f"{archivo} esta medido: un cambio es una version nueva, no un re-sellado."
        )
    sha = sha256_de(cuerpo)
    texto = archivo.read_bytes().decode("utf-8").replace("\r\n", "\n")
    texto = re.sub(r"^sha256: .*$", f"sha256: {sha}", texto, count=1, flags=re.MULTILINE)
    archivo.write_bytes(texto.encode("utf-8"))
    return sha


if __name__ == "__main__":
    for ruta in sys.argv[1:]:
        print(ruta, sellar(Path(ruta)))
