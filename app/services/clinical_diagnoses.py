from __future__ import annotations

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.appointment import Appointment
from app.models.clinical_diagnosis import ClinicalDiagnosis
from app.models.health_professional import HealthProfessional
from app.models.medical_record import MedicalRecord
from app.models.patient import Patient
from app.schemas.appointment import AppointmentStatus
from app.schemas.clinical_diagnosis import ClinicalDiagnosisCreate, ClinicalDiagnosisSearch, ClinicalDiagnosisUpdate


class ClinicalDiagnosisNotFoundError(ValueError):
    pass


class ClinicalDiagnosisPatientNotFoundError(ValueError):
    pass


class ClinicalDiagnosisProfessionalNotFoundError(ValueError):
    pass


class ClinicalDiagnosisAppointmentNotFoundError(ValueError):
    pass


class ClinicalDiagnosisAppointmentMismatchError(ValueError):
    pass


class ClinicalDiagnosisMedicalRecordNotFoundError(ValueError):
    pass


class ClinicalDiagnosisMedicalRecordMismatchError(ValueError):
    pass


class ClinicalDiagnosisInvalidDateRangeError(ValueError):
    pass


def _assert_patient_exists(db: Session, patient_id: int) -> None:
    patient = db.get(Patient, patient_id)
    if patient is None or not patient.ativo:
        raise ClinicalDiagnosisPatientNotFoundError("Paciente não encontrado ou inativo.")


def _assert_professional_exists(db: Session, professional_id: int) -> None:
    professional = db.get(HealthProfessional, professional_id)
    if professional is None or not professional.ativo:
        raise ClinicalDiagnosisProfessionalNotFoundError("Profissional de saúde não encontrado ou inativo.")


def _assert_appointment_matches(db: Session, appointment_id: int | None, *, patient_id: int, professional_id: int) -> None:
    if appointment_id is None:
        return

    appointment = db.get(Appointment, appointment_id)
    if appointment is None or appointment.status == AppointmentStatus.CANCELED.value:
        raise ClinicalDiagnosisAppointmentNotFoundError("Consulta não encontrada ou cancelada.")
    if appointment.patient_id != patient_id or appointment.professional_id != professional_id:
        raise ClinicalDiagnosisAppointmentMismatchError("Consulta não pertence ao paciente e profissional informados.")


def _assert_medical_record_matches(db: Session, medical_record_id: int | None, *, patient_id: int) -> None:
    if medical_record_id is None:
        return

    medical_record = db.get(MedicalRecord, medical_record_id)
    if medical_record is None:
        raise ClinicalDiagnosisMedicalRecordNotFoundError("Prontuário médico não encontrado.")
    if medical_record.patient_id != patient_id:
        raise ClinicalDiagnosisMedicalRecordMismatchError("Prontuário não pertence ao paciente informado.")


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


def _validate_date_range(data_inicio: date | None, data_resolucao: date | None) -> None:
    if data_inicio is not None and data_resolucao is not None and data_resolucao < data_inicio:
        raise ClinicalDiagnosisInvalidDateRangeError("Data de resolução não pode ser anterior à data de início.")


def create_clinical_diagnosis(db: Session, payload: ClinicalDiagnosisCreate) -> ClinicalDiagnosis:
    data = payload.model_dump()
    _validate_links(
        db,
        patient_id=data["patient_id"],
        professional_id=data["professional_id"],
        appointment_id=data.get("appointment_id"),
        medical_record_id=data.get("medical_record_id"),
    )
    _validate_date_range(data.get("data_inicio"), data.get("data_resolucao"))

    diagnosis = ClinicalDiagnosis(**data)
    db.add(diagnosis)
    db.commit()
    db.refresh(diagnosis)
    return diagnosis


def get_clinical_diagnosis(db: Session, diagnosis_id: int) -> ClinicalDiagnosis:
    diagnosis = db.get(ClinicalDiagnosis, diagnosis_id)
    if diagnosis is None:
        raise ClinicalDiagnosisNotFoundError("Diagnóstico/problema clínico não encontrado.")
    return diagnosis


def search_clinical_diagnoses(db: Session, search: ClinicalDiagnosisSearch) -> tuple[list[ClinicalDiagnosis], int]:
    statement = select(ClinicalDiagnosis)

    if search.patient_id is not None:
        statement = statement.where(ClinicalDiagnosis.patient_id == search.patient_id)
    if search.professional_id is not None:
        statement = statement.where(ClinicalDiagnosis.professional_id == search.professional_id)
    if search.appointment_id is not None:
        statement = statement.where(ClinicalDiagnosis.appointment_id == search.appointment_id)
    if search.medical_record_id is not None:
        statement = statement.where(ClinicalDiagnosis.medical_record_id == search.medical_record_id)
    if search.cid10_codigo is not None:
        statement = statement.where(ClinicalDiagnosis.cid10_codigo == search.cid10_codigo)
    if search.tipo is not None:
        statement = statement.where(ClinicalDiagnosis.tipo == search.tipo)
    if search.status is not None:
        statement = statement.where(ClinicalDiagnosis.status == search.status)

    count_statement = select(func.count()).select_from(statement.subquery())
    total = int(db.scalar(count_statement) or 0)

    offset = (search.page - 1) * search.page_size
    rows = db.scalars(
        statement.order_by(ClinicalDiagnosis.created_at.desc(), ClinicalDiagnosis.id.desc())
        .offset(offset)
        .limit(search.page_size)
    ).all()
    return list(rows), total


def update_clinical_diagnosis(db: Session, diagnosis_id: int, payload: ClinicalDiagnosisUpdate) -> ClinicalDiagnosis:
    diagnosis = get_clinical_diagnosis(db, diagnosis_id)
    data = payload.model_dump(exclude_unset=True)

    patient_id = data.get("patient_id", diagnosis.patient_id)
    professional_id = data.get("professional_id", diagnosis.professional_id)
    appointment_id = data.get("appointment_id", diagnosis.appointment_id)
    medical_record_id = data.get("medical_record_id", diagnosis.medical_record_id)
    data_inicio = data.get("data_inicio", diagnosis.data_inicio)
    data_resolucao = data.get("data_resolucao", diagnosis.data_resolucao)

    _validate_links(
        db,
        patient_id=patient_id,
        professional_id=professional_id,
        appointment_id=appointment_id,
        medical_record_id=medical_record_id,
    )
    _validate_date_range(data_inicio, data_resolucao)

    for field, value in data.items():
        setattr(diagnosis, field, value)

    db.commit()
    db.refresh(diagnosis)
    return diagnosis
