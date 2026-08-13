"""create prescriptions tables

Revision ID: 202608131608
Revises: 202608131100
Create Date: 2026-08-13 16:08:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "202608131608"
down_revision: str | None = "202608131100"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PRESCRIPTION_PERMISSIONS = (
    ("medicamentos:escrever", "Escrever medicamentos", "Permite criar e atualizar prescrições de medicamentos."),
)

ROLE_PERMISSION_CODES = {
    "admin": ("medicamentos:escrever",),
    "medico": ("medicamentos:escrever",),
    "enfermeiro": ("medicamentos:escrever",),
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
        "prescriptions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("patient_id", sa.Integer(), nullable=False),
        sa.Column("professional_id", sa.Integer(), nullable=False),
        sa.Column("appointment_id", sa.Integer(), nullable=True),
        sa.Column("medical_record_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=32), server_default="draft", nullable=False),
        sa.Column("observacoes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "status IN ('draft', 'active', 'completed', 'canceled')",
            name="ck_prescriptions_status",
        ),
        sa.ForeignKeyConstraint(["appointment_id"], ["appointments.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["medical_record_id"], ["medical_records.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["professional_id"], ["health_professionals.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_prescriptions_appointment_id", "prescriptions", ["appointment_id"], unique=False)
    op.create_index("ix_prescriptions_medical_record_id", "prescriptions", ["medical_record_id"], unique=False)
    op.create_index("ix_prescriptions_patient_id", "prescriptions", ["patient_id"], unique=False)
    op.create_index("ix_prescriptions_professional_id", "prescriptions", ["professional_id"], unique=False)
    op.create_index("ix_prescriptions_status", "prescriptions", ["status"], unique=False)
    op.create_index(
        "ix_prescriptions_patient_created",
        "prescriptions",
        ["patient_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_prescriptions_professional_created",
        "prescriptions",
        ["professional_id", "created_at"],
        unique=False,
    )

    op.create_table(
        "prescription_items",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("prescription_id", sa.Integer(), nullable=False),
        sa.Column("medicamento", sa.String(length=255), nullable=False),
        sa.Column("apresentacao", sa.String(length=255), nullable=False),
        sa.Column("dose", sa.String(length=120), nullable=False),
        sa.Column("via", sa.String(length=64), nullable=False),
        sa.Column("frequencia", sa.String(length=120), nullable=False),
        sa.Column("duracao", sa.String(length=120), nullable=False),
        sa.Column("orientacoes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["prescription_id"], ["prescriptions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_prescription_items_prescription_id",
        "prescription_items",
        ["prescription_id"],
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
        for codigo, nome, descricao in PRESCRIPTION_PERMISSIONS
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
    permission_codes = [codigo for codigo, _, _ in PRESCRIPTION_PERMISSIONS]
    permission_ids = list(
        bind.scalars(sa.select(permissions.c.id).where(permissions.c.codigo.in_(permission_codes))).all()
    )
    if permission_ids:
        bind.execute(role_permissions.delete().where(role_permissions.c.permission_id.in_(permission_ids)))
    bind.execute(permissions.delete().where(permissions.c.codigo.in_(permission_codes)))

    op.drop_index("ix_prescription_items_prescription_id", table_name="prescription_items")
    op.drop_table("prescription_items")
    op.drop_index("ix_prescriptions_professional_created", table_name="prescriptions")
    op.drop_index("ix_prescriptions_patient_created", table_name="prescriptions")
    op.drop_index("ix_prescriptions_status", table_name="prescriptions")
    op.drop_index("ix_prescriptions_professional_id", table_name="prescriptions")
    op.drop_index("ix_prescriptions_patient_id", table_name="prescriptions")
    op.drop_index("ix_prescriptions_medical_record_id", table_name="prescriptions")
    op.drop_index("ix_prescriptions_appointment_id", table_name="prescriptions")
    op.drop_table("prescriptions")
