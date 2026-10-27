"""Plataforma: extensiones, busqueda en espanol sin tildes, outbox y trazas de IA.

Revision: 0001
Anterior: ninguna
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS unaccent")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    # Texto completo en espanol que ignora tildes: "cafe" encuentra "café".
    op.execute("CREATE TEXT SEARCH CONFIGURATION es_sin_tildes (COPY = spanish)")
    op.execute(
        "ALTER TEXT SEARCH CONFIGURATION es_sin_tildes "
        "ALTER MAPPING FOR hword, hword_part, word WITH unaccent, spanish_stem"
    )

    op.create_table(
        "eventos_salida",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tipo", sa.Text(), nullable=False),
        sa.Column("datos", postgresql.JSONB(), nullable=False),
        sa.Column("ocurrido_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "creado_en", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("procesado_en", sa.DateTime(timezone=True)),
        sa.Column("intentos", sa.Integer(), server_default="0", nullable=False),
        sa.Column("ultimo_error", sa.Text()),
        sa.PrimaryKeyConstraint("id", name="pk_eventos_salida"),
    )
    op.create_index(
        "ix_eventos_salida_pendientes",
        "eventos_salida",
        ["creado_en"],
        postgresql_where=sa.text("procesado_en IS NULL"),
    )

    op.create_table(
        "trazas_ia",
        sa.Column("run_id", sa.Text(), nullable=False),
        sa.Column("componente", sa.Text(), nullable=False),
        sa.Column("modelo", sa.Text(), server_default="", nullable=False),
        sa.Column("proveedor", sa.Text(), server_default="", nullable=False),
        sa.Column("prompt_version", sa.Text(), server_default="", nullable=False),
        sa.Column("tokens_total", sa.Integer(), server_default="0", nullable=False),
        sa.Column("costo_usd", sa.Numeric(12, 6)),
        sa.Column("duracion_s", sa.Numeric(10, 4), server_default="0", nullable=False),
        sa.Column("traza", postgresql.JSONB(), nullable=False),
        sa.Column(
            "creado_en", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("run_id", name="pk_trazas_ia"),
    )


def downgrade() -> None:
    op.drop_table("trazas_ia")
    op.drop_index("ix_eventos_salida_pendientes", table_name="eventos_salida")
    op.drop_table("eventos_salida")
    op.execute("DROP TEXT SEARCH CONFIGURATION IF EXISTS es_sin_tildes")
    op.execute("DROP EXTENSION IF EXISTS pg_trgm")
    op.execute("DROP EXTENSION IF EXISTS unaccent")
