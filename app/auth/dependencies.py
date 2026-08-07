from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.auth.jwt import JWTValidationError, decode_token
from app.database.session import get_db
from app.models.user import User

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Não foi possível validar as credenciais.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if credentials is None:
        raise credentials_exception

    try:
        payload = decode_token(credentials.credentials, expected_type="access")
        user_id = int(payload["sub"])
    except (JWTValidationError, ValueError, TypeError):
        raise credentials_exception from None

    user = db.get(User, user_id)
    if user is None or not user.ativo:
        raise credentials_exception

    from app.auth.authorization import load_user_authorization_context

    return load_user_authorization_context(user, db)


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_permission(*permissions: str, require_all: bool = False):
    from app.auth.authorization import assert_user_has_permissions, normalize_permission_code

    required_permissions = tuple(normalize_permission_code(permission) for permission in permissions)
    if not required_permissions:
        raise ValueError("Informe pelo menos uma permissão para autorização.")

    def dependency(current_user: CurrentUser, db: Annotated[Session, Depends(get_db)]) -> User:
        assert_user_has_permissions(current_user, required_permissions, db, require_all=require_all)
        return current_user

    return dependency


def require_role(*roles: str, require_all: bool = False):
    from app.auth.authorization import assert_user_has_roles, normalize_permission_code

    required_roles = tuple(normalize_permission_code(role) for role in roles)
    if not required_roles:
        raise ValueError("Informe pelo menos um papel para autorização.")

    def dependency(current_user: CurrentUser, db: Annotated[Session, Depends(get_db)]) -> User:
        assert_user_has_roles(current_user, required_roles, db, require_all=require_all)
        return current_user

    return dependency
