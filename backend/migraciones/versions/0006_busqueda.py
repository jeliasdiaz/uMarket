"""Busqueda: registro de busquedas (metrica y dataset) y clics en resultados.

Revision: 0006
Anterior: 0005
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)
TZ = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "busquedas",
        sa.Column("id", UUID, nullable=False),
        sa.Column("campus_id", sa.Text(), nullable=False),
        sa.Column("usuario_id", UUID),
        sa.Column("texto", sa.Text(), nullable=False),
        sa.Column("interprete", sa.Text(), nullable=False),
        sa.Column("consulta", postgresql.JSONB(), nullable=False),
        sa.Column("anulados", postgresql.ARRAY(sa.Text()), server_default="{}", nullable=False),
        sa.Column("relajados", postgresql.ARRAY(sa.Text()), server_default="{}", nullable=False),
        sa.Column("n_tiendas", sa.Integer(), nullable=False),
        sa.Column("n_productos", sa.Integer(), nullable=False),
        sa.Column("latencia_ms", sa.Integer(), nullable=False),
        sa.Column("tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("costo_usd", sa.Numeric(12, 6)),
        sa.Column("run_id", sa.Text(), nullable=False),
        sa.Column("creada_en", TZ, nullable=False),
        sa.ForeignKeyConstraint(["campus_id"], ["campus.id"], name="fk_busquedas_campus_id_campus"),
        sa.ForeignKeyConstraint(
            ["usuario_id"], ["usuarios.id"], name="fk_busquedas_usuario_id_usuarios"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_busquedas"),
    )
    op.create_index("ix_busquedas_creada_en", "busquedas", ["creada_en"])

    op.create_table(
        "busqueda_clics",
        sa.Column("id", UUID, nullable=False),
        sa.Column("busqueda_id", UUID, nullable=False),
        sa.Column("tienda_id", UUID, nullable=False),
        sa.Column("producto_id", UUID),
        sa.Column("posicion", sa.Integer(), nullable=False),
        sa.Column("creado_en", TZ, nullable=False),
        sa.ForeignKeyConstraint(
            ["busqueda_id"], ["busquedas.id"], name="fk_busqueda_clics_busqueda_id_busquedas"
        ),
        sa.ForeignKeyConstraint(
            ["tienda_id"], ["tiendas.id"], name="fk_busqueda_clics_tienda_id_tiendas"
        ),
        sa.ForeignKeyConstraint(
            ["producto_id"], ["productos.id"], name="fk_busqueda_clics_producto_id_productos"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_busqueda_clics"),
    )
    op.create_index("ix_busqueda_clics_busqueda_id", "busqueda_clics", ["busqueda_id"])


def downgrade() -> None:
    op.drop_table("busqueda_clics")
    op.drop_table("busquedas")
