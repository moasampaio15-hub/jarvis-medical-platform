"""create exam orders tables

Revision ID: 202608131720
Revises: 202608131608
Create Date: 2026-08-13 17:20:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "202608131720"
down_revision: str | None = "202608131608"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

EXAM_PERMISSIONS = (
    ("exames:ler", "Ler exames", "Permite consultar pedidos e resultados de exames."),
    ("exames:gerenciar", "Gerenciar exames", "Permite criar, processar e publicar resultados de exames."),
)

ROLE_PERMISSION_CODES = {
    "medico": ("exames:gerenciar",),
    "enfermeiro": ("exames:ler", "exames:gerenciar"),
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
        "exam_orders",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("patient_id", sa.Integer(), nullable=False),
        sa.Column("professional_id", sa.Integer(), nullable=False),
        sa.Column("appointment_id", sa.Integer(), nullable=True),
        sa.Column("medical_record_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=32), server_default="draft", nullable=False),
        sa.Column("prioridade", sa.String(length=32), server_default="rotina", nullable=False),
        sa.Column("justificativa", sa.Text(), nullable=True),
        sa.Column("observacoes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "status IN ('draft', 'requested', 'completed', 'canceled')",
            name="ck_exam_orders_status",
        ),
        sa.CheckConstraint("prioridade IN ('rotina', 'urgente')", name="ck_exam_orders_prioridade"),
        sa.ForeignKeyConstraint(["appointment_id"], ["appointments.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["medical_record_id"], ["medical_records.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["professional_id"], ["health_professionals.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_exam_orders_appointment_id", "exam_orders", ["appointment_id"], unique=False)
    op.create_index("ix_exam_orders_medical_record_id", "exam_orders", ["medical_record_id"], unique=False)
    op.create_index("ix_exam_orders_patient_id", "exam_orders", ["patient_id"], unique=False)
    op.create_index("ix_exam_orders_prioridade", "exam_orders", ["prioridade"], unique=False)
    op.create_index("ix_exam_orders_professional_id", "exam_orders", ["professional_id"], unique=False)
    op.create_index("ix_exam_orders_status", "exam_orders", ["status"], unique=False)
    op.create_index(
        "ix_exam_orders_patient_created",
        "exam_orders",
        ["patient_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_exam_orders_professional_created",
        "exam_orders",
        ["professional_id", "created_at"],
        unique=False,
    )

    op.create_table(
        "exam_order_items",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("exam_order_id", sa.Integer(), nullable=False),
        sa.Column("nome_exame", sa.String(length=255), nullable=False),
        sa.Column("codigo", sa.String(length=64), nullable=True),
        sa.Column("material", sa.String(length=120), nullable=True),
        sa.Column("orientacoes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["exam_order_id"], ["exam_orders.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_exam_order_items_exam_order_id",
        "exam_order_items",
        ["exam_order_id"],
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
        for codigo, nome, descricao in EXAM_PERMISSIONS
    }

    for role_code, permission_codes in ROLE_PERMISSION_CODES.items():
        role_id = role_ids.get(role_code)
        if role_id is None:
            continue
        for permission_code in permission_codes:
            _grant_permission(bind, role_permissions, int(role_id), permission_ids[permission_code])


def downgrade() -> None:
    bind = op.get_bind()
    roles, permissions, role_permissions = _tables()
    role_ids = list(
        bind.scalars(sa.select(roles.c.id).where(roles.c.codigo.in_(ROLE_PERMISSION_CODES))).all()
    )
    permission_codes = [codigo for codigo, _, _ in EXAM_PERMISSIONS]
    permission_ids = list(
        bind.scalars(sa.select(permissions.c.id).where(permissions.c.codigo.in_(permission_codes))).all()
    )
    if role_ids and permission_ids:
        bind.execute(
            role_permissions.delete().where(
                role_permissions.c.role_id.in_(role_ids),
                role_permissions.c.permission_id.in_(permission_ids),
            )
        )

    op.drop_index("ix_exam_order_items_exam_order_id", table_name="exam_order_items")
    op.drop_table("exam_order_items")
    op.drop_index("ix_exam_orders_professional_created", table_name="exam_orders")
    op.drop_index("ix_exam_orders_patient_created", table_name="exam_orders")
    op.drop_index("ix_exam_orders_status", table_name="exam_orders")
    op.drop_index("ix_exam_orders_professional_id", table_name="exam_orders")
    op.drop_index("ix_exam_orders_prioridade", table_name="exam_orders")
    op.drop_index("ix_exam_orders_patient_id", table_name="exam_orders")
    op.drop_index("ix_exam_orders_medical_record_id", table_name="exam_orders")
    op.drop_index("ix_exam_orders_appointment_id", table_name="exam_orders")
    op.drop_table("exam_orders")
