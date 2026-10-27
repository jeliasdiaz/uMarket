"""Todas las tablas del sistema, juntas, para Alembic y para los tests de esquema.

Importar cada `adaptadores/tablas.py` es lo que las registra en `metadatos`. Un
modulo nuevo con tablas agrega aqui una linea.
"""

from sqlalchemy import MetaData


def metadatos_completos() -> MetaData:
    import umarket.bd.plataforma
    import umarket.busqueda.adaptadores.tablas
    import umarket.campus.adaptadores.tablas
    import umarket.catalogo.adaptadores.tablas
    import umarket.identidad.adaptadores.tablas
    import umarket.notificaciones.adaptadores.tablas
    import umarket.pedidos.adaptadores.tablas
    import umarket.reputacion.adaptadores.tablas  # noqa: F401
    from umarket.bd.metadatos import metadatos

    return metadatos
