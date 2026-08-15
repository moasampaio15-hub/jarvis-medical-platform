from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import require_permission
from app.database.session import get_db
from app.models.user import User
from app.schemas.vital_sign import VitalSignCreate, VitalSignList, VitalSignRead, VitalSignSearch, VitalSignUpdate
from app.services.vital_signs import (
    VitalSignAppointmentMismatchError,
    VitalSignAppointmentNotFoundError,
    VitalSignMedicalRecordMismatchError,
    VitalSignMedicalRecordNotFoundError,
    VitalSignNotFoundError,
    VitalSignPatientNotFoundError,
    VitalSignProfessionalNotFoundError,
    create_vital_sign,
    get_vital_sign,
    search_vital_signs,
    update_vital_sign,
)

router = APIRouter(prefix="/api/v1/vital-signs", tags=["Sinais Vitais e Triagem"])


def _not_found_exception() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Registro de sinais vitais não encontrado.")


def _invalid_patient_exception() -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Paciente não encontrado ou inativo.")


def _invalid_professional_exception() -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Profissional de saúde não encontrado ou inativo.")


def _invalid_appointment_exception() -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Consulta não encontrada ou cancelada.")


def _appointment_mismatch_exception() -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Consulta não pertence ao paciente e profissional informados.")


def _invalid_medical_record_exception() -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Prontuário médico não encontrado.")


def _medical_record_mismatch_exception() -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Prontuário não pertence ao paciente informado.")


@router.post(
    "",
    response_model=VitalSignRead,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar sinais vitais e triagem",
    description=(
        "Registra sinais vitais e observações breves de triagem, com vínculo opcional a consulta e prontuário. "
        "Protegido por `sinais_vitais:gerenciar`."
    ),
    responses={
        status.HTTP_400_BAD_REQUEST: {"description": "Paciente, profissional, consulta ou prontuário inválidos."},
        status.HTTP_401_UNAUTHORIZED: {"description": "Token ausente, inválido ou expirado."},
        status.HTTP_403_FORBIDDEN: {"description": "Permissão `sinais_vitais:gerenciar` ausente."},
        status.HTTP_409_CONFLICT: {"description": "Registro de sinais vitais inválido."},
    },
)
def create_vital_sign_endpoint(
    payload: VitalSignCreate,
    _: Annotated[User, Depends(require_permission("sinais_vitais:gerenciar"))],
    db: Annotated[Session, Depends(get_db)],
) -> VitalSignRead:
    try:
        vital_sign = create_vital_sign(db, payload)
    except VitalSignPatientNotFoundError as exc:
        raise _invalid_patient_exception() from exc
    except VitalSignProfessionalNotFoundError as exc:
        raise _invalid_professional_exception() from exc
    except VitalSignAppointmentNotFoundError as exc:
        raise _invalid_appointment_exception() from exc
    except VitalSignAppointmentMismatchError as exc:
        raise _appointment_mismatch_exception() from exc
    except VitalSignMedicalRecordNotFoundError as exc:
        raise _invalid_medical_record_exception() from exc
    except VitalSignMedicalRecordMismatchError as exc:
        raise _medical_record_mismatch_exception() from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Registro de sinais vitais inválido.") from exc
    return VitalSignRead.model_validate(vital_sign)


@router.get(
    "",
    response_model=VitalSignList,
    summary="Listar sinais vitais e triagens",
    description="Lista sinais vitais com filtros por paciente, profissional, consulta, prontuário e período. Protegido por `sinais_vitais:ler`.",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "Token ausente, inválido ou expirado."},
        status.HTTP_403_FORBIDDEN: {"description": "Permissão `sinais_vitais:ler` ausente."},
    },
)
def list_vital_signs_endpoint(
    search: Annotated[VitalSignSearch, Depends()],
    _: Annotated[User, Depends(require_permission("sinais_vitais:ler"))],
    db: Annotated[Session, Depends(get_db)],
) -> VitalSignList:
    vital_signs, total = search_vital_signs(db, search)
    return VitalSignList(
        items=[VitalSignRead.model_validate(vital_sign) for vital_sign in vital_signs],
        total=total,
        page=search.page,
        page_size=search.page_size,
    )


@router.get(
    "/{vital_sign_id}",
    response_model=VitalSignRead,
    summary="Consultar sinais vitais por ID",
    description="Retorna um registro histórico de sinais vitais e triagem. Protegido por `sinais_vitais:ler`.",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "Token ausente, inválido ou expirado."},
        status.HTTP_403_FORBIDDEN: {"description": "Permissão `sinais_vitais:ler` ausente."},
        status.HTTP_404_NOT_FOUND: {"description": "Registro de sinais vitais não encontrado."},
    },
)
def get_vital_sign_endpoint(
    vital_sign_id: int,
    _: Annotated[User, Depends(require_permission("sinais_vitais:ler"))],
    db: Annotated[Session, Depends(get_db)],
) -> VitalSignRead:
    try:
        vital_sign = get_vital_sign(db, vital_sign_id)
    except VitalSignNotFoundError as exc:
        raise _not_found_exception() from exc
    return VitalSignRead.model_validate(vital_sign)


@router.patch(
    "/{vital_sign_id}",
    response_model=VitalSignRead,
    summary="Atualizar sinais vitais e triagem",
    description="Atualiza medições, observações e vínculos do registro. Protegido por `sinais_vitais:gerenciar`.",
    responses={
        status.HTTP_400_BAD_REQUEST: {"description": "Paciente, profissional, consulta ou prontuário inválidos."},
        status.HTTP_401_UNAUTHORIZED: {"description": "Token ausente, inválido ou expirado."},
        status.HTTP_403_FORBIDDEN: {"description": "Permissão `sinais_vitais:gerenciar` ausente."},
        status.HTTP_404_NOT_FOUND: {"description": "Registro de sinais vitais não encontrado."},
        status.HTTP_409_CONFLICT: {"description": "Registro de sinais vitais inválido."},
    },
)
def update_vital_sign_endpoint(
    vital_sign_id: int,
    payload: VitalSignUpdate,
    _: Annotated[User, Depends(require_permission("sinais_vitais:gerenciar"))],
    db: Annotated[Session, Depends(get_db)],
) -> VitalSignRead:
    try:
        vital_sign = update_vital_sign(db, vital_sign_id, payload)
    except VitalSignNotFoundError as exc:
        raise _not_found_exception() from exc
    except VitalSignPatientNotFoundError as exc:
        raise _invalid_patient_exception() from exc
    except VitalSignProfessionalNotFoundError as exc:
        raise _invalid_professional_exception() from exc
    except VitalSignAppointmentNotFoundError as exc:
        raise _invalid_appointment_exception() from exc
    except VitalSignAppointmentMismatchError as exc:
        raise _appointment_mismatch_exception() from exc
    except VitalSignMedicalRecordNotFoundError as exc:
        raise _invalid_medical_record_exception() from exc
    except VitalSignMedicalRecordMismatchError as exc:
        raise _medical_record_mismatch_exception() from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Registro de sinais vitais inválido.") from exc
    return VitalSignRead.model_validate(vital_sign)
