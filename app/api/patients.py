from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import require_permission
from app.database.session import get_db
from app.models.user import User
from app.schemas.patient import PatientCreate, PatientList, PatientRead, PatientSearch, PatientUpdate
from app.services.patients import (
    PatientDuplicateError,
    PatientNotFoundError,
    create_patient,
    deactivate_patient,
    get_patient,
    search_patients,
    update_patient,
)

router = APIRouter(prefix="/api/v1/patients", tags=["Pacientes"])


def _not_found_exception() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Paciente não encontrado.")


def _conflict_exception(field: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=f"Paciente com {field.upper()} já cadastrado.",
    )


@router.post(
    "",
    response_model=PatientRead,
    status_code=status.HTTP_201_CREATED,
    summary="Cadastrar paciente",
    description=(
        "Cria um cadastro administrativo de paciente sem dados clínicos. "
        "Protegido pela permissão `patients:create`."
    ),
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "Token ausente, inválido ou expirado."},
        status.HTTP_403_FORBIDDEN: {"description": "Permissão `patients:create` ausente."},
        status.HTTP_409_CONFLICT: {"description": "CPF ou CNS já cadastrado."},
    },
)
def create_patient_endpoint(
    payload: PatientCreate,
    _: Annotated[User, Depends(require_permission("patients:create"))],
    db: Annotated[Session, Depends(get_db)],
) -> PatientRead:
    try:
        patient = create_patient(db, payload)
    except PatientDuplicateError as exc:
        raise _conflict_exception(exc.field) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="CPF ou CNS já cadastrado.",
        ) from exc
    return PatientRead.model_validate(patient)


@router.get(
    "",
    response_model=PatientList,
    summary="Listar e buscar pacientes",
    description=(
        "Lista pacientes com paginação e filtros por nome, CPF e CNS. "
        "Protegido pela permissão `patients:read`."
    ),
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "Token ausente, inválido ou expirado."},
        status.HTTP_403_FORBIDDEN: {"description": "Permissão `patients:read` ausente."},
    },
)
def list_patients_endpoint(
    search: Annotated[PatientSearch, Depends()],
    _: Annotated[User, Depends(require_permission("patients:read"))],
    db: Annotated[Session, Depends(get_db)],
) -> PatientList:
    patients, total = search_patients(db, search)
    return PatientList(
        items=[PatientRead.model_validate(patient) for patient in patients],
        total=total,
        page=search.page,
        page_size=search.page_size,
    )


@router.get(
    "/{patient_id}",
    response_model=PatientRead,
    summary="Consultar paciente por ID",
    description="Retorna dados cadastrais do paciente. Protegido pela permissão `patients:read`.",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "Token ausente, inválido ou expirado."},
        status.HTTP_403_FORBIDDEN: {"description": "Permissão `patients:read` ausente."},
        status.HTTP_404_NOT_FOUND: {"description": "Paciente não encontrado."},
    },
)
def get_patient_endpoint(
    patient_id: int,
    _: Annotated[User, Depends(require_permission("patients:read"))],
    db: Annotated[Session, Depends(get_db)],
) -> PatientRead:
    try:
        patient = get_patient(db, patient_id)
    except PatientNotFoundError as exc:
        raise _not_found_exception() from exc
    return PatientRead.model_validate(patient)


@router.patch(
    "/{patient_id}",
    response_model=PatientRead,
    summary="Atualizar cadastro de paciente",
    description="Atualiza dados cadastrais sem dados clínicos. Protegido por `patients:update`.",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "Token ausente, inválido ou expirado."},
        status.HTTP_403_FORBIDDEN: {"description": "Permissão `patients:update` ausente."},
        status.HTTP_404_NOT_FOUND: {"description": "Paciente não encontrado."},
        status.HTTP_409_CONFLICT: {"description": "CPF ou CNS já cadastrado."},
    },
)
def update_patient_endpoint(
    patient_id: int,
    payload: PatientUpdate,
    _: Annotated[User, Depends(require_permission("patients:update"))],
    db: Annotated[Session, Depends(get_db)],
) -> PatientRead:
    try:
        patient = update_patient(db, patient_id, payload)
    except PatientNotFoundError as exc:
        raise _not_found_exception() from exc
    except PatientDuplicateError as exc:
        raise _conflict_exception(exc.field) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="CPF ou CNS já cadastrado.",
        ) from exc
    return PatientRead.model_validate(patient)


@router.delete(
    "/{patient_id}",
    response_model=PatientRead,
    summary="Inativar paciente",
    description=(
        "Realiza inativação lógica do cadastro, marcando `ativo=false`; não exclui fisicamente. "
        "Protegido por `patients:deactivate`."
    ),
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "Token ausente, inválido ou expirado."},
        status.HTTP_403_FORBIDDEN: {"description": "Permissão `patients:deactivate` ausente."},
        status.HTTP_404_NOT_FOUND: {"description": "Paciente não encontrado."},
    },
)
def deactivate_patient_endpoint(
    patient_id: int,
    _: Annotated[User, Depends(require_permission("patients:deactivate"))],
    db: Annotated[Session, Depends(get_db)],
) -> PatientRead:
    try:
        patient = deactivate_patient(db, patient_id)
    except PatientNotFoundError as exc:
        raise _not_found_exception() from exc
    return PatientRead.model_validate(patient)
