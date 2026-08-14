from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.health_professional import HealthProfessional
from app.models.medical_record import MedicalRecord
from app.models.patient import Patient
from app.models.patient_allergy import PatientAllergy
from app.schemas.patient_allergy import PatientAllergyCreate, PatientAllergySearch, PatientAllergyUpdate


class PatientAllergyNotFoundError(ValueError):
    pass


class PatientAllergyPatientNotFoundError(ValueError):
    pass


class PatientAllergyProfessionalNotFoundError(ValueError):
    pass


class PatientAllergyMedicalRecordNotFoundError(ValueError):
    pass


class PatientAllergyMedicalRecordMismatchError(ValueError):
    pass


def _assert_patient_exists(db: Session, patient_id: int) -> None:
    patient = db.get(Patient, patient_id)
    if patient is None or not patient.ativo:
        raise PatientAllergyPatientNotFoundError("Paciente não encontrado ou inativo.")


def _assert_professional_exists(db: Session, professional_id: int) -> None:
    professional = db.get(HealthProfessional, professional_id)
    if professional is None or not professional.ativo:
        raise PatientAllergyProfessionalNotFoundError("Profissional de saúde não encontrado ou inativo.")


def _assert_medical_record_matches(db: Session, medical_record_id: int | None, *, patient_id: int) -> None:
    if medical_record_id is None:
        return

    medical_record = db.get(MedicalRecord, medical_record_id)
    if medical_record is None:
        raise PatientAllergyMedicalRecordNotFoundError("Prontuário médico não encontrado.")
    if medical_record.patient_id != patient_id:
        raise PatientAllergyMedicalRecordMismatchError("Prontuário não pertence ao paciente informado.")


def _validate_links(db: Session, *, patient_id: int, professional_id: int, medical_record_id: int | None) -> None:
    _assert_patient_exists(db, patient_id)
    _assert_professional_exists(db, professional_id)
    _assert_medical_record_matches(db, medical_record_id, patient_id=patient_id)


def create_patient_allergy(db: Session, payload: PatientAllergyCreate) -> PatientAllergy:
    data = payload.model_dump()
    _validate_links(
        db,
        patient_id=data["patient_id"],
        professional_id=data["professional_id"],
        medical_record_id=data.get("medical_record_id"),
    )

    allergy = PatientAllergy(**data)
    db.add(allergy)
    db.commit()
    db.refresh(allergy)
    return allergy


def get_patient_allergy(db: Session, allergy_id: int) -> PatientAllergy:
    allergy = db.get(PatientAllergy, allergy_id)
    if allergy is None:
        raise PatientAllergyNotFoundError("Alergia/intolerância não encontrada.")
    return allergy


def search_patient_allergies(db: Session, search: PatientAllergySearch) -> tuple[list[PatientAllergy], int]:
    statement = select(PatientAllergy)

    if search.patient_id is not None:
        statement = statement.where(PatientAllergy.patient_id == search.patient_id)
    if search.professional_id is not None:
        statement = statement.where(PatientAllergy.professional_id == search.professional_id)
    if search.medical_record_id is not None:
        statement = statement.where(PatientAllergy.medical_record_id == search.medical_record_id)
    if search.tipo is not None:
        statement = statement.where(PatientAllergy.tipo == search.tipo)
    if search.categoria is not None:
        statement = statement.where(PatientAllergy.categoria == search.categoria)
    if search.gravidade is not None:
        statement = statement.where(PatientAllergy.gravidade == search.gravidade)
    if search.status is not None:
        statement = statement.where(PatientAllergy.status == search.status)
    if search.substancia:
        statement = statement.where(func.lower(PatientAllergy.substancia).like(f"%{search.substancia.lower()}%"))

    count_statement = select(func.count()).select_from(statement.subquery())
    total = int(db.scalar(count_statement) or 0)

    offset = (search.page - 1) * search.page_size
    rows = db.scalars(
        statement.order_by(PatientAllergy.created_at.desc(), PatientAllergy.id.desc())
        .offset(offset)
        .limit(search.page_size)
    ).all()
    return list(rows), total


def update_patient_allergy(db: Session, allergy_id: int, payload: PatientAllergyUpdate) -> PatientAllergy:
    allergy = get_patient_allergy(db, allergy_id)
    data = payload.model_dump(exclude_unset=True)

    patient_id = data.get("patient_id", allergy.patient_id)
    professional_id = data.get("professional_id", allergy.professional_id)
    medical_record_id = data.get("medical_record_id", allergy.medical_record_id)
    _validate_links(
        db,
        patient_id=patient_id,
        professional_id=professional_id,
        medical_record_id=medical_record_id,
    )

    for field, value in data.items():
        setattr(allergy, field, value)

    db.commit()
    db.refresh(allergy)
    return allergy
