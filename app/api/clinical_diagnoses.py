from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import require_permission
from app.database.session import get_db
from app.models.user import User
from app.schemas.clinical_diagnosis import (
    ClinicalDiagnosisCreate,
    ClinicalDiagnosisList,
    ClinicalDiagnosisRead,
    ClinicalDiagnosisSearch,
    ClinicalDiagnosisUpdate,
)
from app.services.clinical_diagnoses import (
    ClinicalDiagnosisAppointmentMismatchError,
    ClinicalDiagnosisAppointmentNotFoundError,
    ClinicalDiagnosisInvalidDateRangeError,
    ClinicalDiagnosisMedicalRecordMismatchError,
    ClinicalDiagnosisMedicalRecordNotFoundError,
    ClinicalDiagnosisNotFoundError,
    ClinicalDiagnosisPatientNotFoundError,
    ClinicalDiagnosisProfessionalNotFoundError,
    create_clinical_diagnosis,
    get_clinical_diagnosis,
    search_clinical_diagnoses,
    update_clinical_diagnosis,
)

router = APIRouter(prefix="/api/v1/clinical-diagnoses", tags=["Diagnósticos e Problemas Clínicos"])


def _not_found_exception() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Diagnóstico/problema clínico não encontrado.")


def _bad_request(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


def _handle_validation_error(exc: ValueError) -> HTTPException:
    if isinstance(exc, ClinicalDiagnosisPatientNotFoundError):
        return _bad_request("Paciente não encontrado ou inativo.")
    if isinstance(exc, ClinicalDiagnosisProfessionalNotFoundError):
        return _bad_request("Profissional de saúde não encontrado ou inativo.")
    if isinstance(exc, ClinicalDiagnosisAppointmentNotFoundError):
        return _bad_request("Consulta não encontrada ou cancelada.")
    if isinstance(exc, ClinicalDiagnosisAppointmentMismatchError):
        return _bad_request("Consulta não pertence ao paciente e profissional informados.")
    if isinstance(exc, ClinicalDiagnosisMedicalRecordNotFoundError):
        return _bad_request("Prontuário médico não encontrado.")
    if isinstance(exc, ClinicalDiagnosisMedicalRecordMismatchError):
        return _bad_request("Prontuário não pertence ao paciente informado.")
    if isinstance(exc, ClinicalDiagnosisInvalidDateRangeError):
        return _bad_request("Data de resolução não pode ser anterior à data de início.")
    return _bad_request("Diagnóstico/problema clínico inválido.")


@router.post(
    "",
    response_model=ClinicalDiagnosisRead,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar diagnóstico ou problema clínico",
    description=(
        "Registra hipótese, diagnóstico confirmado ou problema clínico do paciente, com vínculo opcional "
        "a consulta e prontuário. Protegido por `diagnosticos:gerenciar`."
    ),
    responses={
        status.HTTP_400_BAD_REQUEST: {"description": "Paciente, profissional, consulta, prontuário ou datas inválidos."},
        status.HTTP_401_UNAUTHORIZED: {"description": "Token ausente, inválido ou expirado."},
        status.HTTP_403_FORBIDDEN: {"description": "Permissão `diagnosticos:gerenciar` ausente."},
        status.HTTP_409_CONFLICT: {"description": "Diagnóstico/problema clínico inválido."},
    },
)
def create_clinical_diagnosis_endpoint(
    payload: ClinicalDiagnosisCreate,
    _: Annotated[User, Depends(require_permission("diagnosticos:gerenciar"))],
    db: Annotated[Session, Depends(get_db)],
) -> ClinicalDiagnosisRead:
    try:
        diagnosis = create_clinical_diagnosis(db, payload)
    except ValueError as exc:
        raise _handle_validation_error(exc) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Diagnóstico/problema clínico inválido.") from exc
    return ClinicalDiagnosisRead.model_validate(diagnosis)


@router.get(
    "",
    response_model=ClinicalDiagnosisList,
    summary="Listar diagnósticos e problemas clínicos",
    description="Lista diagnósticos/problemas com filtros por paciente, profissional, consulta, prontuário, CID-10, tipo e status. Protegido por `diagnosticos:ler`.",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "Token ausente, inválido ou expirado."},
        status.HTTP_403_FORBIDDEN: {"description": "Permissão `diagnosticos:ler` ausente."},
    },
)
def list_clinical_diagnoses_endpoint(
    search: Annotated[ClinicalDiagnosisSearch, Depends()],
    _: Annotated[User, Depends(require_permission("diagnosticos:ler"))],
    db: Annotated[Session, Depends(get_db)],
) -> ClinicalDiagnosisList:
    diagnoses, total = search_clinical_diagnoses(db, search)
    return ClinicalDiagnosisList(
        items=[ClinicalDiagnosisRead.model_validate(diagnosis) for diagnosis in diagnoses],
        total=total,
        page=search.page,
        page_size=search.page_size,
    )


@router.get(
    "/{diagnosis_id}",
    response_model=ClinicalDiagnosisRead,
    summary="Consultar diagnóstico ou problema clínico por ID",
    description="Retorna um diagnóstico/problema clínico. Protegido por `diagnosticos:ler`.",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "Token ausente, inválido ou expirado."},
        status.HTTP_403_FORBIDDEN: {"description": "Permissão `diagnosticos:ler` ausente."},
        status.HTTP_404_NOT_FOUND: {"description": "Diagnóstico/problema clínico não encontrado."},
    },
)
def get_clinical_diagnosis_endpoint(
    diagnosis_id: int,
    _: Annotated[User, Depends(require_permission("diagnosticos:ler"))],
    db: Annotated[Session, Depends(get_db)],
) -> ClinicalDiagnosisRead:
    try:
        diagnosis = get_clinical_diagnosis(db, diagnosis_id)
    except ClinicalDiagnosisNotFoundError as exc:
        raise _not_found_exception() from exc
    return ClinicalDiagnosisRead.model_validate(diagnosis)


@router.patch(
    "/{diagnosis_id}",
    response_model=ClinicalDiagnosisRead,
    summary="Atualizar diagnóstico ou problema clínico",
    description="Atualiza dados, status e vínculos do diagnóstico/problema clínico. Protegido por `diagnosticos:gerenciar`.",
    responses={
        status.HTTP_400_BAD_REQUEST: {"description": "Paciente, profissional, consulta, prontuário ou datas inválidos."},
        status.HTTP_401_UNAUTHORIZED: {"description": "Token ausente, inválido ou expirado."},
        status.HTTP_403_FORBIDDEN: {"description": "Permissão `diagnosticos:gerenciar` ausente."},
        status.HTTP_404_NOT_FOUND: {"description": "Diagnóstico/problema clínico não encontrado."},
        status.HTTP_409_CONFLICT: {"description": "Diagnóstico/problema clínico inválido."},
    },
)
def update_clinical_diagnosis_endpoint(
    diagnosis_id: int,
    payload: ClinicalDiagnosisUpdate,
    _: Annotated[User, Depends(require_permission("diagnosticos:gerenciar"))],
    db: Annotated[Session, Depends(get_db)],
) -> ClinicalDiagnosisRead:
    try:
        diagnosis = update_clinical_diagnosis(db, diagnosis_id, payload)
    except ClinicalDiagnosisNotFoundError as exc:
        raise _not_found_exception() from exc
    except ValueError as exc:
        raise _handle_validation_error(exc) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Diagnóstico/problema clínico inválido.") from exc
    return ClinicalDiagnosisRead.model_validate(diagnosis)
