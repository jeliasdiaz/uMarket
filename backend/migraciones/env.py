"""Entorno de Alembic.

La URL sale de `Settings.url_migraciones` (la conexion directa en Neon), salvo
que quien llama pase una por `config.attributes["url"]` (los tests lo hacen).

Las migraciones se escriben a mano y se revisan siempre. `tests/bd/test_migraciones.py`
comprueba que, aplicadas, coinciden con las tablas declaradas en el codigo.
"""

from alembic import context
from sqlalchemy import create_engine

from umarket.bd.esquema import metadatos_completos
from umarket.config import Settings

config = context.config
url = config.attributes.get("url") or Settings().url_migraciones
metadatos = metadatos_completos()


def correr_offline() -> None:
    context.configure(url=url, target_metadata=metadatos, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def correr_online() -> None:
    motor = create_engine(url)
    with motor.connect() as conexion:
        context.configure(connection=conexion, target_metadata=metadatos)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    correr_offline()
else:
    correr_online()
