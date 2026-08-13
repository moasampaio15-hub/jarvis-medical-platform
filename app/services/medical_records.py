from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.appointment import Appointment
from app.models.health_professional import HealthProfessional
from app.models.medical_record import MedicalRecord
from app.models.patient import Patient
from app.schemas.appointment import AppointmentStatus
from app.schemas.medical_record import (
    MedicalRecordCreate,
    MedicalRecordSearch,
    MedicalRecordStatus,
    MedicalRecordUpdate,
)


class MedicalRecordNotFoundError(ValueError):
    pass


class MedicalRecordPatientNotFoundError(ValueError):
    pass


class MedicalRecordProfessionalNotFoundError(ValueError):
    pass


class MedicalRecordAppointmentNotFoundError(ValueError):
    pass


class MedicalRecordAppointmentMismatchError(ValueError):
    pass


class MedicalRecordDuplicateAppointmentError(ValueError):
    pass


def _status_value(status: MedicalRecordStatus | str) -> str:
    return status.value if isinstance(status, MedicalRecordStatus) else status


def _assert_patient_exists(db: Session, patient_id: int) -> None:
    patient = db.get(Patient, patient_id)
    if patient is None or not patient.ativo:
        raise MedicalRecordPatientNotFoundError("Paciente não encontrado ou inativo.")


def _assert_professional_exists(db: Session, professional_id: int) -> None:
    professional = db.get(HealthProfessional, professional_id)
    if professional is None or not professional.ativo:
        raise MedicalRecordProfessionalNotFoundError("Profissional de saúde não encontrado ou inativo.")


def _assert_unique_appointment(
    db: Session,
    appointment_id: int | None,
    *,
    exclude_record_id: int | None = None,
) -> None:
    if appointment_id is None:
        return

    statement = select(MedicalRecord.id).where(MedicalRecord.appointment_id == appointment_id)
    if exclude_record_id is not None:
        statement = statement.where(MedicalRecord.id != exclude_record_id)
    if db.scalar(statement) is not None:
        raise MedicalRecordDuplicateAppointmentError("Consulta já vinculada a outro prontuário.")


def _assert_appointment_matches(
    db: Session,
    appointment_id: int | None,
    *,
    patient_id: int,
    professional_id: int,
) -> None:
    if appointment_id is None:
        return

    appointment = db.get(Appointment, appointment_id)
    if appointment is None or appointment.status == AppointmentStatus.CANCELED.value:
        raise MedicalRecordAppointmentNotFoundError("Consulta não encontrada ou cancelada.")
    if appointment.patient_id != patient_id or appointment.professional_id != professional_id:
        raise MedicalRecordAppointmentMismatchError(
            "Consulta não pertence ao paciente e profissional informados."
        )


def _validate_links(
    db: Session,
    *,
    patient_id: int,
    professional_id: int,
    appointment_id: int | None,
    exclude_record_id: int | None = None,
) -> None:
    _assert_patient_exists(db, patient_id)
    _assert_professional_exists(db, professional_id)
    _assert_appointment_matches(
        db,
        appointment_id,
        patient_id=patient_id,
        professional_id=professional_id,
    )
    _assert_unique_appointment(db, appointment_id, exclude_record_id=exclude_record_id)


def create_medical_record(db: Session, payload: MedicalRecordCreate) -> MedicalRecord:
    data = payload.model_dump()
    _validate_links(
        db,
        patient_id=data["patient_id"],
        professional_id=data["professional_id"],
        appointment_id=data.get("appointment_id"),
    )

    record = MedicalRecord(**data, status=MedicalRecordStatus.DRAFT.value)
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def get_medical_record(db: Session, record_id: int) -> MedicalRecord:
    record = db.get(MedicalRecord, record_id)
    if record is None:
        raise MedicalRecordNotFoundError("Prontuário médico não encontrado.")
    return record


def search_medical_records(db: Session, search: MedicalRecordSearch) -> tuple[list[MedicalRecord], int]:
    statement = select(MedicalRecord)

    if search.patient_id is not None:
        statement = statement.where(MedicalRecord.patient_id == search.patient_id)
    if search.professional_id is not None:
        statement = statement.where(MedicalRecord.professional_id == search.professional_id)
    if search.appointment_id is not None:
        statement = statement.where(MedicalRecord.appointment_id == search.appointment_id)
    if search.status is not None:
        statement = statement.where(MedicalRecord.status == _status_value(search.status))

    count_statement = select(func.count()).select_from(statement.subquery())
    total = int(db.scalar(count_statement) or 0)

    offset = (search.page - 1) * search.page_size
    rows = db.scalars(
        statement.order_by(MedicalRecord.created_at.desc(), MedicalRecord.id.desc())
        .offset(offset)
        .limit(search.page_size)
    ).all()
    return list(rows), total


def update_medical_record(db: Session, record_id: int, payload: MedicalRecordUpdate) -> MedicalRecord:
    record = get_medical_record(db, record_id)
    data = payload.model_dump(exclude_unset=True)

    patient_id = data.get("patient_id", record.patient_id)
    professional_id = data.get("professional_id", record.professional_id)
    appointment_id = data.get("appointment_id", record.appointment_id)

    _validate_links(
        db,
        patient_id=patient_id,
        professional_id=professional_id,
        appointment_id=appointment_id,
        exclude_record_id=record.id,
    )

    if "status" in data and data["status"] is not None:
        data["status"] = _status_value(data["status"])

    for field, value in data.items():
        setattr(record, field, value)

    db.commit()
    db.refresh(record)
    return record
