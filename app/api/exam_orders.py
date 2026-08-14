from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import require_permission
from app.database.session import get_db
from app.models.user import User
from app.schemas.exam_order import (
    ExamOrderCreate,
    ExamOrderList,
    ExamOrderRead,
    ExamOrderSearch,
    ExamOrderUpdate,
)
from app.services.exam_orders import (
    ExamOrderAppointmentMismatchError,
    ExamOrderAppointmentNotFoundError,
    ExamOrderMedicalRecordAppointmentMismatchError,
    ExamOrderMedicalRecordMismatchError,
    ExamOrderMedicalRecordNotFoundError,
    ExamOrderNotFoundError,
    ExamOrderPatientNotFoundError,
    ExamOrderProfessionalNotFoundError,
    create_exam_order,
    get_exam_order,
    search_exam_orders,
    update_exam_order,
)

router = APIRouter(prefix="/api/v1/exam-orders", tags=["Solicitações de Exames"])


def _not_found_exception() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Solicitação de exame não encontrada.")


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
    response_model=ExamOrderRead,
    status_code=status.HTTP_201_CREATED,
    summary="Criar solicitação de exames",
    description=(
        "Cria uma solicitação de exames vinculada a paciente e profissional de saúde, com vínculo opcional "
        "a consulta e prontuário. Protegido por `exames:gerenciar`."
    ),
    responses={
        status.HTTP_400_BAD_REQUEST: {"description": "Paciente, profissional, consulta ou prontuário inválido."},
        status.HTTP_401_UNAUTHORIZED: {"description": "Token ausente, inválido ou expirado."},
        status.HTTP_403_FORBIDDEN: {"description": "Permissão `exames:gerenciar` ausente."},
        status.HTTP_409_CONFLICT: {"description": "Solicitação de exame inválida."},
    },
)
def create_exam_order_endpoint(
    payload: ExamOrderCreate,
    _: Annotated[User, Depends(require_permission("exames:gerenciar"))],
    db: Annotated[Session, Depends(get_db)],
) -> ExamOrderRead:
    try:
        exam_order = create_exam_order(db, payload)
    except ExamOrderPatientNotFoundError as exc:
        raise _invalid_patient_exception() from exc
    except ExamOrderProfessionalNotFoundError as exc:
        raise _invalid_professional_exception() from exc
    except ExamOrderAppointmentNotFoundError as exc:
        raise _invalid_appointment_exception() from exc
    except ExamOrderAppointmentMismatchError as exc:
        raise _appointment_mismatch_exception() from exc
    except ExamOrderMedicalRecordNotFoundError as exc:
        raise _invalid_medical_record_exception() from exc
    except ExamOrderMedicalRecordMismatchError as exc:
        raise _medical_record_mismatch_exception() from exc
    except ExamOrderMedicalRecordAppointmentMismatchError as exc:
        raise _medical_record_appointment_mismatch_exception() from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Solicitação de exame inválida.") from exc
    return ExamOrderRead.model_validate(exam_order)


@router.get(
    "",
    response_model=ExamOrderList,
    summary="Listar solicitações de exames",
    description=(
        "Lista solicitações de exames com filtros por paciente, profissional, consulta, prontuário, "
        "status e prioridade. Protegido por `exames:ler`."
    ),
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "Token ausente, inválido ou expirado."},
        status.HTTP_403_FORBIDDEN: {"description": "Permissão `exames:ler` ausente."},
    },
)
def list_exam_orders_endpoint(
    search: Annotated[ExamOrderSearch, Depends()],
    _: Annotated[User, Depends(require_permission("exames:ler"))],
    db: Annotated[Session, Depends(get_db)],
) -> ExamOrderList:
    exam_orders, total = search_exam_orders(db, search)
    return ExamOrderList(
        items=[ExamOrderRead.model_validate(exam_order) for exam_order in exam_orders],
        total=total,
        page=search.page,
        page_size=search.page_size,
    )


@router.get(
    "/{exam_order_id}",
    response_model=ExamOrderRead,
    summary="Consultar solicitação de exame por ID",
    description="Retorna a solicitação de exame e seus itens. Protegido por `exames:ler`.",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "Token ausente, inválido ou expirado."},
        status.HTTP_403_FORBIDDEN: {"description": "Permissão `exames:ler` ausente."},
        status.HTTP_404_NOT_FOUND: {"description": "Solicitação de exame não encontrada."},
    },
)
def get_exam_order_endpoint(
    exam_order_id: int,
    _: Annotated[User, Depends(require_permission("exames:ler"))],
    db: Annotated[Session, Depends(get_db)],
) -> ExamOrderRead:
    try:
        exam_order = get_exam_order(db, exam_order_id)
    except ExamOrderNotFoundError as exc:
        raise _not_found_exception() from exc
    return ExamOrderRead.model_validate(exam_order)


@router.patch(
    "/{exam_order_id}",
    response_model=ExamOrderRead,
    summary="Atualizar solicitação de exames",
    description=(
        "Atualiza dados, vínculos, status, prioridade e itens da solicitação de exames. "
        "Protegido por `exames:gerenciar`."
    ),
    responses={
        status.HTTP_400_BAD_REQUEST: {"description": "Paciente, profissional, consulta ou prontuário inválido."},
        status.HTTP_401_UNAUTHORIZED: {"description": "Token ausente, inválido ou expirado."},
        status.HTTP_403_FORBIDDEN: {"description": "Permissão `exames:gerenciar` ausente."},
        status.HTTP_404_NOT_FOUND: {"description": "Solicitação de exame não encontrada."},
        status.HTTP_409_CONFLICT: {"description": "Solicitação de exame inválida."},
    },
)
def update_exam_order_endpoint(
    exam_order_id: int,
    payload: ExamOrderUpdate,
    _: Annotated[User, Depends(require_permission("exames:gerenciar"))],
    db: Annotated[Session, Depends(get_db)],
) -> ExamOrderRead:
    try:
        exam_order = update_exam_order(db, exam_order_id, payload)
    except ExamOrderNotFoundError as exc:
        raise _not_found_exception() from exc
    except ExamOrderPatientNotFoundError as exc:
        raise _invalid_patient_exception() from exc
    except ExamOrderProfessionalNotFoundError as exc:
        raise _invalid_professional_exception() from exc
    except ExamOrderAppointmentNotFoundError as exc:
        raise _invalid_appointment_exception() from exc
    except ExamOrderAppointmentMismatchError as exc:
        raise _appointment_mismatch_exception() from exc
    except ExamOrderMedicalRecordNotFoundError as exc:
        raise _invalid_medical_record_exception() from exc
    except ExamOrderMedicalRecordMismatchError as exc:
        raise _medical_record_mismatch_exception() from exc
    except ExamOrderMedicalRecordAppointmentMismatchError as exc:
        raise _medical_record_appointment_mismatch_exception() from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Solicitação de exame inválida.") from exc
    return ExamOrderRead.model_validate(exam_order)
