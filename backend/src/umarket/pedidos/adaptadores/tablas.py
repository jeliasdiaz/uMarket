from sqlalchemy import (
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    PrimaryKeyConstraint,
    Table,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID

from umarket.bd.metadatos import metadatos
from umarket.pedidos.dominio.estados import Estado
from umarket.pedidos.dominio.pedido import Origen

_ESTADOS = ", ".join(f"'{e.value}'" for e in Estado)
_ORIGENES = ", ".join(f"'{o.value}'" for o in Origen)

pedidos = Table(
    "pedidos",
    metadatos,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("codigo", Text, nullable=False),
    Column("campus_id", Text, ForeignKey("campus.id"), nullable=False),
    Column("tienda_id", UUID(as_uuid=True), ForeignKey("tiendas.id"), nullable=False),
    Column("vendedor_id", UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=False),
    Column("comprador_id", UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=False),
    Column("turno_id", UUID(as_uuid=True), ForeignKey("turnos.id"), nullable=False),
    Column("fecha", Date, nullable=False),
    Column("franja_id", Text, ForeignKey("franjas.id"), nullable=False),
    Column("punto_id", Text, ForeignKey("puntos_encuentro.id"), nullable=False),
    Column("estado", Text, nullable=False),
    Column("total_cop", Integer, nullable=False),
    Column("origen", Text, nullable=False, server_default="tienda"),
    Column("busqueda_id", UUID(as_uuid=True)),
    Column("clave_idempotencia", Text, nullable=False),
    Column("creado_en", DateTime(timezone=True), nullable=False),
    Column("vence_en", DateTime(timezone=True), nullable=False),
    Column("actualizado_en", DateTime(timezone=True), nullable=False),
    Column("llegada_en", DateTime(timezone=True)),
    Column("motivo", Text),
    CheckConstraint(f"estado IN ({_ESTADOS})", name="estado_valido"),
    CheckConstraint(f"origen IN ({_ORIGENES})", name="origen_valido"),
    CheckConstraint("total_cop > 0", name="total_positivo"),
    # El codigo se dice en voz alta: unico por tienda y dia, no globalmente.
    UniqueConstraint("tienda_id", "fecha", "codigo"),
    # Doble toque en "Confirmar" = el mismo pedido.
    UniqueConstraint("comprador_id", "clave_idempotencia"),
    Index(
        "ix_pedidos_vence_en_pendientes", "vence_en", postgresql_where=text("estado = 'pendiente'")
    ),
    Index("ix_pedidos_vendedor_id_fecha", "vendedor_id", "fecha"),
    Index("ix_pedidos_comprador_id_estado", "comprador_id", "estado"),
)

pedido_items = Table(
    "pedido_items",
    metadatos,
    Column("pedido_id", UUID(as_uuid=True), ForeignKey("pedidos.id"), nullable=False),
    Column("producto_id", UUID(as_uuid=True), ForeignKey("productos.id"), nullable=False),
    # Copia del nombre y del precio al momento del pedido: si el vendedor cambia
    # el precio manana, el pedido de hoy no cambia.
    Column("nombre", Text, nullable=False),
    Column("precio_unitario_cop", Integer, nullable=False),
    Column("cantidad", Integer, nullable=False),
    PrimaryKeyConstraint("pedido_id", "producto_id"),
    CheckConstraint("cantidad > 0", name="cantidad_positiva"),
)

transiciones_pedido = Table(
    "transiciones_pedido",
    metadatos,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("pedido_id", UUID(as_uuid=True), ForeignKey("pedidos.id"), nullable=False, index=True),
    Column("desde", Text),
    Column("hacia", Text, nullable=False),
    Column("accion", Text, nullable=False),
    Column("actor", Text, nullable=False),
    Column("motivo", Text),
    Column("en", DateTime(timezone=True), nullable=False),
)
