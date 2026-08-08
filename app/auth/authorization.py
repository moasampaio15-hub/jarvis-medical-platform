from __future__ import annotations

import inspect
import unicodedata
from collections.abc import Callable, Iterable
from functools import wraps
from typing import Any, TypeVar

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.rbac import Permission, Role, RolePermission, UserRole
from app.models.user import User

ROLE_DEFINITIONS: tuple[tuple[str, str, str], ...] = (
    ("admin", "Administrador", "Acesso administrativo completo."),
    ("medico", "Médico", "Acesso aos fluxos clínicos médicos."),
    ("enfermeiro", "Enfermeiro", "Acesso aos fluxos de enfermagem."),
    ("recepcionista", "Recepcionista", "Acesso aos fluxos de recepção e cadastro."),
    ("laboratorio", "Laboratório", "Acesso aos fluxos laboratoriais."),
    ("farmacia", "Farmácia", "Acesso aos fluxos farmacêuticos."),
    ("paciente", "Paciente", "Acesso ao portal do paciente."),
)

PERMISSION_DEFINITIONS: tuple[tuple[str, str, str], ...] = (
    ("admin", "Administração total", "Permissão de compatibilidade para acesso administrativo total."),
    ("medico", "Área médica", "Permissão de compatibilidade para rotas restritas a médicos."),
    ("enfermeiro", "Área de enfermagem", "Permissão de compatibilidade para rotas restritas a enfermeiros."),
    ("recepcionista", "Área de recepção", "Permissão de compatibilidade para rotas restritas a recepcionistas."),
    ("laboratorio", "Área de laboratório", "Permissão de compatibilidade para rotas restritas ao laboratório."),
    ("farmacia", "Área de farmácia", "Permissão de compatibilidade para rotas restritas à farmácia."),
    ("paciente", "Portal do paciente", "Permissão de compatibilidade para rotas restritas a pacientes."),
    ("perfil:ler", "Ler perfil autenticado", "Permite consultar o próprio perfil e contexto de autorização."),
    ("rbac:roles:ler", "Listar papéis", "Permite listar os papéis cadastrados no RBAC."),
    ("rbac:permissoes:ler", "Listar permissões", "Permite listar permissões cadastradas no RBAC."),
    ("rbac:roles:atribuir", "Atribuir papéis", "Permite conceder ou revogar papéis de usuários."),
    ("pacientes:ler", "Ler pacientes", "Permite consultar dados cadastrais de pacientes."),
    ("pacientes:criar", "Criar pacientes", "Permite cadastrar novos pacientes."),
    ("pacientes:atualizar", "Atualizar pacientes", "Permite atualizar dados cadastrais de pacientes."),
    ("patients:read", "Ler pacientes", "Permite consultar cadastros administrativos de pacientes."),
    ("patients:create", "Criar pacientes", "Permite cadastrar pacientes sem dados clínicos."),
    ("patients:update", "Atualizar pacientes", "Permite atualizar dados cadastrais de pacientes."),
    ("patients:deactivate", "Inativar pacientes", "Permite inativar logicamente cadastros de pacientes."),
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

ROLE_PERMISSION_CODES: dict[str, tuple[str, ...]] = {
    "admin": tuple(code for code, _, _ in PERMISSION_DEFINITIONS),
    "medico": (
        "medico",
        "perfil:ler",
        "patients:read",
        "patients:create",
        "patients:update",
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
        "patients:read",
        "patients:create",
        "patients:update",
        "pacientes:ler",
        "consultas:ler",
        "prontuarios:ler",
        "prontuarios:escrever",
        "medicamentos:ler",
    ),
    "recepcionista": (
        "recepcionista",
        "perfil:ler",
        "patients:read",
        "patients:create",
        "patients:update",
        "pacientes:ler",
        "pacientes:criar",
        "pacientes:atualizar",
        "consultas:ler",
        "consultas:gerenciar",
    ),
    "laboratorio": (
        "laboratorio",
        "perfil:ler",
        "patients:read",
        "pacientes:ler",
        "exames:ler",
        "exames:gerenciar",
    ),
    "farmacia": ("farmacia", "perfil:ler", "medicamentos:ler", "medicamentos:dispensar"),
    "paciente": ("paciente", "perfil:ler", "portal_paciente:ler"),
}

DEFAULT_RBAC_ENTRIES = tuple(
    {"codigo": code, "nome": name, "descricao": description}
    for code, name, description in ROLE_DEFINITIONS
)
DEFAULT_ROLE_CODE = "paciente"
ADMIN_PERMISSION_CODE = "admin"
F = TypeVar("F", bound=Callable[..., Any])


def normalize_permission_code(permission: str) -> str:
    normalized = unicodedata.normalize("NFKD", permission.strip().lower())
    return "".join(char for char in normalized if not unicodedata.combining(char))


def _authorization_exception(kind: str, required_values: Iterable[str]) -> HTTPException:
    detail_key = "required_permissions" if kind == "permission" else "required_roles"
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={
            "message": "Permissão insuficiente para executar esta operação.",
            detail_key: sorted(required_values),
        },
    )


