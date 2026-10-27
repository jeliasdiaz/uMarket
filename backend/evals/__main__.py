"""python -m evals correr | comparar  (ver evals/runner.py)."""

import argparse
import sys
from pathlib import Path

from evals.runner import comparar, correr


def main() -> int:
    parser = argparse.ArgumentParser(prog="python -m evals")
    sub = parser.add_subparsers(dest="orden", required=True)

    c = sub.add_parser("correr", help="corre el dataset contra un interprete")
    c.add_argument("--interprete", choices=["palabras", "intencion"], required=True)
    c.add_argument("--n", type=int, default=1, help="corridas por consulta")
    c.add_argument("--conjunto", choices=["dev", "test", "todo"], default="todo")
    c.add_argument("--replay", type=Path, help="crudo.json: reproduce sin red ni cuota")
    c.add_argument("--timeout", type=float, default=3.0, help="tope de la interpretacion (s)")
    c.add_argument("--reglas", help="conjunto de reglas (por defecto el de Settings)")

    k = sub.add_parser("comparar", help="puerta de entrada: baseline contra after")
    k.add_argument("baseline", type=Path)
    k.add_argument("after", type=Path)

    args = parser.parse_args()
    if args.orden == "correr":
        destino = correr(
            args.interprete, args.n, args.conjunto, args.replay, args.timeout, args.reglas
        )
        print((destino / "resumen.md").read_text("utf-8"))
        print(f"Resultados en {destino}")
        return 0
    pasa, texto = comparar(args.baseline, args.after)
    print(texto)
    return 0 if pasa else 1


if __name__ == "__main__":
    sys.exit(main())
