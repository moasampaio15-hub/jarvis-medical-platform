"""create patients table

Revision ID: 202608071705
Revises: 202608071636
Create Date: 2026-08-07 17:05:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "202608071705"
down_revision: str | None = "202608071636"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PATIENT_PERMISSIONS = (
    ("patients:read", "Ler pacientes", "Permite consultar cadastros administrativos de pacientes."),
    ("patients:create", "Criar pacientes", "Permite cadastrar pacientes sem dados clínicos."),
    ("patients:update", "Atualizar pacientes", "Permite atualizar dados cadastrais de pacientes."),
    ("patients:deactivate", "Inativar pacientes", "Permite inativar logicamente cadastros de pacientes."),
)

ROLE_PERMISSION_CODES = {
    "admin": tuple(code for code, _, _ in PATIENT_PERMISSIONS),
    "medico": ("patients:read", "patients:create", "patients:update"),
    "enfermeiro": ("patients:read", "patients:create", "patients:update"),
    "recepcionista": ("patients:read", "patients:create", "patients:update"),
    "laboratorio": ("patients:read",),
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
        "patients",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("nome_completo", sa.String(length=255), nullable=False),
        sa.Column("nome_social", sa.String(length=255), nullable=True),
        sa.Column("data_nascimento", sa.Date(), nullable=True),
        sa.Column("sexo", sa.String(length=32), nullable=True),
        sa.Column("cpf", sa.String(length=11), nullable=True),
        sa.Column("rg", sa.String(length=32), nullable=True),
        sa.Column("cns", sa.String(length=15), nullable=True),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("telefone", sa.String(length=32), nullable=True),
        sa.Column("telefone_secundario", sa.String(length=32), nullable=True),
        sa.Column("nome_mae", sa.String(length=255), nullable=True),
        sa.Column("nome_pai", sa.String(length=255), nullable=True),
        sa.Column("estado_civil", sa.String(length=64), nullable=True),
        sa.Column("profissao", sa.String(length=120), nullable=True),
        sa.Column("cep", sa.String(length=8), nullable=True),
        sa.Column("logradouro", sa.String(length=255), nullable=True),
        sa.Column("numero", sa.String(length=32), nullable=True),
        sa.Column("complemento", sa.String(length=120), nullable=True),
        sa.Column("bairro", sa.String(length=120), nullable=True),
        sa.Column("cidade", sa.String(length=120), nullable=True),
        sa.Column("estado", sa.String(length=2), nullable=True),
        sa.Column("ativo", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_patients_nome_completo", "patients", ["nome_completo"], unique=False)
    op.create_index("ix_patients_cpf", "patients", ["cpf"], unique=True)
    op.create_index("ix_patients_cns", "patients", ["cns"], unique=True)

    bind = op.get_bind()
    roles, permissions, role_permissions = _tables()
    role_ids = {
        code: bind.scalar(sa.select(roles.c.id).where(roles.c.codigo == code))
        for code in ROLE_PERMISSION_CODES
    }
    permission_ids = {
        codigo: _upsert_permission(bind, permissions, codigo, nome, descricao)
        for codigo, nome, descricao in PATIENT_PERMISSIONS
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
    permission_codes = [codigo for codigo, _, _ in PATIENT_PERMISSIONS]
    permission_ids = list(
        bind.scalars(sa.select(permissions.c.id).where(permissions.c.codigo.in_(permission_codes))).all()
    )
    if permission_ids:
        bind.execute(role_permissions.delete().where(role_permissions.c.permission_id.in_(permission_ids)))
    bind.execute(permissions.delete().where(permissions.c.codigo.in_(permission_codes)))

    op.drop_index("ix_patients_cns", table_name="patients")
    op.drop_index("ix_patients_cpf", table_name="patients")
    op.drop_index("ix_patients_nome_completo", table_name="patients")
    op.drop_table("patients")
