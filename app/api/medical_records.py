from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import require_permission
from app.database.session import get_db
from app.models.user import User
from app.schemas.medical_record import (
    MedicalRecordCreate,
    MedicalRecordList,
    MedicalRecordRead,
    MedicalRecordSearch,
    MedicalRecordUpdate,
)
from app.services.medical_records import (
    MedicalRecordAppointmentMismatchError,
    MedicalRecordAppointmentNotFoundError,
    MedicalRecordDuplicateAppointmentError,
    MedicalRecordNotFoundError,
    MedicalRecordPatientNotFoundError,
    MedicalRecordProfessionalNotFoundError,
    create_medical_record,
    get_medical_record,
    search_medical_records,
    update_medical_record,
)

router = APIRouter(prefix="/api/v1/medical-records", tags=["Prontuário Médico"])


def _not_found_exception() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prontuário médico não encontrado.")


def _invalid_patient_exception() -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Paciente não encontrado ou inativo.")


def _invalid_professional_exception() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Profissional de saúde não encontrado ou inativo.",
    )


def _invalid_appointment_exception() -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Consulta não encontrada ou cancelada.")


def _appointment_mismatch_exception() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Consulta não pertence ao paciente e profissional informados.",
    )


def _duplicate_appointment_exception() -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Consulta já vinculada a outro prontuário.")


@router.post(
    "",
    response_model=MedicalRecordRead,
    status_code=status.HTTP_201_CREATED,
    summary="Criar prontuário médico",
    description=(
        "Cria um registro clínico vinculado a paciente e profissional de saúde, com vínculo opcional "
        "a uma consulta existente. Protegido por `prontuarios:escrever`."
    ),
    responses={
        status.HTTP_400_BAD_REQUEST: {"description": "Paciente, profissional ou consulta inválidos."},
        status.HTTP_401_UNAUTHORIZED: {"description": "Token ausente, inválido ou expirado."},
        status.HTTP_403_FORBIDDEN: {"description": "Permissão `prontuarios:escrever` ausente."},
        status.HTTP_409_CONFLICT: {"description": "Consulta já vinculada a outro prontuário."},
    },
)
def create_medical_record_endpoint(
    payload: MedicalRecordCreate,
    _: Annotated[User, Depends(require_permission("prontuarios:escrever"))],
    db: Annotated[Session, Depends(get_db)],
) -> MedicalRecordRead:
    try:
        record = create_medical_record(db, payload)
    except MedicalRecordPatientNotFoundError as exc:
        raise _invalid_patient_exception() from exc
    except MedicalRecordProfessionalNotFoundError as exc:
        raise _invalid_professional_exception() from exc
    except MedicalRecordAppointmentNotFoundError as exc:
        raise _invalid_appointment_exception() from exc
    except MedicalRecordAppointmentMismatchError as exc:
        raise _appointment_mismatch_exception() from exc
    except MedicalRecordDuplicateAppointmentError as exc:
        raise _duplicate_appointment_exception() from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Prontuário médico inválido.") from exc
    return MedicalRecordRead.model_validate(record)


@router.get(
    "",
    response_model=MedicalRecordList,
    summary="Listar prontuários médicos",
    description=(
        "Lista prontuários com filtros por paciente, profissional, consulta e status. "
        "Protegido por `prontuarios:ler`."
    ),
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "Token ausente, inválido ou expirado."},
        status.HTTP_403_FORBIDDEN: {"description": "Permissão `prontuarios:ler` ausente."},
    },
)
def list_medical_records_endpoint(
    search: Annotated[MedicalRecordSearch, Depends()],
    _: Annotated[User, Depends(require_permission("prontuarios:ler"))],
    db: Annotated[Session, Depends(get_db)],
) -> MedicalRecordList:
    records, total = search_medical_records(db, search)
    return MedicalRecordList(
        items=[MedicalRecordRead.model_validate(record) for record in records],
        total=total,
        page=search.page,
        page_size=search.page_size,
    )


@router.get(
    "/{record_id}",
    response_model=MedicalRecordRead,
    summary="Consultar prontuário médico por ID",
    description="Retorna dados clínicos do prontuário. Protegido por `prontuarios:ler`.",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "Token ausente, inválido ou expirado."},
        status.HTTP_403_FORBIDDEN: {"description": "Permissão `prontuarios:ler` ausente."},
        status.HTTP_404_NOT_FOUND: {"description": "Prontuário médico não encontrado."},
    },
)
def get_medical_record_endpoint(
    record_id: int,
    _: Annotated[User, Depends(require_permission("prontuarios:ler"))],
    db: Annotated[Session, Depends(get_db)],
) -> MedicalRecordRead:
    try:
        record = get_medical_record(db, record_id)
    except MedicalRecordNotFoundError as exc:
        raise _not_found_exception() from exc
    return MedicalRecordRead.model_validate(record)


@router.patch(
    "/{record_id}",
    response_model=MedicalRecordRead,
    summary="Atualizar prontuário médico",
    description="Atualiza dados clínicos e vínculos do prontuário. Protegido por `prontuarios:escrever`.",
    responses={
        status.HTTP_400_BAD_REQUEST: {"description": "Paciente, profissional ou consulta inválidos."},
        status.HTTP_401_UNAUTHORIZED: {"description": "Token ausente, inválido ou expirado."},
        status.HTTP_403_FORBIDDEN: {"description": "Permissão `prontuarios:escrever` ausente."},
        status.HTTP_404_NOT_FOUND: {"description": "Prontuário médico não encontrado."},
        status.HTTP_409_CONFLICT: {"description": "Consulta já vinculada a outro prontuário."},
    },
)
def update_medical_record_endpoint(
    record_id: int,
    payload: MedicalRecordUpdate,
    _: Annotated[User, Depends(require_permission("prontuarios:escrever"))],
    db: Annotated[Session, Depends(get_db)],
) -> MedicalRecordRead:
    try:
        record = update_medical_record(db, record_id, payload)
    except MedicalRecordNotFoundError as exc:
        raise _not_found_exception() from exc
    except MedicalRecordPatientNotFoundError as exc:
        raise _invalid_patient_exception() from exc
    except MedicalRecordProfessionalNotFoundError as exc:
        raise _invalid_professional_exception() from exc
    except MedicalRecordAppointmentNotFoundError as exc:
        raise _invalid_appointment_exception() from exc
    except MedicalRecordAppointmentMismatchError as exc:
        raise _appointment_mismatch_exception() from exc
    except MedicalRecordDuplicateAppointmentError as exc:
        raise _duplicate_appointment_exception() from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Prontuário médico inválido.") from exc
    return MedicalRecordRead.model_validate(record)
