from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import require_permission
from app.database.session import get_db
from app.models.user import User
from app.schemas.prescription import (
    PrescriptionCreate,
    PrescriptionList,
    PrescriptionRead,
    PrescriptionSearch,
    PrescriptionUpdate,
)
from app.services.prescriptions import (
    PrescriptionAppointmentMismatchError,
    PrescriptionAppointmentNotFoundError,
    PrescriptionMedicalRecordAppointmentMismatchError,
    PrescriptionMedicalRecordMismatchError,
    PrescriptionMedicalRecordNotFoundError,
    PrescriptionNotFoundError,
    PrescriptionPatientNotFoundError,
    PrescriptionProfessionalNotFoundError,
    create_prescription,
    get_prescription,
    search_prescriptions,
    update_prescription,
)

router = APIRouter(prefix="/api/v1/prescriptions", tags=["Prescrições / Medicamentos"])


def _not_found_exception() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prescrição não encontrada.")


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


def _invalid_medical_record_exception() -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Prontuário médico não encontrado.")


def _medical_record_mismatch_exception() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Prontuário não pertence ao paciente e profissional informados.",
    )


def _medical_record_appointment_mismatch_exception() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Consulta informada não corresponde ao prontuário vinculado.",
    )


@router.post(
    "",
    response_model=PrescriptionRead,
    status_code=status.HTTP_201_CREATED,
    summary="Criar prescrição de medicamentos",
    description=(
        "Cria uma prescrição vinculada a paciente e profissional de saúde, com vínculo opcional "
        "a consulta e prontuário. Protegido por `medicamentos:escrever`."
    ),
    responses={
        status.HTTP_400_BAD_REQUEST: {"description": "Paciente, profissional, consulta ou prontuário inválido."},
        status.HTTP_401_UNAUTHORIZED: {"description": "Token ausente, inválido ou expirado."},
        status.HTTP_403_FORBIDDEN: {"description": "Permissão `medicamentos:escrever` ausente."},
        status.HTTP_409_CONFLICT: {"description": "Prescrição inválida."},
    },
)
def create_prescription_endpoint(
    payload: PrescriptionCreate,
    _: Annotated[User, Depends(require_permission("medicamentos:escrever"))],
    db: Annotated[Session, Depends(get_db)],
) -> PrescriptionRead:
    try:
        prescription = create_prescription(db, payload)
    except PrescriptionPatientNotFoundError as exc:
        raise _invalid_patient_exception() from exc
    except PrescriptionProfessionalNotFoundError as exc:
        raise _invalid_professional_exception() from exc
    except PrescriptionAppointmentNotFoundError as exc:
        raise _invalid_appointment_exception() from exc
    except PrescriptionAppointmentMismatchError as exc:
        raise _appointment_mismatch_exception() from exc
    except PrescriptionMedicalRecordNotFoundError as exc:
        raise _invalid_medical_record_exception() from exc
    except PrescriptionMedicalRecordMismatchError as exc:
        raise _medical_record_mismatch_exception() from exc
    except PrescriptionMedicalRecordAppointmentMismatchError as exc:
        raise _medical_record_appointment_mismatch_exception() from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Prescrição inválida.") from exc
    return PrescriptionRead.model_validate(prescription)


@router.get(
    "",
    response_model=PrescriptionList,
    summary="Listar prescrições de medicamentos",
    description=(
        "Lista prescrições com filtros por paciente, profissional, consulta, prontuário e status. "
        "Protegido por `medicamentos:ler`."
    ),
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "Token ausente, inválido ou expirado."},
        status.HTTP_403_FORBIDDEN: {"description": "Permissão `medicamentos:ler` ausente."},
    },
)
def list_prescriptions_endpoint(
    search: Annotated[PrescriptionSearch, Depends()],
    _: Annotated[User, Depends(require_permission("medicamentos:ler"))],
    db: Annotated[Session, Depends(get_db)],
) -> PrescriptionList:
    prescriptions, total = search_prescriptions(db, search)
    return PrescriptionList(
        items=[PrescriptionRead.model_validate(prescription) for prescription in prescriptions],
        total=total,
        page=search.page,
        page_size=search.page_size,
    )


@router.get(
    "/{prescription_id}",
    response_model=PrescriptionRead,
    summary="Consultar prescrição por ID",
    description="Retorna a prescrição e seus medicamentos. Protegido por `medicamentos:ler`.",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "Token ausente, inválido ou expirado."},
        status.HTTP_403_FORBIDDEN: {"description": "Permissão `medicamentos:ler` ausente."},
        status.HTTP_404_NOT_FOUND: {"description": "Prescrição não encontrada."},
    },
)
def get_prescription_endpoint(
    prescription_id: int,
    _: Annotated[User, Depends(require_permission("medicamentos:ler"))],
    db: Annotated[Session, Depends(get_db)],
) -> PrescriptionRead:
    try:
        prescription = get_prescription(db, prescription_id)
    except PrescriptionNotFoundError as exc:
        raise _not_found_exception() from exc
    return PrescriptionRead.model_validate(prescription)


@router.patch(
    "/{prescription_id}",
    response_model=PrescriptionRead,
    summary="Atualizar prescrição de medicamentos",
    description=(
        "Atualiza dados, vínculos, status e itens da prescrição. "
        "Protegido por `medicamentos:escrever`."
    ),
    responses={
        status.HTTP_400_BAD_REQUEST: {"description": "Paciente, profissional, consulta ou prontuário inválido."},
        status.HTTP_401_UNAUTHORIZED: {"description": "Token ausente, inválido ou expirado."},
        status.HTTP_403_FORBIDDEN: {"description": "Permissão `medicamentos:escrever` ausente."},
        status.HTTP_404_NOT_FOUND: {"description": "Prescrição não encontrada."},
        status.HTTP_409_CONFLICT: {"description": "Prescrição inválida."},
    },
)
def update_prescription_endpoint(
    prescription_id: int,
    payload: PrescriptionUpdate,
    _: Annotated[User, Depends(require_permission("medicamentos:escrever"))],
    db: Annotated[Session, Depends(get_db)],
) -> PrescriptionRead:
    try:
        prescription = update_prescription(db, prescription_id, payload)
    except PrescriptionNotFoundError as exc:
        raise _not_found_exception() from exc
    except PrescriptionPatientNotFoundError as exc:
        raise _invalid_patient_exception() from exc
    except PrescriptionProfessionalNotFoundError as exc:
        raise _invalid_professional_exception() from exc
    except PrescriptionAppointmentNotFoundError as exc:
        raise _invalid_appointment_exception() from exc
    except PrescriptionAppointmentMismatchError as exc:
        raise _appointment_mismatch_exception() from exc
    except PrescriptionMedicalRecordNotFoundError as exc:
        raise _invalid_medical_record_exception() from exc
    except PrescriptionMedicalRecordMismatchError as exc:
        raise _medical_record_mismatch_exception() from exc
    except PrescriptionMedicalRecordAppointmentMismatchError as exc:
        raise _medical_record_appointment_mismatch_exception() from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Prescrição inválida.") from exc
    return PrescriptionRead.model_validate(prescription)
