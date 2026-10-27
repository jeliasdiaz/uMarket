"""Pedidos: pedidos, items (con copia de nombre y precio) y transiciones.

Revision: 0004
Anterior: 0003
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)
ESTADOS = (
    "pendiente",
    "aprobado",
    "rechazado",
    "vencido",
    "cancelado",
    "en_punto",
    "entregado",
    "no_asistio",
)
TZ = sa.DateTime(timezone=True)


def _lista(valores: tuple[str, ...]) -> str:
    return ", ".join(f"'{v}'" for v in valores)


def upgrade() -> None:
    op.create_table(
        "pedidos",
        sa.Column("id", UUID, nullable=False),
        sa.Column("codigo", sa.Text(), nullable=False),
        sa.Column("campus_id", sa.Text(), nullable=False),
        sa.Column("tienda_id", UUID, nullable=False),
        sa.Column("vendedor_id", UUID, nullable=False),
        sa.Column("comprador_id", UUID, nullable=False),
        sa.Column("turno_id", UUID, nullable=False),
        sa.Column("fecha", sa.Date(), nullable=False),
        sa.Column("franja_id", sa.Text(), nullable=False),
        sa.Column("punto_id", sa.Text(), nullable=False),
        sa.Column("estado", sa.Text(), nullable=False),
        sa.Column("total_cop", sa.Integer(), nullable=False),
        sa.Column("origen", sa.Text(), server_default="tienda", nullable=False),
        sa.Column("busqueda_id", UUID),
        sa.Column("clave_idempotencia", sa.Text(), nullable=False),
        sa.Column("creado_en", TZ, nullable=False),
        sa.Column("vence_en", TZ, nullable=False),
        sa.Column("actualizado_en", TZ, nullable=False),
        sa.Column("llegada_en", TZ),
        sa.Column("motivo", sa.Text()),
        sa.CheckConstraint(f"estado IN ({_lista(ESTADOS)})", name="ck_pedidos_estado_valido"),
        sa.CheckConstraint("origen IN ('tienda', 'busqueda')", name="ck_pedidos_origen_valido"),
        sa.CheckConstraint("total_cop > 0", name="ck_pedidos_total_positivo"),
        sa.ForeignKeyConstraint(["campus_id"], ["campus.id"], name="fk_pedidos_campus_id_campus"),
        sa.ForeignKeyConstraint(["tienda_id"], ["tiendas.id"], name="fk_pedidos_tienda_id_tiendas"),
        sa.ForeignKeyConstraint(
            ["vendedor_id"], ["usuarios.id"], name="fk_pedidos_vendedor_id_usuarios"
        ),
        sa.ForeignKeyConstraint(
            ["comprador_id"], ["usuarios.id"], name="fk_pedidos_comprador_id_usuarios"
        ),
        sa.ForeignKeyConstraint(["turno_id"], ["turnos.id"], name="fk_pedidos_turno_id_turnos"),
        sa.ForeignKeyConstraint(["franja_id"], ["franjas.id"], name="fk_pedidos_franja_id_franjas"),
        sa.ForeignKeyConstraint(
            ["punto_id"], ["puntos_encuentro.id"], name="fk_pedidos_punto_id_puntos_encuentro"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_pedidos"),
        sa.UniqueConstraint(
            "tienda_id", "fecha", "codigo", name="uq_pedidos_tienda_id_fecha_codigo"
        ),
        sa.UniqueConstraint(
            "comprador_id", "clave_idempotencia", name="uq_pedidos_comprador_id_clave_idempotencia"
        ),
    )
    op.create_index(
        "ix_pedidos_vence_en_pendientes",
        "pedidos",
        ["vence_en"],
        postgresql_where=sa.text("estado = 'pendiente'"),
    )
    op.create_index("ix_pedidos_vendedor_id_fecha", "pedidos", ["vendedor_id", "fecha"])
    op.create_index("ix_pedidos_comprador_id_estado", "pedidos", ["comprador_id", "estado"])

    op.create_table(
        "pedido_items",
        sa.Column("pedido_id", UUID, nullable=False),
        sa.Column("producto_id", UUID, nullable=False),
        sa.Column("nombre", sa.Text(), nullable=False),
        sa.Column("precio_unitario_cop", sa.Integer(), nullable=False),
        sa.Column("cantidad", sa.Integer(), nullable=False),
        sa.CheckConstraint("cantidad > 0", name="ck_pedido_items_cantidad_positiva"),
        sa.ForeignKeyConstraint(
            ["pedido_id"], ["pedidos.id"], name="fk_pedido_items_pedido_id_pedidos"
        ),
        sa.ForeignKeyConstraint(
            ["producto_id"], ["productos.id"], name="fk_pedido_items_producto_id_productos"
        ),
        sa.PrimaryKeyConstraint("pedido_id", "producto_id", name="pk_pedido_items"),
    )

    op.create_table(
        "transiciones_pedido",
        sa.Column("id", UUID, nullable=False),
        sa.Column("pedido_id", UUID, nullable=False),
        sa.Column("desde", sa.Text()),
        sa.Column("hacia", sa.Text(), nullable=False),
        sa.Column("accion", sa.Text(), nullable=False),
        sa.Column("actor", sa.Text(), nullable=False),
        sa.Column("motivo", sa.Text()),
        sa.Column("en", TZ, nullable=False),
        sa.ForeignKeyConstraint(
            ["pedido_id"], ["pedidos.id"], name="fk_transiciones_pedido_pedido_id_pedidos"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_transiciones_pedido"),
    )
    op.create_index("ix_transiciones_pedido_pedido_id", "transiciones_pedido", ["pedido_id"])


def downgrade() -> None:
    for tabla in ("transiciones_pedido", "pedido_items", "pedidos"):
        op.drop_table(tabla)
