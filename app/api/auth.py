from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import CurrentUser, create_access_token, create_refresh_token
from app.auth.authorization import assign_role_to_user, ensure_default_rbac
from app.auth.jwt import JWTValidationError, decode_token
from app.auth.password import (
    PasswordValidationError,
    hash_password,
    validate_password_strength,
    verify_password,
)
from app.database.session import get_db
from app.models.user import User
from app.schemas.auth import AuthenticatedUserResponse, LoginRequest, RefreshTokenRequest, TokenResponse
from app.schemas.user import UserCreate, UserRead

router = APIRouter(prefix="/auth", tags=["Autenticação"])


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _get_user_by_email(db: Session, email: str) -> User | None:
    normalized_email = _normalize_email(email)
    statement = select(User).where(func.lower(User.email) == normalized_email)
    return db.scalar(statement)


def _build_token_response(user_id: int) -> TokenResponse:
    return TokenResponse(
        access_token=create_access_token(subject=user_id),
        refresh_token=create_refresh_token(subject=user_id),
    )


@router.post(
    "/register",
    response_model=AuthenticatedUserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar novo usuário",
    responses={
        status.HTTP_201_CREATED: {"description": "Usuário registrado e autenticado."},
        status.HTTP_400_BAD_REQUEST: {"description": "Senha fora da política de segurança."},
        status.HTTP_409_CONFLICT: {"description": "E-mail já cadastrado."},
    },
)
def register_user(payload: UserCreate, db: Annotated[Session, Depends(get_db)]) -> AuthenticatedUserResponse:
    """Cria uma conta ativa e retorna access token e refresh token JWT."""
    if _get_user_by_email(db, payload.email) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="E-mail já cadastrado.",
        )

    try:
        validate_password_strength(payload.senha)
    except PasswordValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=exc.errors,
        ) from exc

    user = User(
        nome=payload.nome.strip(),
        email=_normalize_email(payload.email),
        senha_hash=hash_password(payload.senha),
    )
    try:
        ensure_default_rbac(db)
        db.add(user)
        db.flush()
        assign_role_to_user(db, user)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="E-mail já cadastrado.",
        ) from exc

    db.refresh(user)

    return AuthenticatedUserResponse(
        user=UserRead.model_validate(user), tokens=_build_token_response(user.id)
    )


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Autenticar usuário",
    responses={status.HTTP_401_UNAUTHORIZED: {"description": "Credenciais inválidas ou usuário inativo."}},
)
def login(payload: LoginRequest, db: Annotated[Session, Depends(get_db)]) -> TokenResponse:
    """Valida e-mail e senha e emite novos tokens JWT."""
    user = _get_user_by_email(db, payload.email)
    if user is None or not user.ativo or not verify_password(payload.senha, user.senha_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="E-mail ou senha inválidos.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return _build_token_response(user.id)


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Renovar tokens JWT",
    responses={status.HTTP_401_UNAUTHORIZED: {"description": "Refresh token inválido ou usuário inativo."}},
)
def refresh_tokens(payload: RefreshTokenRequest, db: Annotated[Session, Depends(get_db)]) -> TokenResponse:
    """Valida um refresh token e emite um novo par de tokens."""
    try:
        decoded_token = decode_token(payload.refresh_token, expected_type="refresh")
        user_id = int(decoded_token["sub"])
    except (JWTValidationError, ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token inválido ou expirado.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None

    user = db.get(User, user_id)
    if user is None or not user.ativo:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário inativo ou inexistente.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return _build_token_response(user.id)


@router.get(
    "/me",
    response_model=UserRead,
    summary="Obter usuário autenticado",
    responses={status.HTTP_401_UNAUTHORIZED: {"description": "Token ausente, inválido ou expirado."}},
)
def read_current_user(current_user: CurrentUser) -> User:
    """Retorna o perfil do usuário autenticado pelo access token."""
    return current_user
