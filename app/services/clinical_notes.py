from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.appointment import Appointment
from app.models.clinical_note import ClinicalNote
from app.models.health_professional import HealthProfessional
from app.models.medical_record import MedicalRecord
from app.models.patient import Patient
from app.schemas.appointment import AppointmentStatus
from app.schemas.clinical_note import ClinicalNoteCreate, ClinicalNoteSearch, ClinicalNoteUpdate, NOTE_CONTENT_FIELDS


class ClinicalNoteNotFoundError(ValueError):
    pass


class ClinicalNotePatientNotFoundError(ValueError):
    pass


class ClinicalNoteProfessionalNotFoundError(ValueError):
    pass


class ClinicalNoteAppointmentNotFoundError(ValueError):
    pass


class ClinicalNoteAppointmentMismatchError(ValueError):
    pass


class ClinicalNoteMedicalRecordNotFoundError(ValueError):
    pass


class ClinicalNoteMedicalRecordMismatchError(ValueError):
    pass


class ClinicalNoteEmptyContentError(ValueError):
    pass


def _assert_patient_exists(db: Session, patient_id: int) -> None:
    patient = db.get(Patient, patient_id)
    if patient is None or not patient.ativo:
        raise ClinicalNotePatientNotFoundError("Paciente não encontrado ou inativo.")


def _assert_professional_exists(db: Session, professional_id: int) -> None:
    professional = db.get(HealthProfessional, professional_id)
    if professional is None or not professional.ativo:
        raise ClinicalNoteProfessionalNotFoundError("Profissional de saúde não encontrado ou inativo.")


def _assert_appointment_matches(db: Session, appointment_id: int | None, *, patient_id: int, professional_id: int) -> None:
    if appointment_id is None:
        return

    appointment = db.get(Appointment, appointment_id)
    if appointment is None or appointment.status == AppointmentStatus.CANCELED.value:
        raise ClinicalNoteAppointmentNotFoundError("Consulta não encontrada ou cancelada.")
    if appointment.patient_id != patient_id or appointment.professional_id != professional_id:
        raise ClinicalNoteAppointmentMismatchError("Consulta não pertence ao paciente e profissional informados.")


def _assert_medical_record_matches(db: Session, medical_record_id: int | None, *, patient_id: int) -> None:
    if medical_record_id is None:
        return

    medical_record = db.get(MedicalRecord, medical_record_id)
    if medical_record is None:
        raise ClinicalNoteMedicalRecordNotFoundError("Prontuário médico não encontrado.")
    if medical_record.patient_id != patient_id:
        raise ClinicalNoteMedicalRecordMismatchError("Prontuário não pertence ao paciente informado.")


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
    _assert_appointment_matches(db, appointment_id, patient_id=patient_id, professional_id=professional_id)
    _assert_medical_record_matches(db, medical_record_id, patient_id=patient_id)


def _validate_content(data: dict, note: ClinicalNote | None = None) -> None:
    values = {field: getattr(note, field, None) for field in NOTE_CONTENT_FIELDS} if note else {}
    values.update({field: data[field] for field in NOTE_CONTENT_FIELDS if field in data})
    if not any(values.get(field) for field in NOTE_CONTENT_FIELDS):
        raise ClinicalNoteEmptyContentError("Informe ao menos um campo clínico da nota.")


def create_clinical_note(db: Session, payload: ClinicalNoteCreate) -> ClinicalNote:
    data = payload.model_dump()
    if data.get("recorded_at") is None:
        data.pop("recorded_at", None)
    _validate_links(
        db,
        patient_id=data["patient_id"],
        professional_id=data["professional_id"],
        appointment_id=data.get("appointment_id"),
        medical_record_id=data.get("medical_record_id"),
    )
    _validate_content(data)

    note = ClinicalNote(**data)
    db.add(note)
    db.commit()
    db.refresh(note)
    return note


def get_clinical_note(db: Session, note_id: int) -> ClinicalNote:
    note = db.get(ClinicalNote, note_id)
    if note is None:
        raise ClinicalNoteNotFoundError("Nota clínica não encontrada.")
    return note


def search_clinical_notes(db: Session, search: ClinicalNoteSearch) -> tuple[list[ClinicalNote], int]:
    statement = select(ClinicalNote)

    if search.patient_id is not None:
        statement = statement.where(ClinicalNote.patient_id == search.patient_id)
    if search.professional_id is not None:
        statement = statement.where(ClinicalNote.professional_id == search.professional_id)
    if search.appointment_id is not None:
        statement = statement.where(ClinicalNote.appointment_id == search.appointment_id)
    if search.medical_record_id is not None:
        statement = statement.where(ClinicalNote.medical_record_id == search.medical_record_id)
    if search.tipo is not None:
        statement = statement.where(ClinicalNote.tipo == search.tipo)
    if search.recorded_from is not None:
        statement = statement.where(ClinicalNote.recorded_at >= search.recorded_from)
    if search.recorded_to is not None:
        statement = statement.where(ClinicalNote.recorded_at <= search.recorded_to)

    count_statement = select(func.count()).select_from(statement.subquery())
    total = int(db.scalar(count_statement) or 0)

    offset = (search.page - 1) * search.page_size
    rows = db.scalars(
        statement.order_by(ClinicalNote.recorded_at.desc(), ClinicalNote.id.desc())
        .offset(offset)
        .limit(search.page_size)
    ).all()
    return list(rows), total


def update_clinical_note(db: Session, note_id: int, payload: ClinicalNoteUpdate) -> ClinicalNote:
    note = get_clinical_note(db, note_id)
    data = payload.model_dump(exclude_unset=True)
    if data.get("recorded_at") is None:
        data.pop("recorded_at", None)

    patient_id = data.get("patient_id", note.patient_id)
    professional_id = data.get("professional_id", note.professional_id)
    appointment_id = data.get("appointment_id", note.appointment_id)
    medical_record_id = data.get("medical_record_id", note.medical_record_id)
    _validate_links(
        db,
        patient_id=patient_id,
        professional_id=professional_id,
        appointment_id=appointment_id,
        medical_record_id=medical_record_id,
    )
    _validate_content(data, note)

    for field, value in data.items():
        setattr(note, field, value)

    db.commit()
    db.refresh(note)
    return note
