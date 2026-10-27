"""Reputacion (calificaciones, metricas por tienda) y suscripciones push.

Revision: 0005
Anterior: 0004
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)
TZ = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "calificaciones",
        sa.Column("id", UUID, nullable=False),
        sa.Column("pedido_id", UUID, nullable=False),
        sa.Column("tienda_id", UUID, nullable=False),
        sa.Column("comprador_id", UUID, nullable=False),
        sa.Column("estrellas", sa.SmallInteger(), nullable=False),
        sa.Column("comentario", sa.Text(), server_default="", nullable=False),
        sa.Column("creada_en", TZ, nullable=False),
        sa.CheckConstraint("estrellas BETWEEN 1 AND 5", name="ck_calificaciones_estrellas_validas"),
        sa.ForeignKeyConstraint(
            ["pedido_id"], ["pedidos.id"], name="fk_calificaciones_pedido_id_pedidos"
        ),
        sa.ForeignKeyConstraint(
            ["tienda_id"], ["tiendas.id"], name="fk_calificaciones_tienda_id_tiendas"
        ),
        sa.ForeignKeyConstraint(
            ["comprador_id"], ["usuarios.id"], name="fk_calificaciones_comprador_id_usuarios"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_calificaciones"),
        sa.UniqueConstraint("pedido_id", name="uq_calificaciones_pedido_id"),
    )
    op.create_index("ix_calificaciones_tienda_id", "calificaciones", ["tienda_id"])

    op.create_table(
        "metricas_tienda",
        sa.Column("tienda_id", UUID, nullable=False),
        sa.Column("resenas", sa.Integer(), server_default="0", nullable=False),
        sa.Column("suma_estrellas", sa.Integer(), server_default="0", nullable=False),
        sa.Column("entregas", sa.Integer(), server_default="0", nullable=False),
        sa.Column("vencidos", sa.Integer(), server_default="0", nullable=False),
        sa.Column("cancelados_por_vendedor", sa.Integer(), server_default="0", nullable=False),
        sa.Column("actualizado_en", TZ, nullable=False),
        sa.ForeignKeyConstraint(
            ["tienda_id"], ["tiendas.id"], name="fk_metricas_tienda_tienda_id_tiendas"
        ),
        sa.PrimaryKeyConstraint("tienda_id", name="pk_metricas_tienda"),
    )

    op.create_table(
        "suscripciones_push",
        sa.Column("endpoint", sa.Text(), nullable=False),
        sa.Column("usuario_id", UUID, nullable=False),
        sa.Column("p256dh", sa.Text(), nullable=False),
        sa.Column("auth", sa.Text(), nullable=False),
        sa.Column("creada_en", TZ, server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["usuario_id"], ["usuarios.id"], name="fk_suscripciones_push_usuario_id_usuarios"
        ),
        sa.PrimaryKeyConstraint("endpoint", name="pk_suscripciones_push"),
    )
    op.create_index("ix_suscripciones_push_usuario_id", "suscripciones_push", ["usuario_id"])


def downgrade() -> None:
    for tabla in ("suscripciones_push", "metricas_tienda", "calificaciones"):
        op.drop_table(tabla)
