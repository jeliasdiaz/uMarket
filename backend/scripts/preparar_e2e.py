"""Deja una base lista para pruebas E2E o una demo: esquema limpio, campus y catalogo fixture HOY.

    DATABASE_URL=postgresql+psycopg://...umarket_e2e python scripts/preparar_e2e.py

Borra el esquema de esa base. Se niega a correr contra una URL de Neon o de un
entorno que no sea local/test: es una herramienta de desarrollo.
"""

import sys
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

RAIZ = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(RAIZ / "src"), str(RAIZ)]

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

from evals.fixture import sembrar_fixture
from scripts.sembrar_datos import sembrar_campus
from umarket.config import Settings


def main() -> int:
    settings = Settings()
    url = settings.database_url
    if "neon.tech" in url or settings.entorno not in ("local", "test"):
        print("preparar_e2e solo corre contra Postgres local (entorno local o test).")
        return 1
    motor = create_engine(url)
    with motor.begin() as c:
        c.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        c.execute(text("CREATE SCHEMA public"))
    cfg = Config(str(RAIZ / "alembic.ini"))
    cfg.attributes["url"] = url
    command.upgrade(cfg, "head")
    sembrar_campus(motor)
    hoy = datetime.now(UTC).astimezone(ZoneInfo(settings.zona_horaria_por_defecto)).date()
    claves = sembrar_fixture(motor, hoy)
    print(f"Base lista: campus demo y {len(claves)} productos con turnos para {hoy}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
