"""Datos semilla del campus demo: puntos, franjas y (opcional) tiendas de ejemplo.

Idempotente: se puede correr varias veces. Uso:

    python scripts/sembrar_datos.py            # solo campus, puntos y franjas
    python scripts/sembrar_datos.py --demo     # ademas tiendas y productos de ejemplo
"""

import argparse
import sys
from datetime import time
from pathlib import Path

from sqlalchemy import Engine, create_engine
from sqlalchemy.dialects.postgresql import insert

sys.path[:0] = [
    str(Path(__file__).resolve().parents[1] / "src"),
    str(Path(__file__).resolve().parents[1]),
]

from umarket.campus.adaptadores.tablas import campus, franjas, puntos_encuentro
from umarket.config import Settings

CAMPUS_DEMO = {
    "id": "campus-demo",
    "nombre": "Campus Demo",
    "zona_horaria": "America/Bogota",
    "dominios_correo": ["demo.edu.co"],
}

PUNTOS = [
    (
        "b19-entrada",
        "Bloque 19 - entrada",
        "Bajo el techo, junto a la portería.",
        ["el 19", "bloque 19"],
    ),
    (
        "b19-cafeteria",
        "Bloque 19 - cafetería",
        "Mesas cubiertas del bloque 19.",
        ["el 19", "cafe del 19"],
    ),
    (
        "biblioteca",
        "Biblioteca central - plazoleta",
        "Plazoleta frente a la entrada.",
        ["la biblio"],
    ),
    (
        "cafeteria-central",
        "Cafetería central",
        "Entrada principal de la cafetería.",
        ["la central"],
    ),
]

FRANJAS = [
    ("f-0700", time(7, 0), time(7, 30)),
    ("f-1000", time(10, 0), time(10, 30)),
    ("f-1200", time(12, 0), time(12, 30)),
    ("f-1600", time(16, 0), time(16, 30)),
]


def sembrar_campus(motor: Engine, campus_id: str = "campus-demo") -> None:
    datos = {**CAMPUS_DEMO, "id": campus_id}
    with motor.begin() as c:
        c.execute(
            insert(campus).values(**datos).on_conflict_do_update(index_elements=["id"], set_=datos)
        )
        for pid, nombre, descripcion, alias in PUNTOS:
            fila = {
                "id": pid,
                "campus_id": campus_id,
                "nombre": nombre,
                "descripcion": descripcion,
                "alias": alias,
            }
            c.execute(
                insert(puntos_encuentro)
                .values(**fila)
                .on_conflict_do_update(index_elements=["id"], set_=fila)
            )
        for fid, inicio, fin in FRANJAS:
            fila = {"id": fid, "campus_id": campus_id, "hora_inicio": inicio, "hora_fin": fin}
            c.execute(
                insert(franjas)
                .values(**fila)
                .on_conflict_do_update(index_elements=["id"], set_=fila)
            )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--demo", action="store_true", help="tiendas y productos de ejemplo")
    args = parser.parse_args()
    motor = create_engine(Settings().database_url)
    sembrar_campus(motor)
    print("Campus demo sembrado: 4 puntos, 4 franjas.")
    if args.demo:
        from datetime import UTC, datetime
        from zoneinfo import ZoneInfo

        from evals.fixture import sembrar_fixture

        hoy = datetime.now(UTC).astimezone(ZoneInfo("America/Bogota")).date()
        print(f"Catalogo demo: {len(sembrar_fixture(motor, hoy))} productos con turnos para {hoy}.")


if __name__ == "__main__":
    main()
