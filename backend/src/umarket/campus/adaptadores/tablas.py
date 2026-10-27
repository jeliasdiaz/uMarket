from sqlalchemy import Boolean, CheckConstraint, Column, ForeignKey, Table, Text, Time
from sqlalchemy.dialects.postgresql import ARRAY

from umarket.bd.metadatos import metadatos

campus = Table(
    "campus",
    metadatos,
    Column("id", Text, primary_key=True),
    Column("nombre", Text, nullable=False),
    Column("zona_horaria", Text, nullable=False, server_default="America/Bogota"),
    Column("dominios_correo", ARRAY(Text), nullable=False, server_default="{}"),
)

puntos_encuentro = Table(
    "puntos_encuentro",
    metadatos,
    Column("id", Text, primary_key=True),
    Column("campus_id", Text, ForeignKey("campus.id"), nullable=False, index=True),
    Column("nombre", Text, nullable=False),
    Column("descripcion", Text, nullable=False, server_default=""),
    Column("foto_url", Text),
    Column("alias", ARRAY(Text), nullable=False, server_default="{}"),
    Column("activo", Boolean, nullable=False, server_default="true"),
)

franjas = Table(
    "franjas",
    metadatos,
    Column("id", Text, primary_key=True),
    Column("campus_id", Text, ForeignKey("campus.id"), nullable=False, index=True),
    Column("hora_inicio", Time, nullable=False),
    Column("hora_fin", Time, nullable=False),
    CheckConstraint("hora_fin > hora_inicio", name="orden_horas"),
)
