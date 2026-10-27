from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, Table, Text, func
from sqlalchemy.dialects.postgresql import UUID

from umarket.bd.metadatos import metadatos

usuarios = Table(
    "usuarios",
    metadatos,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("campus_id", Text, ForeignKey("campus.id"), nullable=False, index=True),
    Column("correo", Text, nullable=False, unique=True),
    Column("nombre", Text, nullable=False),
    Column("creado_en", DateTime(timezone=True), nullable=False),
)

consentimientos = Table(
    "consentimientos",
    metadatos,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("usuario_id", UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=False, index=True),
    Column("version_terminos", Text, nullable=False),
    Column("aceptado_en", DateTime(timezone=True), nullable=False, server_default=func.now()),
)

codigos_acceso = Table(
    "codigos_acceso",
    metadatos,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("correo", Text, nullable=False),
    Column("codigo_huella", Text, nullable=False),
    Column("creado_en", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("expira_en", DateTime(timezone=True), nullable=False),
    Column("intentos", Integer, nullable=False, server_default="0"),
    Column("usado_en", DateTime(timezone=True)),
    Index("ix_codigos_acceso_correo_creado_en", "correo", "creado_en"),
)

sesiones = Table(
    "sesiones",
    metadatos,
    Column("token_huella", Text, primary_key=True),
    Column("usuario_id", UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=False, index=True),
    Column("creado_en", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("expira_en", DateTime(timezone=True), nullable=False),
)
