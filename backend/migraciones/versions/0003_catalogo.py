"""Catalogo: tiendas, productos (con busqueda de texto y trigramas), turnos y stock.

Revision: 0003
Anterior: 0002
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)
CATEGORIAS = ("empanadas", "arepas", "almuerzos", "postres", "bebidas", "snacks", "frutas", "otros")


def upgrade() -> None:
    op.create_table(
        "tiendas",
        sa.Column("id", UUID, nullable=False),
        sa.Column("campus_id", sa.Text(), nullable=False),
        sa.Column("vendedor_id", UUID, nullable=False),
        sa.Column("nombre", sa.Text(), nullable=False),
        sa.Column("slug", sa.Text(), nullable=False),
        sa.Column("descripcion", sa.Text(), server_default="", nullable=False),
        sa.Column("activa", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("creada_en", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["campus_id"], ["campus.id"], name="fk_tiendas_campus_id_campus"),
        sa.ForeignKeyConstraint(
            ["vendedor_id"], ["usuarios.id"], name="fk_tiendas_vendedor_id_usuarios"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_tiendas"),
        sa.UniqueConstraint("vendedor_id", name="uq_tiendas_vendedor_id"),
        sa.UniqueConstraint("slug", name="uq_tiendas_slug"),
    )
    op.create_index("ix_tiendas_campus_id", "tiendas", ["campus_id"])

    categorias = ", ".join(f"'{c}'" for c in CATEGORIAS)
    op.create_table(
        "productos",
        sa.Column("id", UUID, nullable=False),
        sa.Column("tienda_id", UUID, nullable=False),
        sa.Column("nombre", sa.Text(), nullable=False),
        sa.Column("nombre_normalizado", sa.Text(), nullable=False),
        sa.Column("descripcion", sa.Text(), server_default="", nullable=False),
        sa.Column("categoria", sa.Text(), nullable=False),
        sa.Column("etiquetas", postgresql.ARRAY(sa.Text()), server_default="{}", nullable=False),
        sa.Column("precio_cop", sa.Integer(), nullable=False),
        sa.Column("activo", sa.Boolean(), server_default="true", nullable=False),
        sa.Column(
            "busqueda",
            postgresql.TSVECTOR(),
            sa.Computed(
                "to_tsvector('es_sin_tildes'::regconfig, nombre || ' ' || descripcion)",
                persisted=True,
            ),
        ),
        sa.CheckConstraint(f"categoria IN ({categorias})", name="ck_productos_categoria_valida"),
        sa.CheckConstraint("precio_cop > 0", name="ck_productos_precio_positivo"),
        sa.ForeignKeyConstraint(
            ["tienda_id"], ["tiendas.id"], name="fk_productos_tienda_id_tiendas"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_productos"),
    )
    op.create_index("ix_productos_tienda_id", "productos", ["tienda_id"])
    op.create_index("ix_productos_busqueda", "productos", ["busqueda"], postgresql_using="gin")
    op.create_index(
        "ix_productos_nombre_trgm",
        "productos",
        ["nombre_normalizado"],
        postgresql_using="gin",
        postgresql_ops={"nombre_normalizado": "gin_trgm_ops"},
    )

    op.create_table(
        "turnos",
        sa.Column("id", UUID, nullable=False),
        sa.Column("tienda_id", UUID, nullable=False),
        sa.Column("fecha", sa.Date(), nullable=False),
        sa.Column("franja_id", sa.Text(), nullable=False),
        sa.Column("punto_id", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["tienda_id"], ["tiendas.id"], name="fk_turnos_tienda_id_tiendas"),
        sa.ForeignKeyConstraint(["franja_id"], ["franjas.id"], name="fk_turnos_franja_id_franjas"),
        sa.ForeignKeyConstraint(
            ["punto_id"], ["puntos_encuentro.id"], name="fk_turnos_punto_id_puntos_encuentro"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_turnos"),
        sa.UniqueConstraint(
            "tienda_id", "fecha", "franja_id", name="uq_turnos_tienda_id_fecha_franja_id"
        ),
    )
    op.create_index("ix_turnos_fecha_franja_id", "turnos", ["fecha", "franja_id"])

    op.create_table(
        "stock_turno",
        sa.Column("turno_id", UUID, nullable=False),
        sa.Column("producto_id", UUID, nullable=False),
        sa.Column("total", sa.Integer(), nullable=False),
        sa.Column("reservado", sa.Integer(), server_default="0", nullable=False),
        sa.CheckConstraint(
            "reservado >= 0 AND reservado <= total", name="ck_stock_turno_reserva_dentro_del_total"
        ),
        sa.ForeignKeyConstraint(["turno_id"], ["turnos.id"], name="fk_stock_turno_turno_id_turnos"),
        sa.ForeignKeyConstraint(
            ["producto_id"], ["productos.id"], name="fk_stock_turno_producto_id_productos"
        ),
        sa.PrimaryKeyConstraint("turno_id", "producto_id", name="pk_stock_turno"),
    )


def downgrade() -> None:
    for tabla in ("stock_turno", "turnos", "productos", "tiendas"):
        op.drop_table(tabla)