def _get_role(db: Session, codigo: str) -> Role | None:
    return db.scalar(select(Role).where(Role.codigo == codigo))


def _get_permission(db: Session, codigo: str) -> Permission | None:
    return db.scalar(select(Permission).where(Permission.codigo == codigo))


def ensure_default_rbac(db: Session) -> None:
    roles_by_code: dict[str, Role] = {}
    permissions_by_code: dict[str, Permission] = {}

    for codigo, nome, descricao in ROLE_DEFINITIONS:
        role = _get_role(db, codigo)
        if role is None:
            role = Role(codigo=codigo, nome=nome, descricao=descricao)
            db.add(role)
            db.flush()
        else:
            role.nome = nome
            role.descricao = descricao
        roles_by_code[codigo] = role

    for codigo, nome, descricao in PERMISSION_DEFINITIONS:
        permission = _get_permission(db, codigo)
        if permission is None:
            permission = Permission(codigo=codigo, nome=nome, descricao=descricao)
            db.add(permission)
            db.flush()
        else:
            permission.nome = nome
            permission.descricao = descricao
        permissions_by_code[codigo] = permission

    for role_code, permission_codes in ROLE_PERMISSION_CODES.items():
        role = roles_by_code[role_code]
        for permission_code in permission_codes:
            permission = permissions_by_code[permission_code]
            if db.get(RolePermission, (role.id, permission.id)) is None:
                db.add(RolePermission(role_id=role.id, permission_id=permission.id))


def assign_role_to_user(db: Session, user: User, role_code: str = DEFAULT_ROLE_CODE) -> None:
    normalized_role_code = normalize_permission_code(role_code)
    role = _get_role(db, normalized_role_code)
    if role is None:
        raise ValueError(f"Role não encontrada: {normalized_role_code}")
    if db.get(UserRole, (user.id, role.id)) is None:
        db.add(UserRole(user_id=user.id, role_id=role.id))


def revoke_role_from_user(db: Session, user: User, role_code: str) -> bool:
    normalized_role_code = normalize_permission_code(role_code)
    role = _get_role(db, normalized_role_code)
    if role is None:
        raise ValueError(f"Role não encontrada: {normalized_role_code}")
    user_role = db.get(UserRole, (user.id, role.id))
    if user_role is None:
        return False
    db.delete(user_role)
    return True


def get_user_role_codes(db: Session, user_id: int) -> set[str]:
    statement = (
        select(Role.codigo)
        .join(UserRole, UserRole.role_id == Role.id)
        .where(UserRole.user_id == user_id)
    )
    return set(db.scalars(statement).all())


def get_user_permission_codes(db: Session, user_id: int) -> set[str]:
    statement = (
        select(Permission.codigo)
        .join(RolePermission, RolePermission.permission_id == Permission.id)
        .join(Role, Role.id == RolePermission.role_id)
        .join(UserRole, UserRole.role_id == Role.id)
        .where(UserRole.user_id == user_id)
    )
    return set(db.scalars(statement).all())


