"""Las migraciones aplicadas coinciden con las tablas declaradas en el codigo.

Sin esto, una tabla puede cambiar en `adaptadores/tablas.py` sin migracion (o al
reves) y nadie se entera hasta que falla en Neon.
"""

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import Engine, text

from tests.conftest import URL_TEST, config_alembic
from umarket.bd.esquema import metadatos_completos

pytestmark = pytest.mark.integracion


def test_el_esquema_migrado_coincide_con_el_codigo(motor: Engine) -> None:
    with motor.connect() as conexion:
        diferencias = compare_metadata(MigrationContext.configure(conexion), metadatos_completos())
    assert diferencias == [], f"Migraciones y tablas no coinciden: {diferencias}"


def test_la_busqueda_en_espanol_ignora_tildes(motor: Engine) -> None:
    with motor.connect() as conexion:
        coincide = conexion.execute(
            text(
                "select to_tsvector('es_sin_tildes', 'Café con arepas')"
                " @@ plainto_tsquery('es_sin_tildes', 'cafe arepa')"
            )
        ).scalar_one()
    assert coincide is True


def test_bajar_y_volver_a_subir(motor: Engine) -> None:
    cfg = config_alembic(URL_TEST)
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    with motor.connect() as conexion:
        assert conexion.execute(text("select count(*) from alembic_version")).scalar_one() == 1
