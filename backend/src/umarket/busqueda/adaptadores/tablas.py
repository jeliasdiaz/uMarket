from sqlalchemy import Column, DateTime, ForeignKey, Integer, Numeric, Table, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID

from umarket.bd.metadatos import metadatos

# El registro de busquedas es a la vez metrica de producto (conversion, busquedas
# sin resultados = demanda no cubierta) y la fuente del dataset de evals, previa
# anonimizacion y con consentimiento (PLAN-Y-DECISIONES §4.3).
busquedas = Table(
    "busquedas",
    metadatos,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("campus_id", Text, ForeignKey("campus.id"), nullable=False),
    Column("usuario_id", UUID(as_uuid=True), ForeignKey("usuarios.id")),
    Column("texto", Text, nullable=False),
    Column("interprete", Text, nullable=False),
    Column("consulta", JSONB, nullable=False),
    Column("anulados", ARRAY(Text), nullable=False, server_default="{}"),
    Column("relajados", ARRAY(Text), nullable=False, server_default="{}"),
    Column("n_tiendas", Integer, nullable=False),
    Column("n_productos", Integer, nullable=False),
    Column("latencia_ms", Integer, nullable=False),
    Column("tokens", Integer, nullable=False, server_default="0"),
    Column("costo_usd", Numeric(12, 6)),
    Column("run_id", Text, nullable=False),
    Column("creada_en", DateTime(timezone=True), nullable=False, index=True),
)

busqueda_clics = Table(
    "busqueda_clics",
    metadatos,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column(
        "busqueda_id", UUID(as_uuid=True), ForeignKey("busquedas.id"), nullable=False, index=True
    ),
    Column("tienda_id", UUID(as_uuid=True), ForeignKey("tiendas.id"), nullable=False),
    Column("producto_id", UUID(as_uuid=True), ForeignKey("productos.id")),
    Column("posicion", Integer, nullable=False),
    Column("creado_en", DateTime(timezone=True), nullable=False),
)
