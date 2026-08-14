"""create patient allergies table

Revision ID: 202608140915
Revises: 202608140301
Create Date: 2026-08-14 09:15:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "202608140915"
down_revision: str | None = "202608140301"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ALLERGY_PERMISSIONS = (
    ("alergias:ler", "Ler alergias", "Permite consultar alergias, intolerâncias e reações adversas."),
    (
        "alergias:gerenciar",
        "Gerenciar alergias",
        "Permite registrar e atualizar alergias, intolerâncias e reações adversas.",
    ),
)

ROLE_PERMISSION_CODES = {
    "admin": ("alergias:ler", "alergias:gerenciar"),
    "medico": ("alergias:ler", "alergias:gerenciar"),
    "enfermeiro": ("alergias:ler", "alergias:gerenciar"),
    "laboratorio": ("alergias:ler",),
    "farmacia": ("alergias:ler",),
}


def _tables() -> tuple[sa.TableClause, sa.TableClause, sa.TableClause]:
    roles = sa.table("roles", sa.column("id", sa.Integer), sa.column("codigo", sa.String))
    permissions = sa.table(
        "permissions",
        sa.column("id", sa.Integer),
        sa.column("codigo", sa.String),
        sa.column("nome", sa.String),
        sa.column("descricao", sa.String),
    )
    role_permissions = sa.table(
        "role_permissions",
        sa.column("role_id", sa.Integer),
        sa.column("permission_id", sa.Integer),
    )
    return roles, permissions, role_permissions


def _upsert_permission(bind, permissions, codigo: str, nome: str, descricao: str) -> int:
    permission_id = bind.scalar(sa.select(permissions.c.id).where(permissions.c.codigo == codigo))
    if permission_id is None:
        bind.execute(permissions.insert().values(codigo=codigo, nome=nome, descricao=descricao))
        permission_id = bind.scalar(sa.select(permissions.c.id).where(permissions.c.codigo == codigo))
    else:
        bind.execute(
            permissions.update()
            .where(permissions.c.codigo == codigo)
            .values(nome=nome, descricao=descricao)
        )
    return int(permission_id)


def _grant_permission(bind, role_permissions, role_id: int, permission_id: int) -> None:
    exists = bind.scalar(
        sa.select(role_permissions.c.role_id).where(
            role_permissions.c.role_id == role_id,
            role_permissions.c.permission_id == permission_id,
        )
    )
    if exists is None:
        bind.execute(role_permissions.insert().values(role_id=role_id, permission_id=permission_id))


def upgrade() -> None:
    op.create_table(
        "patient_allergies",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("patient_id", sa.Integer(), nullable=False),
        sa.Column("professional_id", sa.Integer(), nullable=False),
        sa.Column("medical_record_id", sa.Integer(), nullable=True),
        sa.Column("tipo", sa.String(length=32), server_default="allergy", nullable=False),
        sa.Column("categoria", sa.String(length=32), server_default="unknown", nullable=False),
        sa.Column("substancia", sa.String(length=255), nullable=False),
        sa.Column("reacao", sa.String(length=255), nullable=True),
        sa.Column("gravidade", sa.String(length=32), server_default="unknown", nullable=False),
        sa.Column("status", sa.String(length=32), server_default="active", nullable=False),
        sa.Column("observado_em", sa.Date(), nullable=True),
        sa.Column("observacoes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "tipo IN ('allergy', 'intolerance', 'adverse_reaction', 'unknown')",
            name="ck_patient_allergies_tipo",
        ),
        sa.CheckConstraint(
            "categoria IN ('medication', 'food', 'environment', 'latex', 'other', 'unknown')",
            name="ck_patient_allergies_categoria",
        ),
        sa.CheckConstraint(
            "gravidade IN ('mild', 'moderate', 'severe', 'life_threatening', 'unknown')",
            name="ck_patient_allergies_gravidade",
        ),
        sa.CheckConstraint(
            "status IN ('active', 'inactive', 'entered_in_error')",
            name="ck_patient_allergies_status",
        ),
        sa.ForeignKeyConstraint(["medical_record_id"], ["medical_records.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["professional_id"], ["health_professionals.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_patient_allergies_categoria", "patient_allergies", ["categoria"], unique=False)
    op.create_index("ix_patient_allergies_gravidade", "patient_allergies", ["gravidade"], unique=False)
    op.create_index("ix_patient_allergies_medical_record_id", "patient_allergies", ["medical_record_id"], unique=False)
    op.create_index("ix_patient_allergies_patient_id", "patient_allergies", ["patient_id"], unique=False)
    op.create_index("ix_patient_allergies_professional_id", "patient_allergies", ["professional_id"], unique=False)
    op.create_index("ix_patient_allergies_status", "patient_allergies", ["status"], unique=False)
    op.create_index("ix_patient_allergies_tipo", "patient_allergies", ["tipo"], unique=False)
    op.create_index("ix_patient_allergies_patient_status", "patient_allergies", ["patient_id", "status"], unique=False)
    op.create_index(
        "ix_patient_allergies_patient_substancia",
        "patient_allergies",
        ["patient_id", "substancia"],
        unique=False,
    )
    op.create_index(
        "ix_patient_allergies_professional_created",
        "patient_allergies",
        ["professional_id", "created_at"],
        unique=False,
    )

    bind = op.get_bind()
    roles, permissions, role_permissions = _tables()
    role_ids = {
        code: bind.scalar(sa.select(roles.c.id).where(roles.c.codigo == code))
        for code in ROLE_PERMISSION_CODES
    }
    permission_ids = {
        codigo: _upsert_permission(bind, permissions, codigo, nome, descricao)
        for codigo, nome, descricao in ALLERGY_PERMISSIONS
    }

    for role_code, permission_codes in ROLE_PERMISSION_CODES.items():
        role_id = role_ids.get(role_code)
        if role_id is None:
            continue
        for permission_code in permission_codes:
            _grant_permission(bind, role_permissions, int(role_id), permission_ids[permission_code])


def downgrade() -> None:
    bind = op.get_bind()
    _, permissions, role_permissions = _tables()
    permission_codes = [codigo for codigo, _, _ in ALLERGY_PERMISSIONS]
    permission_ids = list(
        bind.scalars(sa.select(permissions.c.id).where(permissions.c.codigo.in_(permission_codes))).all()
    )
    if permission_ids:
        bind.execute(role_permissions.delete().where(role_permissions.c.permission_id.in_(permission_ids)))
    bind.execute(permissions.delete().where(permissions.c.codigo.in_(permission_codes)))

    op.drop_index("ix_patient_allergies_professional_created", table_name="patient_allergies")
    op.drop_index("ix_patient_allergies_patient_substancia", table_name="patient_allergies")
    op.drop_index("ix_patient_allergies_patient_status", table_name="patient_allergies")
    op.drop_index("ix_patient_allergies_tipo", table_name="patient_allergies")
    op.drop_index("ix_patient_allergies_status", table_name="patient_allergies")
    op.drop_index("ix_patient_allergies_professional_id", table_name="patient_allergies")
    op.drop_index("ix_patient_allergies_patient_id", table_name="patient_allergies")
    op.drop_index("ix_patient_allergies_medical_record_id", table_name="patient_allergies")
    op.drop_index("ix_patient_allergies_gravidade", table_name="patient_allergies")
    op.drop_index("ix_patient_allergies_categoria", table_name="patient_allergies")
    op.drop_table("patient_allergies")
