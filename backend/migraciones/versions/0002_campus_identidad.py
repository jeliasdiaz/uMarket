"""Campus (puntos y franjas) e identidad (usuarios, consentimientos, codigos, sesiones).

Revision: 0002
Anterior: 0001
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

AHORA = sa.func.now()


def upgrade() -> None:
    op.create_table(
        "campus",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("nombre", sa.Text(), nullable=False),
        sa.Column("zona_horaria", sa.Text(), server_default="America/Bogota", nullable=False),
        sa.Column(
            "dominios_correo", postgresql.ARRAY(sa.Text()), server_default="{}", nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name="pk_campus"),
    )
    op.create_table(
        "puntos_encuentro",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("campus_id", sa.Text(), nullable=False),
        sa.Column("nombre", sa.Text(), nullable=False),
        sa.Column("descripcion", sa.Text(), server_default="", nullable=False),
        sa.Column("foto_url", sa.Text()),
        sa.Column("alias", postgresql.ARRAY(sa.Text()), server_default="{}", nullable=False),
        sa.Column("activo", sa.Boolean(), server_default="true", nullable=False),
        sa.ForeignKeyConstraint(
            ["campus_id"], ["campus.id"], name="fk_puntos_encuentro_campus_id_campus"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_puntos_encuentro"),
    )
    op.create_index("ix_puntos_encuentro_campus_id", "puntos_encuentro", ["campus_id"])
    op.create_table(
        "franjas",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("campus_id", sa.Text(), nullable=False),
        sa.Column("hora_inicio", sa.Time(), nullable=False),
        sa.Column("hora_fin", sa.Time(), nullable=False),
        sa.CheckConstraint("hora_fin > hora_inicio", name="ck_franjas_orden_horas"),
        sa.ForeignKeyConstraint(["campus_id"], ["campus.id"], name="fk_franjas_campus_id_campus"),
        sa.PrimaryKeyConstraint("id", name="pk_franjas"),
    )
    op.create_index("ix_franjas_campus_id", "franjas", ["campus_id"])

    op.create_table(
        "usuarios",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("campus_id", sa.Text(), nullable=False),
        sa.Column("correo", sa.Text(), nullable=False),
        sa.Column("nombre", sa.Text(), nullable=False),
        sa.Column("creado_en", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["campus_id"], ["campus.id"], name="fk_usuarios_campus_id_campus"),
        sa.PrimaryKeyConstraint("id", name="pk_usuarios"),
        sa.UniqueConstraint("correo", name="uq_usuarios_correo"),
    )
    op.create_index("ix_usuarios_campus_id", "usuarios", ["campus_id"])
    op.create_table(
        "consentimientos",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("usuario_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version_terminos", sa.Text(), nullable=False),
        sa.Column("aceptado_en", sa.DateTime(timezone=True), server_default=AHORA, nullable=False),
        sa.ForeignKeyConstraint(
            ["usuario_id"], ["usuarios.id"], name="fk_consentimientos_usuario_id_usuarios"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_consentimientos"),
    )
    op.create_index("ix_consentimientos_usuario_id", "consentimientos", ["usuario_id"])
    op.create_table(
        "codigos_acceso",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("correo", sa.Text(), nullable=False),
        sa.Column("codigo_huella", sa.Text(), nullable=False),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=AHORA, nullable=False),
        sa.Column("expira_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("intentos", sa.Integer(), server_default="0", nullable=False),
        sa.Column("usado_en", sa.DateTime(timezone=True)),
        sa.PrimaryKeyConstraint("id", name="pk_codigos_acceso"),
    )
    op.create_index("ix_codigos_acceso_correo_creado_en", "codigos_acceso", ["correo", "creado_en"])
    op.create_table(
        "sesiones",
        sa.Column("token_huella", sa.Text(), nullable=False),
        sa.Column("usuario_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=AHORA, nullable=False),
        sa.Column("expira_en", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["usuario_id"], ["usuarios.id"], name="fk_sesiones_usuario_id_usuarios"
        ),
        sa.PrimaryKeyConstraint("token_huella", name="pk_sesiones"),
    )
    op.create_index("ix_sesiones_usuario_id", "sesiones", ["usuario_id"])


def downgrade() -> None:
    for tabla in ("sesiones", "codigos_acceso", "consentimientos", "usuarios"):
        op.drop_table(tabla)
    for tabla in ("franjas", "puntos_encuentro", "campus"):
        op.drop_table(tabla)
