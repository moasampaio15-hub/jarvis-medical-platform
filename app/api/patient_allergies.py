from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import require_permission
from app.database.session import get_db
from app.models.user import User
from app.schemas.patient_allergy import (
    PatientAllergyCreate,
    PatientAllergyList,
    PatientAllergyRead,
    PatientAllergySearch,
    PatientAllergyUpdate,
)
from app.services.patient_allergies import (
    PatientAllergyMedicalRecordMismatchError,
    PatientAllergyMedicalRecordNotFoundError,
    PatientAllergyNotFoundError,
    PatientAllergyPatientNotFoundError,
    PatientAllergyProfessionalNotFoundError,
    create_patient_allergy,
    get_patient_allergy,
    search_patient_allergies,
    update_patient_allergy,
)

router = APIRouter(prefix="/api/v1/patient-allergies", tags=["Alergias e Intolerâncias"])


def _not_found_exception() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alergia/intolerância não encontrada.")


def _invalid_patient_exception() -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Paciente não encontrado ou inativo.")


def _invalid_professional_exception() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Profissional de saúde não encontrado ou inativo.",
    )


def _invalid_medical_record_exception() -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Prontuário médico não encontrado.")


def _medical_record_mismatch_exception() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Prontuário não pertence ao paciente informado.",
    )


@router.post(
    "",
    response_model=PatientAllergyRead,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar alergia ou intolerância",
    description=(
        "Registra alergias, intolerâncias e reações adversas do paciente, com vínculo opcional "
        "ao prontuário. Protegido por `alergias:gerenciar`."
    ),
    responses={
        status.HTTP_400_BAD_REQUEST: {"description": "Paciente, profissional ou prontuário inválidos."},
        status.HTTP_401_UNAUTHORIZED: {"description": "Token ausente, inválido ou expirado."},
        status.HTTP_403_FORBIDDEN: {"description": "Permissão `alergias:gerenciar` ausente."},
        status.HTTP_409_CONFLICT: {"description": "Registro de alergia/intolerância inválido."},
    },
)
def create_patient_allergy_endpoint(
    payload: PatientAllergyCreate,
    _: Annotated[User, Depends(require_permission("alergias:gerenciar"))],
    db: Annotated[Session, Depends(get_db)],
) -> PatientAllergyRead:
    try:
        allergy = create_patient_allergy(db, payload)
    except PatientAllergyPatientNotFoundError as exc:
        raise _invalid_patient_exception() from exc
    except PatientAllergyProfessionalNotFoundError as exc:
        raise _invalid_professional_exception() from exc
    except PatientAllergyMedicalRecordNotFoundError as exc:
        raise _invalid_medical_record_exception() from exc
    except PatientAllergyMedicalRecordMismatchError as exc:
        raise _medical_record_mismatch_exception() from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Registro de alergia/intolerância inválido.",
        ) from exc
    return PatientAllergyRead.model_validate(allergy)


@router.get(
    "",
    response_model=PatientAllergyList,
    summary="Listar alergias e intolerâncias",
    description=(
        "Lista alergias, intolerâncias e reações adversas com filtros por paciente, profissional, "
        "tipo, categoria, gravidade, status e substância. Protegido por `alergias:ler`."
    ),
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "Token ausente, inválido ou expirado."},
        status.HTTP_403_FORBIDDEN: {"description": "Permissão `alergias:ler` ausente."},
    },
)
def list_patient_allergies_endpoint(
    search: Annotated[PatientAllergySearch, Depends()],
    _: Annotated[User, Depends(require_permission("alergias:ler"))],
    db: Annotated[Session, Depends(get_db)],
) -> PatientAllergyList:
    allergies, total = search_patient_allergies(db, search)
    return PatientAllergyList(
        items=[PatientAllergyRead.model_validate(allergy) for allergy in allergies],
        total=total,
        page=search.page,
        page_size=search.page_size,
    )


@router.get(
    "/{allergy_id}",
    response_model=PatientAllergyRead,
    summary="Consultar alergia ou intolerância por ID",
    description="Retorna dados do registro de alergia/intolerância. Protegido por `alergias:ler`.",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "Token ausente, inválido ou expirado."},
        status.HTTP_403_FORBIDDEN: {"description": "Permissão `alergias:ler` ausente."},
        status.HTTP_404_NOT_FOUND: {"description": "Alergia/intolerância não encontrada."},
    },
)
def get_patient_allergy_endpoint(
    allergy_id: int,
    _: Annotated[User, Depends(require_permission("alergias:ler"))],
    db: Annotated[Session, Depends(get_db)],
) -> PatientAllergyRead:
    try:
        allergy = get_patient_allergy(db, allergy_id)
    except PatientAllergyNotFoundError as exc:
        raise _not_found_exception() from exc
    return PatientAllergyRead.model_validate(allergy)


@router.patch(
    "/{allergy_id}",
    response_model=PatientAllergyRead,
    summary="Atualizar alergia ou intolerância",
    description="Atualiza dados e status do registro de alergia/intolerância. Protegido por `alergias:gerenciar`.",
    responses={
        status.HTTP_400_BAD_REQUEST: {"description": "Paciente, profissional ou prontuário inválidos."},
        status.HTTP_401_UNAUTHORIZED: {"description": "Token ausente, inválido ou expirado."},
        status.HTTP_403_FORBIDDEN: {"description": "Permissão `alergias:gerenciar` ausente."},
        status.HTTP_404_NOT_FOUND: {"description": "Alergia/intolerância não encontrada."},
        status.HTTP_409_CONFLICT: {"description": "Registro de alergia/intolerância inválido."},
    },
)
def update_patient_allergy_endpoint(
    allergy_id: int,
    payload: PatientAllergyUpdate,
    _: Annotated[User, Depends(require_permission("alergias:gerenciar"))],
    db: Annotated[Session, Depends(get_db)],
) -> PatientAllergyRead:
    try:
        allergy = update_patient_allergy(db, allergy_id, payload)
    except PatientAllergyNotFoundError as exc:
        raise _not_found_exception() from exc
    except PatientAllergyPatientNotFoundError as exc:
        raise _invalid_patient_exception() from exc
    except PatientAllergyProfessionalNotFoundError as exc:
        raise _invalid_professional_exception() from exc
    except PatientAllergyMedicalRecordNotFoundError as exc:
        raise _invalid_medical_record_exception() from exc
    except PatientAllergyMedicalRecordMismatchError as exc:
        raise _medical_record_mismatch_exception() from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Registro de alergia/intolerância inválido.",
        ) from exc
    return PatientAllergyRead.model_validate(allergy)