def load_user_authorization_context(user: User, db: Session) -> User:
    user.role_codes = get_user_role_codes(db, user.id)
    user.permission_codes = get_user_permission_codes(db, user.id)
    return user


def _user_role_codes(user: User, db: Session) -> set[str]:
    role_codes = getattr(user, "role_codes", None)
    if role_codes is None:
        role_codes = get_user_role_codes(db, user.id)
        user.role_codes = role_codes
    return set(role_codes)


def _user_permission_codes(user: User, db: Session) -> set[str]:
    permission_codes = getattr(user, "permission_codes", None)
    if permission_codes is None:
        permission_codes = get_user_permission_codes(db, user.id)
        user.permission_codes = permission_codes
    return set(permission_codes)


def user_has_roles(user: User, roles: Iterable[str], db: Session, *, require_all: bool = False) -> bool:
    required_roles = {normalize_permission_code(role) for role in roles}
    if not required_roles:
        raise ValueError("Informe pelo menos um papel para autorização.")
    if user.superuser:
        return True
    user_roles = _user_role_codes(user, db)
    if ADMIN_PERMISSION_CODE in user_roles:
        return True
    return required_roles.issubset(user_roles) if require_all else bool(required_roles & user_roles)


def user_has_permissions(
    user: User,
    permissions: Iterable[str],
    db: Session,
    *,
    require_all: bool = False,
) -> bool:
    required_permissions = {normalize_permission_code(permission) for permission in permissions}
    if not required_permissions:
        raise ValueError("Informe pelo menos uma permissão para autorização.")
    if user.superuser:
        return True
    user_permissions = _user_permission_codes(user, db)
    user_roles = _user_role_codes(user, db)
    if ADMIN_PERMISSION_CODE in user_permissions or ADMIN_PERMISSION_CODE in user_roles:
        return True
    return required_permissions.issubset(user_permissions) if require_all else bool(required_permissions & user_permissions)


def assert_user_has_roles(user: User, roles: Iterable[str], db: Session, *, require_all: bool = False) -> None:
    required_roles = {normalize_permission_code(role) for role in roles}
    if not user_has_roles(user, required_roles, db, require_all=require_all):
        raise _authorization_exception("role", required_roles)


def assert_user_has_permissions(
    user: User,
    permissions: Iterable[str],
    db: Session,
    *,
    require_all: bool = False,
) -> None:
    required_permissions = {normalize_permission_code(permission) for permission in permissions}
    if not user_has_permissions(user, required_permissions, db, require_all=require_all):
        raise _authorization_exception("permission", required_permissions)


def requires_permission(*permissions: str, require_all: bool = False) -> Callable[[F], F]:
    required_permissions = tuple(normalize_permission_code(permission) for permission in permissions)
    if not required_permissions:
        raise ValueError("Informe pelo menos uma permissão para autorização.")

    def decorator(func: F) -> F:
        signature = inspect.signature(func)

        def _authorize(args: tuple[Any, ...], kwargs: dict[str, Any]) -> None:
            bound = signature.bind_partial(*args, **kwargs)
            user = bound.arguments.get("current_user") or bound.arguments.get("user")
            db = bound.arguments.get("db") or bound.arguments.get("session")
            if not isinstance(user, User) or not isinstance(db, Session):
                raise RuntimeError(
                    "Decorators de autorização exigem argumentos 'current_user'/'user' e "
                    "'db'/'session'. Para endpoints FastAPI, prefira Depends(require_permission(...))."
                )
            assert_user_has_permissions(user, required_permissions, db, require_all=require_all)

        if inspect.iscoroutinefunction(func):

            @wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                _authorize(args, kwargs)
                return await func(*args, **kwargs)

            async_wrapper.__signature__ = signature  # type: ignore[attr-defined]
            return async_wrapper  # type: ignore[return-value]

        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            _authorize(args, kwargs)
            return func(*args, **kwargs)

        wrapper.__signature__ = signature  # type: ignore[attr-defined]
        return wrapper  # type: ignore[return-value]

    return decorator


authorization_required = requires_permission
