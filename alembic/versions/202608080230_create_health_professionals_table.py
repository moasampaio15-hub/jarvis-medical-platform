"""create health professionals table

Revision ID: 202608080230
Revises: 202608071705
Create Date: 2026-08-08 02:30:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "202608080230"
down_revision: str | None = "202608071705"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

HEALTH_PROFESSIONAL_PERMISSIONS = (
    (
        "health_professionals:read",
        "Ler profissionais de saúde",
        "Permite consultar cadastros administrativos de profissionais de saúde.",
    ),
    (
        "health_professionals:create",
        "Criar profissionais de saúde",
        "Permite cadastrar profissionais de saúde.",
    ),
    (
        "health_professionals:update",
        "Atualizar profissionais de saúde",
        "Permite atualizar cadastros administrativos de profissionais de saúde.",
    ),
    (
        "health_professionals:deactivate",
        "Inativar profissionais de saúde",
        "Permite inativar logicamente cadastros de profissionais de saúde.",
    ),
)

ROLE_PERMISSION_CODES = {
    "admin": tuple(code for code, _, _ in HEALTH_PROFESSIONAL_PERMISSIONS),
    "medico": ("health_professionals:read",),
    "enfermeiro": ("health_professionals:read",),
    "recepcionista": ("health_professionals:read",),
    "laboratorio": ("health_professionals:read",),
    "farmacia": ("health_professionals:read",),
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
        "health_professionals",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("nome_completo", sa.String(length=255), nullable=False),
        sa.Column("nome_social", sa.String(length=255), nullable=True),
        sa.Column("cpf", sa.String(length=11), nullable=True),
        sa.Column("data_nascimento", sa.Date(), nullable=True),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("telefone", sa.String(length=32), nullable=True),
        sa.Column("conselho_tipo", sa.String(length=16), nullable=False),
        sa.Column("conselho_numero", sa.String(length=32), nullable=False),
        sa.Column("conselho_uf", sa.String(length=2), nullable=False),
        sa.Column("especialidade_principal", sa.String(length=120), nullable=True),
        sa.Column("outras_especialidades", sa.JSON(), nullable=True),
        sa.Column("rqe", sa.String(length=32), nullable=True),
        sa.Column("ativo", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "conselho_tipo IN ('CRM', 'COREN', 'CRO', 'CRF', 'CREFITO', 'CRP', 'outro')",
            name="ck_health_professionals_conselho_tipo",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "conselho_numero",
            "conselho_tipo",
            "conselho_uf",
            name="uq_health_professionals_conselho",
        ),
    )
    op.create_index(
        "ix_health_professionals_conselho",
        "health_professionals",
        ["conselho_tipo", "conselho_uf", "conselho_numero"],
        unique=False,
    )
    op.create_index("ix_health_professionals_cpf", "health_professionals", ["cpf"], unique=True)
    op.create_index(
        "ix_health_professionals_nome_completo", "health_professionals", ["nome_completo"], unique=False
    )
    op.create_index("ix_health_professionals_user_id", "health_professionals", ["user_id"], unique=True)

    bind = op.get_bind()
    roles, permissions, role_permissions = _tables()
    role_ids = {
        code: bind.scalar(sa.select(roles.c.id).where(roles.c.codigo == code))
        for code in ROLE_PERMISSION_CODES
    }
    permission_ids = {
        codigo: _upsert_permission(bind, permissions, codigo, nome, descricao)
        for codigo, nome, descricao in HEALTH_PROFESSIONAL_PERMISSIONS
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
    permission_codes = [codigo for codigo, _, _ in HEALTH_PROFESSIONAL_PERMISSIONS]
    permission_ids = list(
        bind.scalars(sa.select(permissions.c.id).where(permissions.c.codigo.in_(permission_codes))).all()
    )
    if permission_ids:
        bind.execute(role_permissions.delete().where(role_permissions.c.permission_id.in_(permission_ids)))
    bind.execute(permissions.delete().where(permissions.c.codigo.in_(permission_codes)))

    op.drop_index("ix_health_professionals_user_id", table_name="health_professionals")
    op.drop_index("ix_health_professionals_nome_completo", table_name="health_professionals")
    op.drop_index("ix_health_professionals_cpf", table_name="health_professionals")
    op.drop_index("ix_health_professionals_conselho", table_name="health_professionals")
    op.drop_table("health_professionals")
