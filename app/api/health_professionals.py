from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import require_permission
from app.database.session import get_db
from app.models.user import User
from app.schemas.health_professional import (
    HealthProfessionalCreate,
    HealthProfessionalList,
    HealthProfessionalRead,
    HealthProfessionalSearch,
    HealthProfessionalUpdate,
)
from app.services.health_professionals import (
    HealthProfessionalDuplicateError,
    HealthProfessionalNotFoundError,
    HealthProfessionalUserNotFoundError,
    create_health_professional,
    deactivate_health_professional,
    get_health_professional,
    search_health_professionals,
    update_health_professional,
)

router = APIRouter(prefix="/api/v1/health-professionals", tags=["Profissionais de Saúde"])


def _not_found_exception() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profissional de saúde não encontrado.")


def _conflict_exception(field: str) -> HTTPException:
    messages = {
        "cpf": "Profissional de saúde com CPF já cadastrado.",
        "conselho": "Profissional de saúde com conselho já cadastrado.",
        "user_id": "Usuário já vinculado a outro profissional de saúde.",
    }
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=messages.get(field, f"Profissional de saúde com {field} já cadastrado."),
    )


def _invalid_user_exception() -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Usuário vinculado não encontrado.")


@router.post(
    "",
    response_model=HealthProfessionalRead,
    status_code=status.HTTP_201_CREATED,
    summary="Cadastrar profissional de saúde",
    description=(
        "Cria um cadastro administrativo de profissional de saúde, com vínculo opcional a uma conta "
        "autenticável existente. Não armazena senha nem duplica dados de autenticação. "
        "Protegido pela permissão `health_professionals:create`."
    ),
    responses={
        status.HTTP_400_BAD_REQUEST: {"description": "Usuário vinculado não encontrado."},
        status.HTTP_401_UNAUTHORIZED: {"description": "Token ausente, inválido ou expirado."},
        status.HTTP_403_FORBIDDEN: {"description": "Permissão `health_professionals:create` ausente."},
        status.HTTP_409_CONFLICT: {"description": "CPF, conselho ou usuário já cadastrado."},
    },
)
def create_health_professional_endpoint(
    payload: HealthProfessionalCreate,
    _: Annotated[User, Depends(require_permission("health_professionals:create"))],
    db: Annotated[Session, Depends(get_db)],
) -> HealthProfessionalRead:
    try:
        professional = create_health_professional(db, payload)
    except HealthProfessionalUserNotFoundError as exc:
        raise _invalid_user_exception() from exc
    except HealthProfessionalDuplicateError as exc:
        raise _conflict_exception(exc.field) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="CPF, conselho ou usuário já cadastrado.",
        ) from exc
    return HealthProfessionalRead.model_validate(professional)


@router.get(
    "",
    response_model=HealthProfessionalList,
    summary="Listar e buscar profissionais de saúde",
    description=(
        "Lista profissionais de saúde com paginação e filtros por nome, CPF, conselho e especialidade. "
        "Protegido pela permissão `health_professionals:read`."
    ),
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "Token ausente, inválido ou expirado."},
        status.HTTP_403_FORBIDDEN: {"description": "Permissão `health_professionals:read` ausente."},
    },
)
def list_health_professionals_endpoint(
    search: Annotated[HealthProfessionalSearch, Depends()],
    _: Annotated[User, Depends(require_permission("health_professionals:read"))],
    db: Annotated[Session, Depends(get_db)],
) -> HealthProfessionalList:
    professionals, total = search_health_professionals(db, search)
    return HealthProfessionalList(
        items=[HealthProfessionalRead.model_validate(professional) for professional in professionals],
        total=total,
        page=search.page,
        page_size=search.page_size,
    )


@router.get(
    "/{professional_id}",
    response_model=HealthProfessionalRead,
    summary="Consultar profissional de saúde por ID",
    description="Retorna dados administrativos do profissional. Protegido por `health_professionals:read`.",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "Token ausente, inválido ou expirado."},
        status.HTTP_403_FORBIDDEN: {"description": "Permissão `health_professionals:read` ausente."},
        status.HTTP_404_NOT_FOUND: {"description": "Profissional de saúde não encontrado."},
    },
)
def get_health_professional_endpoint(
    professional_id: int,
    _: Annotated[User, Depends(require_permission("health_professionals:read"))],
    db: Annotated[Session, Depends(get_db)],
) -> HealthProfessionalRead:
    try:
        professional = get_health_professional(db, professional_id)
    except HealthProfessionalNotFoundError as exc:
        raise _not_found_exception() from exc
    return HealthProfessionalRead.model_validate(professional)


@router.patch(
    "/{professional_id}",
    response_model=HealthProfessionalRead,
    summary="Atualizar cadastro de profissional de saúde",
    description=(
        "Atualiza dados administrativos e vínculo opcional com usuário. "
        "Protegido por `health_professionals:update`."
    ),
    responses={
        status.HTTP_400_BAD_REQUEST: {"description": "Usuário vinculado não encontrado."},
        status.HTTP_401_UNAUTHORIZED: {"description": "Token ausente, inválido ou expirado."},
        status.HTTP_403_FORBIDDEN: {"description": "Permissão `health_professionals:update` ausente."},
        status.HTTP_404_NOT_FOUND: {"description": "Profissional de saúde não encontrado."},
        status.HTTP_409_CONFLICT: {"description": "CPF, conselho ou usuário já cadastrado."},
    },
)
def update_health_professional_endpoint(
    professional_id: int,
    payload: HealthProfessionalUpdate,
    _: Annotated[User, Depends(require_permission("health_professionals:update"))],
    db: Annotated[Session, Depends(get_db)],
) -> HealthProfessionalRead:
    try:
        professional = update_health_professional(db, professional_id, payload)
    except HealthProfessionalNotFoundError as exc:
        raise _not_found_exception() from exc
    except HealthProfessionalUserNotFoundError as exc:
        raise _invalid_user_exception() from exc
    except HealthProfessionalDuplicateError as exc:
        raise _conflict_exception(exc.field) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="CPF, conselho ou usuário já cadastrado.",
        ) from exc
    return HealthProfessionalRead.model_validate(professional)


@router.delete(
    "/{professional_id}",
    response_model=HealthProfessionalRead,
    summary="Inativar profissional de saúde",
    description=(
        "Realiza inativação lógica do cadastro, marcando `ativo=false`; não exclui fisicamente. "
        "Protegido por `health_professionals:deactivate`."
    ),
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "Token ausente, inválido ou expirado."},
        status.HTTP_403_FORBIDDEN: {"description": "Permissão `health_professionals:deactivate` ausente."},
        status.HTTP_404_NOT_FOUND: {"description": "Profissional de saúde não encontrado."},
    },
)
def deactivate_health_professional_endpoint(
    professional_id: int,
    _: Annotated[User, Depends(require_permission("health_professionals:deactivate"))],
    db: Annotated[Session, Depends(get_db)],
) -> HealthProfessionalRead:
    try:
        professional = deactivate_health_professional(db, professional_id)
    except HealthProfessionalNotFoundError as exc:
        raise _not_found_exception() from exc
    return HealthProfessionalRead.model_validate(professional)
