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

DEFAULT_RBAC_ENTRIES: tuple[dict[str, str], ...] = (
    {"codigo": "admin", "nome": "Administrador", "descricao": "Acesso administrativo completo."},
    {"codigo": "medico", "nome": "Médico", "descricao": "Acesso aos fluxos clínicos médicos."},
    {"codigo": "enfermeiro", "nome": "Enfermeiro", "descricao": "Acesso aos fluxos de enfermagem."},
    {
        "codigo": "recepcionista",
        "nome": "Recepcionista",
        "descricao": "Acesso aos fluxos de recepção e cadastro.",
    },
    {
        "codigo": "laboratorio",
        "nome": "Laboratório",
        "descricao": "Acesso aos fluxos laboratoriais.",
    },
    {"codigo": "farmacia", "nome": "Farmácia", "descricao": "Acesso aos fluxos farmacêuticos."},
    {"codigo": "paciente", "nome": "Paciente", "descricao": "Acesso ao portal do paciente."},
)
DEFAULT_ROLE_CODE = "paciente"
ADMIN_PERMISSION_CODE = "admin"
F = TypeVar("F", bound=Callable[..., Any])


def normalize_permission_code(permission: str) -> str:
    normalized = unicodedata.normalize("NFKD", permission.strip().lower())
    return "".join(char for char in normalized if not unicodedata.combining(char))


def _authorization_exception(required_permissions: Iterable[str]) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={
            "message": "Permissão insuficiente para executar esta operação.",
            "required_permissions": sorted(required_permissions),
        },
    )


def _get_role(db: Session, codigo: str) -> Role | None:
    return db.scalar(select(Role).where(Role.codigo == codigo))


def _get_permission(db: Session, codigo: str) -> Permission | None:
    return db.scalar(select(Permission).where(Permission.codigo == codigo))


def ensure_default_rbac(db: Session) -> None:
    roles_by_code: dict[str, Role] = {}
    permissions_by_code: dict[str, Permission] = {}

    for entry in DEFAULT_RBAC_ENTRIES:
        role = _get_role(db, entry["codigo"])
        if role is None:
            role = Role(**entry)
            db.add(role)
            db.flush()
        roles_by_code[entry["codigo"]] = role

        permission = _get_permission(db, entry["codigo"])
        if permission is None:
            permission = Permission(**entry)
            db.add(permission)
            db.flush()
        permissions_by_code[entry["codigo"]] = permission

    for role_code, role in roles_by_code.items():
        permission_codes = permissions_by_code.keys() if role_code == ADMIN_PERMISSION_CODE else (role_code,)
        for permission_code in permission_codes:
            permission = permissions_by_code[permission_code]
            role_permission = db.get(RolePermission, (role.id, permission.id))
            if role_permission is None:
                db.add(RolePermission(role_id=role.id, permission_id=permission.id))


def assign_role_to_user(db: Session, user: User, role_code: str = DEFAULT_ROLE_CODE) -> None:
    normalized_role_code = normalize_permission_code(role_code)
    role = _get_role(db, normalized_role_code)
    if role is None:
        raise ValueError(f"Role padrão não encontrada: {normalized_role_code}")
    if db.get(UserRole, (user.id, role.id)) is None:
        db.add(UserRole(user_id=user.id, role_id=role.id))


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

    user_permissions = get_user_permission_codes(db, user.id)
    user_roles = get_user_role_codes(db, user.id)
    if ADMIN_PERMISSION_CODE in user_permissions or ADMIN_PERMISSION_CODE in user_roles:
        return True

    if require_all:
        return required_permissions.issubset(user_permissions)
    return bool(required_permissions.intersection(user_permissions))


def assert_user_has_permissions(
    user: User,
    permissions: Iterable[str],
    db: Session,
    *,
    require_all: bool = False,
) -> None:
    required_permissions = {normalize_permission_code(permission) for permission in permissions}
    if not user_has_permissions(user, required_permissions, db, require_all=require_all):
        raise _authorization_exception(required_permissions)


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
                    "Decorators de autorização exigem argumentos 'current_user'/'user' "
                    "e 'db'/'session'. Para endpoints FastAPI, prefira Depends(require_permission(...))."
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
