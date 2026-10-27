"""Los metadatos compartidos por las tablas de todos los modulos.

Cada modulo declara sus tablas en `adaptadores/tablas.py` sobre este objeto, y
Alembic los junta en `migraciones/env.py`. La convencion de nombres hace que los
nombres de indices y restricciones sean estables entre autogeneraciones.

Los estados y vocabularios se guardan como `text` con `CHECK`, no como enums de
Postgres: agregar un estado es cambiar una restriccion, no una migracion de tipo.
"""

from sqlalchemy import MetaData

metadatos = MetaData(
    naming_convention={
        "ix": "ix_%(table_name)s_%(column_0_N_name)s",
        "uq": "uq_%(table_name)s_%(column_0_N_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "pk": "pk_%(table_name)s",
    }
)
