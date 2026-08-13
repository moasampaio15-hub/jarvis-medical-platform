from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import require_permission
from app.database.session import get_db
from app.models.user import User
from app.schemas.appointment import (
    AppointmentCancel,
    AppointmentCreate,
    AppointmentList,
    AppointmentRead,
    AppointmentSearch,
    AppointmentStatusUpdate,
)
from app.services.appointments import (
    AppointmentConflictError,
    AppointmentNotFoundError,
    AppointmentPatientNotFoundError,
    AppointmentProfessionalNotFoundError,
    cancel_appointment,
    create_appointment,
    get_appointment,
    search_appointments,
    update_appointment_status,
)

router = APIRouter(prefix="/api/v1/appointments", tags=["Agenda e Consultas"])


def _not_found_exception() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Consulta não encontrada.")


def _invalid_patient_exception() -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Paciente não encontrado ou inativo.")


def _invalid_professional_exception() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Profissional de saúde não encontrado ou inativo.",
    )


def _conflict_exception(field: str) -> HTTPException:
    messages = {
        "profissional": "Conflito de horário para o profissional de saúde.",
        "paciente": "Conflito de horário para o paciente.",
    }
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=messages.get(field, "Conflito de horário para a consulta."),
    )


@router.post(
    "",
    response_model=AppointmentRead,
    status_code=status.HTTP_201_CREATED,
    summary="Criar consulta",
    description=(
        "Cria uma consulta na agenda vinculando paciente e profissional de saúde. "
        "Previne conflitos de horário para paciente e profissional. Protegido por `consultas:gerenciar`."
    ),
    responses={
        status.HTTP_400_BAD_REQUEST: {"description": "Paciente ou profissional inválido/inativo."},
        status.HTTP_401_UNAUTHORIZED: {"description": "Token ausente, inválido ou expirado."},
        status.HTTP_403_FORBIDDEN: {"description": "Permissão `consultas:gerenciar` ausente."},
        status.HTTP_409_CONFLICT: {"description": "Conflito de horário."},
    },
)
def create_appointment_endpoint(
    payload: AppointmentCreate,
    _: Annotated[User, Depends(require_permission("consultas:gerenciar"))],
    db: Annotated[Session, Depends(get_db)],
) -> AppointmentRead:
    try:
        appointment = create_appointment(db, payload)
    except AppointmentPatientNotFoundError as exc:
        raise _invalid_patient_exception() from exc
    except AppointmentProfessionalNotFoundError as exc:
        raise _invalid_professional_exception() from exc
    except AppointmentConflictError as exc:
        raise _conflict_exception(exc.field) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Consulta inválida ou conflitante.") from exc
    return AppointmentRead.model_validate(appointment)


@router.get(
    "",
    response_model=AppointmentList,
    summary="Listar consultas por período",
    description=(
        "Lista consultas por interseção de período, paciente, profissional e status. "
        "Protegido por `consultas:ler`."
    ),
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "Token ausente, inválido ou expirado."},
        status.HTTP_403_FORBIDDEN: {"description": "Permissão `consultas:ler` ausente."},
    },
)
def list_appointments_endpoint(
    search: Annotated[AppointmentSearch, Depends()],
    _: Annotated[User, Depends(require_permission("consultas:ler"))],
    db: Annotated[Session, Depends(get_db)],
) -> AppointmentList:
    appointments, total = search_appointments(db, search)
    return AppointmentList(
        items=[AppointmentRead.model_validate(appointment) for appointment in appointments],
        total=total,
        page=search.page,
        page_size=search.page_size,
    )


@router.get(
    "/{appointment_id}",
    response_model=AppointmentRead,
    summary="Consultar consulta por ID",
    description="Retorna os dados administrativos da consulta. Protegido por `consultas:ler`.",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "Token ausente, inválido ou expirado."},
        status.HTTP_403_FORBIDDEN: {"description": "Permissão `consultas:ler` ausente."},
        status.HTTP_404_NOT_FOUND: {"description": "Consulta não encontrada."},
    },
)
def get_appointment_endpoint(
    appointment_id: int,
    _: Annotated[User, Depends(require_permission("consultas:ler"))],
    db: Annotated[Session, Depends(get_db)],
) -> AppointmentRead:
    try:
        appointment = get_appointment(db, appointment_id)
    except AppointmentNotFoundError as exc:
        raise _not_found_exception() from exc
    return AppointmentRead.model_validate(appointment)


@router.patch(
    "/{appointment_id}/status",
    response_model=AppointmentRead,
    summary="Atualizar status da consulta",
    description=(
        "Atualiza o status da consulta. Ao reativar uma consulta cancelada para status ativo, "
        "a agenda é validada novamente contra conflitos. Protegido por `consultas:gerenciar`."
    ),
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "Token ausente, inválido ou expirado."},
        status.HTTP_403_FORBIDDEN: {"description": "Permissão `consultas:gerenciar` ausente."},
        status.HTTP_404_NOT_FOUND: {"description": "Consulta não encontrada."},
        status.HTTP_409_CONFLICT: {"description": "Conflito de horário."},
    },
)
def update_appointment_status_endpoint(
    appointment_id: int,
    payload: AppointmentStatusUpdate,
    _: Annotated[User, Depends(require_permission("consultas:gerenciar"))],
    db: Annotated[Session, Depends(get_db)],
) -> AppointmentRead:
    try:
        appointment = update_appointment_status(db, appointment_id, payload)
    except AppointmentNotFoundError as exc:
        raise _not_found_exception() from exc
    except AppointmentPatientNotFoundError as exc:
        raise _invalid_patient_exception() from exc
    except AppointmentProfessionalNotFoundError as exc:
        raise _invalid_professional_exception() from exc
    except AppointmentConflictError as exc:
        raise _conflict_exception(exc.field) from exc
    return AppointmentRead.model_validate(appointment)


@router.post(
    "/{appointment_id}/cancel",
    response_model=AppointmentRead,
    summary="Cancelar consulta",
    description=(
        "Cancela logicamente a consulta e libera o horário para novos agendamentos. "
        "Protegido por `consultas:gerenciar`."
    ),
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "Token ausente, inválido ou expirado."},
        status.HTTP_403_FORBIDDEN: {"description": "Permissão `consultas:gerenciar` ausente."},
        status.HTTP_404_NOT_FOUND: {"description": "Consulta não encontrada."},
    },
)
def cancel_appointment_endpoint(
    appointment_id: int,
    payload: AppointmentCancel,
    _: Annotated[User, Depends(require_permission("consultas:gerenciar"))],
    db: Annotated[Session, Depends(get_db)],
) -> AppointmentRead:
    try:
        appointment = cancel_appointment(db, appointment_id, payload)
    except AppointmentNotFoundError as exc:
        raise _not_found_exception() from exc
    return AppointmentRead.model_validate(appointment)
