from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.appointment import Appointment
from app.models.health_professional import HealthProfessional
from app.models.medical_record import MedicalRecord
from app.models.patient import Patient
from app.models.prescription import Prescription, PrescriptionItem
from app.schemas.appointment import AppointmentStatus
from app.schemas.prescription import (
    PrescriptionCreate,
    PrescriptionSearch,
    PrescriptionStatus,
    PrescriptionUpdate,
)


class PrescriptionNotFoundError(ValueError):
    pass


class PrescriptionPatientNotFoundError(ValueError):
    pass


class PrescriptionProfessionalNotFoundError(ValueError):
    pass


class PrescriptionAppointmentNotFoundError(ValueError):
    pass


class PrescriptionAppointmentMismatchError(ValueError):
    pass


class PrescriptionMedicalRecordNotFoundError(ValueError):
    pass


class PrescriptionMedicalRecordMismatchError(ValueError):
    pass


class PrescriptionMedicalRecordAppointmentMismatchError(ValueError):
    pass


def _status_value(status: PrescriptionStatus | str) -> str:
    return status.value if isinstance(status, PrescriptionStatus) else status


def _assert_patient_exists(db: Session, patient_id: int) -> None:
    patient = db.get(Patient, patient_id)
    if patient is None or not patient.ativo:
        raise PrescriptionPatientNotFoundError("Paciente não encontrado ou inativo.")


def _assert_professional_exists(db: Session, professional_id: int) -> None:
    professional = db.get(HealthProfessional, professional_id)
    if professional is None or not professional.ativo:
        raise PrescriptionProfessionalNotFoundError("Profissional de saúde não encontrado ou inativo.")


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
        raise PrescriptionAppointmentNotFoundError("Consulta não encontrada ou cancelada.")
    if appointment.patient_id != patient_id or appointment.professional_id != professional_id:
        raise PrescriptionAppointmentMismatchError(
            "Consulta não pertence ao paciente e profissional informados."
        )


def _assert_medical_record_matches(
    db: Session,
    medical_record_id: int | None,
    *,
    patient_id: int,
    professional_id: int,
    appointment_id: int | None,
) -> None:
    if medical_record_id is None:
        return

    medical_record = db.get(MedicalRecord, medical_record_id)
    if medical_record is None:
        raise PrescriptionMedicalRecordNotFoundError("Prontuário médico não encontrado.")
    if medical_record.patient_id != patient_id or medical_record.professional_id != professional_id:
        raise PrescriptionMedicalRecordMismatchError(
            "Prontuário não pertence ao paciente e profissional informados."
        )
    if (
        appointment_id is not None
        and medical_record.appointment_id is not None
        and medical_record.appointment_id != appointment_id
    ):
        raise PrescriptionMedicalRecordAppointmentMismatchError(
            "Consulta informada não corresponde ao prontuário vinculado."
        )


def _validate_links(
    db: Session,
    *,
    patient_id: int,
    professional_id: int,
    appointment_id: int | None,
    medical_record_id: int | None,
) -> None:
    _assert_patient_exists(db, patient_id)
    _assert_professional_exists(db, professional_id)
    _assert_appointment_matches(
        db,
        appointment_id,
        patient_id=patient_id,
        professional_id=professional_id,
    )
    _assert_medical_record_matches(
        db,
        medical_record_id,
        patient_id=patient_id,
        professional_id=professional_id,
        appointment_id=appointment_id,
    )


def _build_items(items: list[dict]) -> list[PrescriptionItem]:
    return [PrescriptionItem(**item) for item in items]


def create_prescription(db: Session, payload: PrescriptionCreate) -> Prescription:
    data = payload.model_dump()
    items_data = data.pop("items")
    _validate_links(
        db,
        patient_id=data["patient_id"],
        professional_id=data["professional_id"],
        appointment_id=data.get("appointment_id"),
        medical_record_id=data.get("medical_record_id"),
    )

    prescription = Prescription(**data, status=PrescriptionStatus.DRAFT.value)
    prescription.items = _build_items(items_data)
    db.add(prescription)
    db.commit()
    db.refresh(prescription)
    return prescription


def get_prescription(db: Session, prescription_id: int) -> Prescription:
    statement = (
        select(Prescription)
        .options(selectinload(Prescription.items))
        .where(Prescription.id == prescription_id)
    )
    prescription = db.scalar(statement)
    if prescription is None:
        raise PrescriptionNotFoundError("Prescrição não encontrada.")
    return prescription


def search_prescriptions(db: Session, search: PrescriptionSearch) -> tuple[list[Prescription], int]:
    statement = select(Prescription)

    if search.patient_id is not None:
        statement = statement.where(Prescription.patient_id == search.patient_id)
    if search.professional_id is not None:
        statement = statement.where(Prescription.professional_id == search.professional_id)
    if search.appointment_id is not None:
        statement = statement.where(Prescription.appointment_id == search.appointment_id)
    if search.medical_record_id is not None:
        statement = statement.where(Prescription.medical_record_id == search.medical_record_id)
    if search.status is not None:
        statement = statement.where(Prescription.status == _status_value(search.status))

    count_statement = select(func.count()).select_from(statement.subquery())
    total = int(db.scalar(count_statement) or 0)

    offset = (search.page - 1) * search.page_size
    rows = db.scalars(
        statement.options(selectinload(Prescription.items))
        .order_by(Prescription.created_at.desc(), Prescription.id.desc())
        .offset(offset)
        .limit(search.page_size)
    ).all()
    return list(rows), total


def update_prescription(db: Session, prescription_id: int, payload: PrescriptionUpdate) -> Prescription:
    prescription = get_prescription(db, prescription_id)
    data = payload.model_dump(exclude_unset=True)
    items_data = data.pop("items", None)

    patient_id = data.get("patient_id", prescription.patient_id)
    professional_id = data.get("professional_id", prescription.professional_id)
    appointment_id = data.get("appointment_id", prescription.appointment_id)
    medical_record_id = data.get("medical_record_id", prescription.medical_record_id)

    _validate_links(
        db,
        patient_id=patient_id,
        professional_id=professional_id,
        appointment_id=appointment_id,
        medical_record_id=medical_record_id,
    )

    if "status" in data and data["status"] is not None:
        data["status"] = _status_value(data["status"])

    for field, value in data.items():
        setattr(prescription, field, value)

    if items_data is not None:
        prescription.items = _build_items(items_data)

    db.commit()
    db.refresh(prescription)
    return prescription
