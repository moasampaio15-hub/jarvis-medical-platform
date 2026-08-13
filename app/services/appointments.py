from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.appointment import Appointment
from app.models.health_professional import HealthProfessional
from app.models.patient import Patient
from app.schemas.appointment import (
    AppointmentCancel,
    AppointmentCreate,
    AppointmentSearch,
    AppointmentStatus,
    AppointmentStatusUpdate,
)

ACTIVE_CONFLICT_STATUSES = (AppointmentStatus.SCHEDULED.value, AppointmentStatus.CONFIRMED.value)


class AppointmentNotFoundError(ValueError):
    pass


class AppointmentPatientNotFoundError(ValueError):
    pass


class AppointmentProfessionalNotFoundError(ValueError):
    pass


class AppointmentConflictError(ValueError):
    def __init__(self, field: str) -> None:
        self.field = field
        super().__init__(f"Conflito de horário para {field}.")


def _status_value(status: AppointmentStatus | str) -> str:
    return status.value if isinstance(status, AppointmentStatus) else status


def _assert_patient_exists(db: Session, patient_id: int) -> None:
    patient = db.get(Patient, patient_id)
    if patient is None or not patient.ativo:
        raise AppointmentPatientNotFoundError("Paciente não encontrado ou inativo.")


def _assert_professional_exists(db: Session, professional_id: int) -> None:
    professional = db.get(HealthProfessional, professional_id)
    if professional is None or not professional.ativo:
        raise AppointmentProfessionalNotFoundError("Profissional de saúde não encontrado ou inativo.")


def _has_overlap(
    db: Session,
    *,
    patient_id: int | None = None,
    professional_id: int | None = None,
    start_at: datetime,
    end_at: datetime,
    exclude_appointment_id: int | None = None,
) -> bool:
    statement = select(Appointment.id).where(
        Appointment.status.in_(ACTIVE_CONFLICT_STATUSES),
        Appointment.start_at < end_at,
        Appointment.end_at > start_at,
    )
    if patient_id is not None:
        statement = statement.where(Appointment.patient_id == patient_id)
    if professional_id is not None:
        statement = statement.where(Appointment.professional_id == professional_id)
    if exclude_appointment_id is not None:
        statement = statement.where(Appointment.id != exclude_appointment_id)
    return db.scalar(statement) is not None


def _assert_no_time_conflicts(
    db: Session,
    *,
    patient_id: int,
    professional_id: int,
    start_at: datetime,
    end_at: datetime,
    exclude_appointment_id: int | None = None,
) -> None:
    if _has_overlap(
        db,
        professional_id=professional_id,
        start_at=start_at,
        end_at=end_at,
        exclude_appointment_id=exclude_appointment_id,
    ):
        raise AppointmentConflictError("profissional")
    if _has_overlap(
        db,
        patient_id=patient_id,
        start_at=start_at,
        end_at=end_at,
        exclude_appointment_id=exclude_appointment_id,
    ):
        raise AppointmentConflictError("paciente")


def create_appointment(db: Session, payload: AppointmentCreate) -> Appointment:
    data = payload.model_dump()
    _assert_patient_exists(db, data["patient_id"])
    _assert_professional_exists(db, data["professional_id"])
    _assert_no_time_conflicts(
        db,
        patient_id=data["patient_id"],
        professional_id=data["professional_id"],
        start_at=data["start_at"],
        end_at=data["end_at"],
    )

    appointment = Appointment(**data, status=AppointmentStatus.SCHEDULED.value)
    db.add(appointment)
    db.commit()
    db.refresh(appointment)
    return appointment


def get_appointment(db: Session, appointment_id: int) -> Appointment:
    appointment = db.get(Appointment, appointment_id)
    if appointment is None:
        raise AppointmentNotFoundError("Consulta não encontrada.")
    return appointment


def search_appointments(db: Session, search: AppointmentSearch) -> tuple[list[Appointment], int]:
    statement = select(Appointment)

    if search.start_at is not None:
        statement = statement.where(Appointment.end_at > search.start_at)
    if search.end_at is not None:
        statement = statement.where(Appointment.start_at < search.end_at)
    if search.patient_id is not None:
        statement = statement.where(Appointment.patient_id == search.patient_id)
    if search.professional_id is not None:
        statement = statement.where(Appointment.professional_id == search.professional_id)
    if search.status is not None:
        statement = statement.where(Appointment.status == _status_value(search.status))

    count_statement = select(func.count()).select_from(statement.subquery())
    total = int(db.scalar(count_statement) or 0)

    offset = (search.page - 1) * search.page_size
    rows = db.scalars(
        statement.order_by(Appointment.start_at.asc(), Appointment.id.asc()).offset(offset).limit(search.page_size)
    ).all()
    return list(rows), total


def update_appointment_status(db: Session, appointment_id: int, payload: AppointmentStatusUpdate) -> Appointment:
    appointment = get_appointment(db, appointment_id)
    target_status = _status_value(payload.status)

    if target_status in ACTIVE_CONFLICT_STATUSES:
        _assert_patient_exists(db, appointment.patient_id)
        _assert_professional_exists(db, appointment.professional_id)
        _assert_no_time_conflicts(
            db,
            patient_id=appointment.patient_id,
            professional_id=appointment.professional_id,
            start_at=appointment.start_at,
            end_at=appointment.end_at,
            exclude_appointment_id=appointment.id,
        )
        appointment.cancel_reason = None
        appointment.canceled_at = None

    if target_status == AppointmentStatus.CANCELED.value and appointment.canceled_at is None:
        appointment.canceled_at = datetime.now(timezone.utc)

    appointment.status = target_status
    db.commit()
    db.refresh(appointment)
    return appointment


def cancel_appointment(db: Session, appointment_id: int, payload: AppointmentCancel) -> Appointment:
    appointment = get_appointment(db, appointment_id)
    appointment.status = AppointmentStatus.CANCELED.value
    appointment.cancel_reason = payload.cancel_reason
    if appointment.canceled_at is None:
        appointment.canceled_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(appointment)
    return appointment
