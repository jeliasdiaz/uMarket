from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    SmallInteger,
    Table,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID

from umarket.bd.metadatos import metadatos

calificaciones = Table(
    "calificaciones",
    metadatos,
    Column("id", UUID(as_uuid=True), primary_key=True),
    # Una calificacion por pedido: solo califica quien recibio, y una vez.
    Column("pedido_id", UUID(as_uuid=True), ForeignKey("pedidos.id"), nullable=False, unique=True),
    Column("tienda_id", UUID(as_uuid=True), ForeignKey("tiendas.id"), nullable=False, index=True),
    Column("comprador_id", UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=False),
    Column("estrellas", SmallInteger, nullable=False),
    Column("comentario", Text, nullable=False, server_default=""),
    Column("creada_en", DateTime(timezone=True), nullable=False),
    CheckConstraint("estrellas BETWEEN 1 AND 5", name="estrellas_validas"),
)

metricas_tienda = Table(
    "metricas_tienda",
    metadatos,
    Column("tienda_id", UUID(as_uuid=True), ForeignKey("tiendas.id"), primary_key=True),
    Column("resenas", Integer, nullable=False, server_default="0"),
    Column("suma_estrellas", Integer, nullable=False, server_default="0"),
    Column("entregas", Integer, nullable=False, server_default="0"),
    Column("vencidos", Integer, nullable=False, server_default="0"),
    Column("cancelados_por_vendedor", Integer, nullable=False, server_default="0"),
    Column("actualizado_en", DateTime(timezone=True), nullable=False),
)
