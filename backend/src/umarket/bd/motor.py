"""El motor de SQLAlchemy y la fabrica de sesiones.

Neon: la cadena *pooled* pasa por PgBouncer en modo transaccion. psycopg prepara
sentencias del lado del servidor tras varias ejecuciones, y eso puede fallar con
un pooler; por eso, si la URL es de un pooler, se desactiva. En Postgres local no
cambia nada.
"""

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker


def crear_motor(url: str) -> Engine:
    connect_args: dict[str, object] = {}
    if "-pooler" in url:
        connect_args["prepare_threshold"] = None
    return create_engine(url, pool_pre_ping=True, connect_args=connect_args)


def crear_fabrica_sesiones(motor: Engine) -> sessionmaker[Session]:
    # expire_on_commit=False: los adaptadores devuelven objetos de dominio, no filas
    # vivas; no hace falta recargarlas despues de confirmar.
    return sessionmaker(bind=motor, expire_on_commit=False)


def verificar_conexion(motor: Engine) -> str:
    """La version del servidor. Para `/salud/bd`."""
    with motor.connect() as conexion:
        return str(conexion.execute(text("select version()")).scalar_one())
