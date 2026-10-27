from sqlalchemy import Column, DateTime, ForeignKey, Table, Text, func
from sqlalchemy.dialects.postgresql import UUID

from umarket.bd.metadatos import metadatos

suscripciones_push = Table(
    "suscripciones_push",
    metadatos,
    Column("endpoint", Text, primary_key=True),
    Column("usuario_id", UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=False, index=True),
    Column("p256dh", Text, nullable=False),
    Column("auth", Text, nullable=False),
    Column("creada_en", DateTime(timezone=True), nullable=False, server_default=func.now()),
)
