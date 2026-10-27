from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Computed,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    PrimaryKeyConstraint,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, TSVECTOR, UUID

from umarket.bd.metadatos import metadatos
from umarket.catalogo.dominio.vocabulario import CATEGORIAS

_CATEGORIAS_SQL = ", ".join(f"'{c}'" for c in CATEGORIAS)

tiendas = Table(
    "tiendas",
    metadatos,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("campus_id", Text, ForeignKey("campus.id"), nullable=False, index=True),
    Column("vendedor_id", UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=False),
    Column("nombre", Text, nullable=False),
    Column("slug", Text, nullable=False),
    Column("descripcion", Text, nullable=False, server_default=""),
    Column("activa", Boolean, nullable=False, server_default="true"),
    Column("creada_en", DateTime(timezone=True), nullable=False),
    # MVP: una tienda por vendedor.
    UniqueConstraint("vendedor_id"),
    UniqueConstraint("slug"),
)

productos = Table(
    "productos",
    metadatos,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("tienda_id", UUID(as_uuid=True), ForeignKey("tiendas.id"), nullable=False, index=True),
    Column("nombre", Text, nullable=False),
    # Lo calcula la aplicacion con `normalizar()`: el mismo que usan las reglas.
    Column("nombre_normalizado", Text, nullable=False),
    Column("descripcion", Text, nullable=False, server_default=""),
    Column("categoria", Text, nullable=False),
    Column("etiquetas", ARRAY(Text), nullable=False, server_default="{}"),
    Column("precio_cop", Integer, nullable=False),
    Column("activo", Boolean, nullable=False, server_default="true"),
    Column(
        "busqueda",
        TSVECTOR,
        Computed(
            "to_tsvector('es_sin_tildes'::regconfig, nombre || ' ' || descripcion)",
            persisted=True,
        ),
    ),
    CheckConstraint(f"categoria IN ({_CATEGORIAS_SQL})", name="categoria_valida"),
    CheckConstraint("precio_cop > 0", name="precio_positivo"),
    Index("ix_productos_busqueda", "busqueda", postgresql_using="gin"),
    Index(
        "ix_productos_nombre_trgm",
        "nombre_normalizado",
        postgresql_using="gin",
        postgresql_ops={"nombre_normalizado": "gin_trgm_ops"},
    ),
)

turnos = Table(
    "turnos",
    metadatos,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("tienda_id", UUID(as_uuid=True), ForeignKey("tiendas.id"), nullable=False),
    Column("fecha", Date, nullable=False),
    Column("franja_id", Text, ForeignKey("franjas.id"), nullable=False),
    Column("punto_id", Text, ForeignKey("puntos_encuentro.id"), nullable=False),
    # Un vendedor esta en un solo lugar por franja.
    UniqueConstraint("tienda_id", "fecha", "franja_id"),
    Index("ix_turnos_fecha_franja_id", "fecha", "franja_id"),
)

stock_turno = Table(
    "stock_turno",
    metadatos,
    Column("turno_id", UUID(as_uuid=True), ForeignKey("turnos.id"), nullable=False),
    Column("producto_id", UUID(as_uuid=True), ForeignKey("productos.id"), nullable=False),
    Column("total", Integer, nullable=False),
    Column("reservado", Integer, nullable=False, server_default="0"),
    PrimaryKeyConstraint("turno_id", "producto_id"),
    # La garantia de D-14: la base de datos no deja reservar mas de lo que hay.
    CheckConstraint("reservado >= 0 AND reservado <= total", name="reserva_dentro_del_total"),
)
