"""seed granular rbac permissions

Revision ID: 202608071636
Revises: 202608061701
Create Date: 2026-08-07 16:36:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "202608071636"
down_revision: str | None = "202608061701"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DEFAULT_ROLES = (
    ("admin", "Administrador", "Acesso administrativo completo."),
    ("medico", "Médico", "Acesso aos fluxos clínicos médicos."),
    ("enfermeiro", "Enfermeiro", "Acesso aos fluxos de enfermagem."),
    ("recepcionista", "Recepcionista", "Acesso aos fluxos de recepção e cadastro."),
    ("laboratorio", "Laboratório", "Acesso aos fluxos laboratoriais."),
    ("farmacia", "Farmácia", "Acesso aos fluxos farmacêuticos."),
    ("paciente", "Paciente", "Acesso ao portal do paciente."),
)

GRANULAR_PERMISSIONS = (
    ("perfil:ler", "Ler perfil autenticado", "Permite consultar o próprio perfil e contexto de autorização."),
    ("rbac:roles:ler", "Listar papéis", "Permite listar os papéis cadastrados no RBAC."),
    ("rbac:permissoes:ler", "Listar permissões", "Permite listar permissões cadastradas no RBAC."),
    ("rbac:roles:atribuir", "Atribuir papéis", "Permite conceder ou revogar papéis de usuários."),
    ("pacientes:ler", "Ler pacientes", "Permite consultar dados cadastrais de pacientes."),
    ("pacientes:criar", "Criar pacientes", "Permite cadastrar novos pacientes."),
    ("pacientes:atualizar", "Atualizar pacientes", "Permite atualizar dados cadastrais de pacientes."),
    ("consultas:ler", "Ler consultas", "Permite consultar agendamentos e atendimentos."),
    ("consultas:gerenciar", "Gerenciar consultas", "Permite criar, reagendar e cancelar consultas."),
    ("prontuarios:ler", "Ler prontuários", "Permite consultar prontuários clínicos."),
    ("prontuarios:escrever", "Escrever prontuários", "Permite registrar evoluções e anotações clínicas."),
    ("exames:ler", "Ler exames", "Permite consultar pedidos e resultados de exames."),
    ("exames:gerenciar", "Gerenciar exames", "Permite criar, processar e publicar resultados de exames."),
    ("medicamentos:ler", "Ler medicamentos", "Permite consultar prescrições e medicamentos."),
    ("medicamentos:dispensar", "Dispensar medicamentos", "Permite registrar dispensação de medicamentos."),
    ("portal_paciente:ler", "Ler portal do paciente", "Permite consultar informações próprias no portal do paciente."),
)

ROLE_PERMISSION_CODES = {
    "medico": (
        "medico",
        "perfil:ler",
        "pacientes:ler",
        "consultas:ler",
        "consultas:gerenciar",
        "prontuarios:ler",
        "prontuarios:escrever",
        "exames:ler",
        "medicamentos:ler",
    ),
    "enfermeiro": (
        "enfermeiro",
        "perfil:ler",
        "pacientes:ler",
        "consultas:ler",
        "prontuarios:ler",
        "prontuarios:escrever",
        "medicamentos:ler",
    ),
    "recepcionista": (
        "recepcionista",
        "perfil:ler",
        "pacientes:ler",
        "pacientes:criar",
        "pacientes:atualizar",
        "consultas:ler",
        "consultas:gerenciar",
    ),
    "laboratorio": ("laboratorio", "perfil:ler", "pacientes:ler", "exames:ler", "exames:gerenciar"),
    "farmacia": (
        "farmacia",
        "perfil:ler",
        "pacientes:ler",
        "medicamentos:ler",
        "medicamentos:dispensar",
    ),
    "paciente": ("paciente", "perfil:ler", "portal_paciente:ler"),
}


def _tables() -> tuple[sa.TableClause, sa.TableClause, sa.TableClause]:
    roles = sa.table(
        "roles",
        sa.column("id", sa.Integer),
        sa.column("codigo", sa.String),
        sa.column("nome", sa.String),
        sa.column("descricao", sa.String),
    )
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


def _upsert_role(bind, roles, codigo: str, nome: str, descricao: str) -> int:
    role_id = bind.scalar(sa.select(roles.c.id).where(roles.c.codigo == codigo))
    if role_id is None:
        bind.execute(roles.insert().values(codigo=codigo, nome=nome, descricao=descricao))
        role_id = bind.scalar(sa.select(roles.c.id).where(roles.c.codigo == codigo))
    return int(role_id)


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
        bind.execute(
            role_permissions.insert().values(role_id=role_id, permission_id=permission_id)
        )


def upgrade() -> None:
    bind = op.get_bind()
    roles, permissions, role_permissions = _tables()

    role_ids = {
        codigo: _upsert_role(bind, roles, codigo, nome, descricao)
        for codigo, nome, descricao in DEFAULT_ROLES
    }
    permission_ids = {
        codigo: _upsert_permission(bind, permissions, codigo, nome, descricao)
        for codigo, nome, descricao in GRANULAR_PERMISSIONS
    }

    all_permission_codes = tuple(permission_ids) + tuple(role_ids)
    ROLE_PERMISSION_CODES["admin"] = all_permission_codes

    for role_code, permission_codes in ROLE_PERMISSION_CODES.items():
        role_id = role_ids[role_code]
        for permission_code in permission_codes:
            permission_id = permission_ids.get(permission_code)
            if permission_id is None:
                permission_id = bind.scalar(
                    sa.select(permissions.c.id).where(permissions.c.codigo == permission_code)
                )
            if permission_id is not None:
                _grant_permission(bind, role_permissions, role_id, int(permission_id))


def downgrade() -> None:
    bind = op.get_bind()
    _, permissions, role_permissions = _tables()
    granular_codes = [codigo for codigo, _, _ in GRANULAR_PERMISSIONS]
    granular_permission_ids = list(
        bind.scalars(sa.select(permissions.c.id).where(permissions.c.codigo.in_(granular_codes))).all()
    )
    if granular_permission_ids:
        bind.execute(
            role_permissions.delete().where(
                role_permissions.c.permission_id.in_(granular_permission_ids)
            )
        )
    bind.execute(permissions.delete().where(permissions.c.codigo.in_(granular_codes)))
