"""create clinical diagnoses table

Revision ID: 202608141130
Revises: 202608141030
Create Date: 2026-08-14 11:30:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "202608141130"
down_revision: str | None = "202608141030"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DIAGNOSIS_PERMISSIONS = (
    ("diagnosticos:ler", "Ler diagnósticos", "Permite consultar diagnósticos e problemas clínicos."),
    (
        "diagnosticos:gerenciar",
        "Gerenciar diagnósticos",
        "Permite registrar e atualizar diagnósticos e problemas clínicos.",
    ),
)

ROLE_PERMISSION_CODES = {
    "admin": ("diagnosticos:ler", "diagnosticos:gerenciar"),
    "medico": ("diagnosticos:ler", "diagnosticos:gerenciar"),
    "enfermeiro": ("diagnosticos:ler",),
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
        bind.execute(permissions.update().where(permissions.c.codigo == codigo).values(nome=nome, descricao=descricao))
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
        "clinical_diagnoses",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("patient_id", sa.Integer(), nullable=False),
        sa.Column("professional_id", sa.Integer(), nullable=False),
        sa.Column("appointment_id", sa.Integer(), nullable=True),
        sa.Column("medical_record_id", sa.Integer(), nullable=True),
        sa.Column("cid10_codigo", sa.String(length=16), nullable=True),
        sa.Column("descricao", sa.String(length=255), nullable=False),
        sa.Column("tipo", sa.String(length=32), server_default="hipotese", nullable=False),
        sa.Column("status", sa.String(length=32), server_default="ativo", nullable=False),
        sa.Column("data_inicio", sa.Date(), nullable=True),
        sa.Column("data_resolucao", sa.Date(), nullable=True),
        sa.Column("observacoes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("tipo IN ('hipotese', 'confirmado', 'problema')", name="ck_clinical_diagnoses_tipo"),
        sa.CheckConstraint("status IN ('ativo', 'resolvido')", name="ck_clinical_diagnoses_status"),
        sa.CheckConstraint("data_resolucao IS NULL OR data_inicio IS NULL OR data_resolucao >= data_inicio", name="ck_clinical_diagnoses_date_range"),
        sa.ForeignKeyConstraint(["appointment_id"], ["appointments.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["medical_record_id"], ["medical_records.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["professional_id"], ["health_professionals.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_clinical_diagnoses_appointment_id", "clinical_diagnoses", ["appointment_id"], unique=False)
    op.create_index("ix_clinical_diagnoses_cid10_codigo", "clinical_diagnoses", ["cid10_codigo"], unique=False)
    op.create_index("ix_clinical_diagnoses_medical_record_id", "clinical_diagnoses", ["medical_record_id"], unique=False)
    op.create_index("ix_clinical_diagnoses_patient_id", "clinical_diagnoses", ["patient_id"], unique=False)
    op.create_index("ix_clinical_diagnoses_professional_id", "clinical_diagnoses", ["professional_id"], unique=False)
    op.create_index("ix_clinical_diagnoses_status", "clinical_diagnoses", ["status"], unique=False)
    op.create_index("ix_clinical_diagnoses_tipo", "clinical_diagnoses", ["tipo"], unique=False)
    op.create_index("ix_clinical_diagnoses_patient_status", "clinical_diagnoses", ["patient_id", "status"], unique=False)
    op.create_index("ix_clinical_diagnoses_patient_created", "clinical_diagnoses", ["patient_id", "created_at"], unique=False)
    op.create_index("ix_clinical_diagnoses_professional_created", "clinical_diagnoses", ["professional_id", "created_at"], unique=False)

    bind = op.get_bind()
    roles, permissions, role_permissions = _tables()
    role_ids = {code: bind.scalar(sa.select(roles.c.id).where(roles.c.codigo == code)) for code in ROLE_PERMISSION_CODES}
    permission_ids = {
        codigo: _upsert_permission(bind, permissions, codigo, nome, descricao)
        for codigo, nome, descricao in DIAGNOSIS_PERMISSIONS
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
    permission_codes = [codigo for codigo, _, _ in DIAGNOSIS_PERMISSIONS]
    permission_ids = list(bind.scalars(sa.select(permissions.c.id).where(permissions.c.codigo.in_(permission_codes))).all())
    if permission_ids:
        bind.execute(role_permissions.delete().where(role_permissions.c.permission_id.in_(permission_ids)))
    bind.execute(permissions.delete().where(permissions.c.codigo.in_(permission_codes)))

    op.drop_index("ix_clinical_diagnoses_professional_created", table_name="clinical_diagnoses")
    op.drop_index("ix_clinical_diagnoses_patient_created", table_name="clinical_diagnoses")
    op.drop_index("ix_clinical_diagnoses_patient_status", table_name="clinical_diagnoses")
    op.drop_index("ix_clinical_diagnoses_tipo", table_name="clinical_diagnoses")
    op.drop_index("ix_clinical_diagnoses_status", table_name="clinical_diagnoses")
    op.drop_index("ix_clinical_diagnoses_professional_id", table_name="clinical_diagnoses")
    op.drop_index("ix_clinical_diagnoses_patient_id", table_name="clinical_diagnoses")
    op.drop_index("ix_clinical_diagnoses_medical_record_id", table_name="clinical_diagnoses")
    op.drop_index("ix_clinical_diagnoses_cid10_codigo", table_name="clinical_diagnoses")
    op.drop_index("ix_clinical_diagnoses_appointment_id", table_name="clinical_diagnoses")
    op.drop_table("clinical_diagnoses")
