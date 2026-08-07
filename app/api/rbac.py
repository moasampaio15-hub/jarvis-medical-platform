from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import require_permission
from app.auth.authorization import (
    assign_role_to_user,
    ensure_default_rbac,
    get_user_permission_codes,
    get_user_role_codes,
    load_user_authorization_context,
    normalize_permission_code,
    revoke_role_from_user,
)
from app.database.session import get_db
from app.models.rbac import Permission, Role
from app.models.user import User
from app.schemas.rbac import (
    CurrentUserAuthorizationRead,
    PermissionRead,
    RoleRead,
    UserRoleAssignmentRead,
)

router = APIRouter(prefix="/rbac", tags=["RBAC"])


def _authorization_payload(user: User) -> CurrentUserAuthorizationRead:
    return CurrentUserAuthorizationRead(
        id=user.id,
        nome=user.nome,
        email=user.email,
        ativo=user.ativo,
        superuser=user.superuser,
        roles=sorted(getattr(user, "role_codes", set())),
        permissions=sorted(getattr(user, "permission_codes", set())),
    )


def _assignment_payload(db: Session, user: User) -> UserRoleAssignmentRead:
    return UserRoleAssignmentRead(
        user_id=user.id,
        email=user.email,
        roles=sorted(get_user_role_codes(db, user.id)),
        permissions=sorted(get_user_permission_codes(db, user.id)),
    )


@router.get(
    "/me",
    response_model=CurrentUserAuthorizationRead,
    summary="Obter papéis e permissões do usuário autenticado",
    description="Requer a permissão granular `perfil:ler` e retorna o contexto RBAC do JWT atual.",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "Token ausente, inválido ou expirado."},
        status.HTTP_403_FORBIDDEN: {"description": "Usuário autenticado sem permissão `perfil:ler`."},
    },
)
def read_my_authorization(
    current_user: Annotated[User, Depends(require_permission("perfil:ler"))],
) -> CurrentUserAuthorizationRead:
    return _authorization_payload(current_user)


@router.get(
    "/roles",
    response_model=list[RoleRead],
    summary="Listar papéis RBAC",
    description="Endpoint administrativo protegido por `rbac:roles:ler`.",
    responses={status.HTTP_403_FORBIDDEN: {"description": "Permissão `rbac:roles:ler` ausente."}},
)
def list_roles(
    _: Annotated[User, Depends(require_permission("rbac:roles:ler"))],
    db: Annotated[Session, Depends(get_db)],
) -> list[Role]:
    ensure_default_rbac(db)
    db.commit()
    return list(db.scalars(select(Role).order_by(Role.codigo)).all())


@router.get(
    "/permissions",
    response_model=list[PermissionRead],
    summary="Listar permissões RBAC",
    description="Endpoint administrativo protegido por `rbac:permissoes:ler`.",
    responses={
        status.HTTP_403_FORBIDDEN: {"description": "Permissão `rbac:permissoes:ler` ausente."}
    },
)
def list_permissions(
    _: Annotated[User, Depends(require_permission("rbac:permissoes:ler"))],
    db: Annotated[Session, Depends(get_db)],
) -> list[Permission]:
    ensure_default_rbac(db)
    db.commit()
    return list(db.scalars(select(Permission).order_by(Permission.codigo)).all())


@router.post(
    "/users/{user_id}/roles/{role_code}",
    response_model=UserRoleAssignmentRead,
    status_code=status.HTTP_200_OK,
    summary="Atribuir papel a usuário",
    description="Endpoint administrativo protegido por `rbac:roles:atribuir`.",
    responses={
        status.HTTP_403_FORBIDDEN: {"description": "Permissão `rbac:roles:atribuir` ausente."},
        status.HTTP_404_NOT_FOUND: {"description": "Usuário ou papel não encontrado."},
    },
)
def assign_user_role(
    user_id: int,
    role_code: str,
    _: Annotated[User, Depends(require_permission("rbac:roles:atribuir"))],
    db: Annotated[Session, Depends(get_db)],
) -> UserRoleAssignmentRead:
    ensure_default_rbac(db)
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuário não encontrado.")

    normalized_role_code = normalize_permission_code(role_code)
    if db.scalar(select(Role).where(Role.codigo == normalized_role_code)) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Papel não encontrado.")

    assign_role_to_user(db, user, normalized_role_code)
    db.commit()
    load_user_authorization_context(user, db)
    return _assignment_payload(db, user)


@router.delete(
    "/users/{user_id}/roles/{role_code}",
    response_model=UserRoleAssignmentRead,
    summary="Revogar papel de usuário",
    description="Endpoint administrativo protegido por `rbac:roles:atribuir`.",
    responses={
        status.HTTP_403_FORBIDDEN: {"description": "Permissão `rbac:roles:atribuir` ausente."},
        status.HTTP_404_NOT_FOUND: {"description": "Usuário ou papel não encontrado."},
    },
)
def revoke_user_role(
    user_id: int,
    role_code: str,
    _: Annotated[User, Depends(require_permission("rbac:roles:atribuir"))],
    db: Annotated[Session, Depends(get_db)],
) -> UserRoleAssignmentRead:
    ensure_default_rbac(db)
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuário não encontrado.")

    try:
        revoke_role_from_user(db, user, role_code)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Papel não encontrado.") from exc

    db.commit()
    load_user_authorization_context(user, db)
    return _assignment_payload(db, user)
