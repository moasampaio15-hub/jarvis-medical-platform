"""create rbac tables

Revision ID: 202608061701
Revises: 202608061645
Create Date: 2026-08-06 17:01:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "202608061701"
down_revision: str | None = "202608061645"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DEFAULT_RBAC_ENTRIES = (
    (1, "admin", "Administrador", "Acesso administrativo completo."),
    (2, "medico", "Médico", "Acesso aos fluxos clínicos médicos."),
    (3, "enfermeiro", "Enfermeiro", "Acesso aos fluxos de enfermagem."),
    (4, "recepcionista", "Recepcionista", "Acesso aos fluxos de recepção e cadastro."),
    (5, "laboratorio", "Laboratório", "Acesso aos fluxos laboratoriais."),
    (6, "farmacia", "Farmácia", "Acesso aos fluxos farmacêuticos."),
    (7, "paciente", "Paciente", "Acesso ao portal do paciente."),
)


def upgrade() -> None:
    op.create_table(
        "roles",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("codigo", sa.String(length=64), nullable=False),
        sa.Column("nome", sa.String(length=120), nullable=False),
        sa.Column("descricao", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_roles_codigo"), "roles", ["codigo"], unique=True)

    op.create_table(
        "permissions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("codigo", sa.String(length=64), nullable=False),
        sa.Column("nome", sa.String(length=120), nullable=False),
        sa.Column("descricao", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_permissions_codigo"), "permissions", ["codigo"], unique=True)

    op.create_table(
        "role_permissions",
        sa.Column("role_id", sa.Integer(), nullable=False),
        sa.Column("permission_id", sa.Integer(), nullable=False),
        sa.Column("granted_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["permission_id"], ["permissions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("role_id", "permission_id"),
        sa.UniqueConstraint("role_id", "permission_id", name="uq_role_permissions_role_permission"),
    )

    op.create_table(
        "user_roles",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("role_id", sa.Integer(), nullable=False),
        sa.Column("assigned_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "role_id"),
        sa.UniqueConstraint("user_id", "role_id", name="uq_user_roles_user_role"),
    )

    roles_table = sa.table(
        "roles",
        sa.column("id", sa.Integer),
        sa.column("codigo", sa.String),
        sa.column("nome", sa.String),
        sa.column("descricao", sa.String),
    )
    permissions_table = sa.table(
        "permissions",
        sa.column("id", sa.Integer),
        sa.column("codigo", sa.String),
        sa.column("nome", sa.String),
        sa.column("descricao", sa.String),
    )
    role_permissions_table = sa.table(
        "role_permissions",
        sa.column("role_id", sa.Integer),
        sa.column("permission_id", sa.Integer),
    )

    op.bulk_insert(
        roles_table,
        [
            {"id": id_, "codigo": codigo, "nome": nome, "descricao": descricao}
            for id_, codigo, nome, descricao in DEFAULT_RBAC_ENTRIES
        ],
    )
    op.bulk_insert(
        permissions_table,
        [
            {"id": id_, "codigo": codigo, "nome": nome, "descricao": descricao}
            for id_, codigo, nome, descricao in DEFAULT_RBAC_ENTRIES
        ],
    )
    op.bulk_insert(
        role_permissions_table,
        [
            {"role_id": 1, "permission_id": permission_id}
            for permission_id, *_ in DEFAULT_RBAC_ENTRIES
        ]
        + [
            {"role_id": id_, "permission_id": id_}
            for id_, *_ in DEFAULT_RBAC_ENTRIES
            if id_ != 1
        ],
    )


def downgrade() -> None:
    op.drop_table("user_roles")
    op.drop_table("role_permissions")
    op.drop_index(op.f("ix_permissions_codigo"), table_name="permissions")
    op.drop_table("permissions")
    op.drop_index(op.f("ix_roles_codigo"), table_name="roles")
    op.drop_table("roles")
