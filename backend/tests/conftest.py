"""Fixtures compartidas.

Los tests de integracion corren contra un Postgres real (`DATABASE_URL_TEST`,
por defecto el del `compose.yaml`). Si no hay Postgres, se SALTAN con un motivo
visible, no fallan: la suite de dominio sigue sirviendo sin Docker. En CI hay
Postgres, asi que ahi corren siempre.

Al empezar la sesion se borra el esquema de la base de tests y se aplican TODAS
las migraciones: los tests prueban el esquema que se despliega, no uno creado
con `metadata.create_all`.
"""

import os
from collections.abc import Iterator

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import OperationalError

from umarket.bd.esquema import metadatos_completos
from umarket.config import RAIZ_BACKEND

URL_TEST = os.environ.get(
    "DATABASE_URL_TEST", "postgresql+psycopg://umarket:umarket@localhost:5433/umarket_test"
)


def config_alembic(url: str) -> Config:
    cfg = Config(str(RAIZ_BACKEND / "alembic.ini"))
    cfg.attributes["url"] = url
    return cfg


def recrear_esquema(motor: Engine) -> None:
    with motor.begin() as conexion:
        conexion.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        conexion.execute(text("CREATE SCHEMA public"))


@pytest.fixture(scope="session")
def motor() -> Iterator[Engine]:
    motor = create_engine(URL_TEST, pool_pre_ping=True)
    try:
        with motor.connect():
            pass
    except OperationalError as exc:
        pytest.skip(f"Sin Postgres de tests en {URL_TEST}: {exc.__class__.__name__}")
    recrear_esquema(motor)
    command.upgrade(config_alembic(URL_TEST), "head")
    yield motor
    motor.dispose()


@pytest.fixture
def bd(motor: Engine) -> Engine:
    """Base limpia para cada test: TRUNCATE de todas las tablas del sistema."""
    tablas = [t.name for t in metadatos_completos().sorted_tables]
    if tablas:
        with motor.begin() as conexion:
            conexion.execute(text(f"TRUNCATE {', '.join(tablas)} RESTART IDENTITY CASCADE"))
    return motor
