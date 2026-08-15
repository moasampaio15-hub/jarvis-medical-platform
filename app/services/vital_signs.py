from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.appointment import Appointment
from app.models.health_professional import HealthProfessional
from app.models.medical_record import MedicalRecord
from app.models.patient import Patient
from app.models.vital_sign import VitalSign
from app.schemas.appointment import AppointmentStatus
from app.schemas.vital_sign import VitalSignCreate, VitalSignSearch, VitalSignUpdate


class VitalSignNotFoundError(ValueError):
    pass


class VitalSignPatientNotFoundError(ValueError):
    pass


class VitalSignProfessionalNotFoundError(ValueError):
    pass


class VitalSignAppointmentNotFoundError(ValueError):
    pass


class VitalSignAppointmentMismatchError(ValueError):
    pass


class VitalSignMedicalRecordNotFoundError(ValueError):
    pass


class VitalSignMedicalRecordMismatchError(ValueError):
    pass


def _assert_patient_exists(db: Session, patient_id: int) -> None:
    patient = db.get(Patient, patient_id)
    if patient is None or not patient.ativo:
        raise VitalSignPatientNotFoundError("Paciente não encontrado ou inativo.")


def _assert_professional_exists(db: Session, professional_id: int) -> None:
    professional = db.get(HealthProfessional, professional_id)
    if professional is None or not professional.ativo:
        raise VitalSignProfessionalNotFoundError("Profissional de saúde não encontrado ou inativo.")


def _assert_appointment_matches(db: Session, appointment_id: int | None, *, patient_id: int, professional_id: int) -> None:
    if appointment_id is None:
        return

    appointment = db.get(Appointment, appointment_id)
    if appointment is None or appointment.status == AppointmentStatus.CANCELED.value:
        raise VitalSignAppointmentNotFoundError("Consulta não encontrada ou cancelada.")
    if appointment.patient_id != patient_id or appointment.professional_id != professional_id:
        raise VitalSignAppointmentMismatchError("Consulta não pertence ao paciente e profissional informados.")


def _assert_medical_record_matches(db: Session, medical_record_id: int | None, *, patient_id: int) -> None:
    if medical_record_id is None:
        return

    medical_record = db.get(MedicalRecord, medical_record_id)
    if medical_record is None:
        raise VitalSignMedicalRecordNotFoundError("Prontuário médico não encontrado.")
    if medical_record.patient_id != patient_id:
        raise VitalSignMedicalRecordMismatchError("Prontuário não pertence ao paciente informado.")


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


def _decimal_or_none(value: float | int | Decimal | None) -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(value))


def _calculate_imc(peso_kg: float | int | Decimal | None, altura_cm: float | int | Decimal | None) -> Decimal | None:
    peso = _decimal_or_none(peso_kg)
    altura = _decimal_or_none(altura_cm)
    if peso is None or altura is None or altura == 0:
        return None
    altura_m = altura / Decimal("100")
    return (peso / (altura_m * altura_m)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _prepare_measurements(data: dict) -> dict:
    for field in ("temperatura_c", "peso_kg", "altura_cm"):
        if field in data:
            data[field] = _decimal_or_none(data[field])
    return data


def create_vital_sign(db: Session, payload: VitalSignCreate) -> VitalSign:
    data = _prepare_measurements(payload.model_dump())
    if data.get("recorded_at") is None:
        data.pop("recorded_at", None)
    _validate_links(
        db,
        patient_id=data["patient_id"],
        professional_id=data["professional_id"],
        appointment_id=data.get("appointment_id"),
        medical_record_id=data.get("medical_record_id"),
    )
    data["imc"] = _calculate_imc(data.get("peso_kg"), data.get("altura_cm"))

    vital_sign = VitalSign(**data)
    db.add(vital_sign)
    db.commit()
    db.refresh(vital_sign)
    return vital_sign


def get_vital_sign(db: Session, vital_sign_id: int) -> VitalSign:
    vital_sign = db.get(VitalSign, vital_sign_id)
    if vital_sign is None:
        raise VitalSignNotFoundError("Registro de sinais vitais não encontrado.")
    return vital_sign


def search_vital_signs(db: Session, search: VitalSignSearch) -> tuple[list[VitalSign], int]:
    statement = select(VitalSign)

    if search.patient_id is not None:
        statement = statement.where(VitalSign.patient_id == search.patient_id)
    if search.professional_id is not None:
        statement = statement.where(VitalSign.professional_id == search.professional_id)
    if search.appointment_id is not None:
        statement = statement.where(VitalSign.appointment_id == search.appointment_id)
    if search.medical_record_id is not None:
        statement = statement.where(VitalSign.medical_record_id == search.medical_record_id)
    if search.recorded_from is not None:
        statement = statement.where(VitalSign.recorded_at >= search.recorded_from)
    if search.recorded_to is not None:
        statement = statement.where(VitalSign.recorded_at <= search.recorded_to)

    count_statement = select(func.count()).select_from(statement.subquery())
    total = int(db.scalar(count_statement) or 0)

    offset = (search.page - 1) * search.page_size
    rows = db.scalars(
        statement.order_by(VitalSign.recorded_at.desc(), VitalSign.id.desc())
        .offset(offset)
        .limit(search.page_size)
    ).all()
    return list(rows), total


def update_vital_sign(db: Session, vital_sign_id: int, payload: VitalSignUpdate) -> VitalSign:
    vital_sign = get_vital_sign(db, vital_sign_id)
    data = _prepare_measurements(payload.model_dump(exclude_unset=True))
    if data.get("recorded_at") is None:
        data.pop("recorded_at", None)

    patient_id = data.get("patient_id", vital_sign.patient_id)
    professional_id = data.get("professional_id", vital_sign.professional_id)
    appointment_id = data.get("appointment_id", vital_sign.appointment_id)
    medical_record_id = data.get("medical_record_id", vital_sign.medical_record_id)
    _validate_links(
        db,
        patient_id=patient_id,
        professional_id=professional_id,
        appointment_id=appointment_id,
        medical_record_id=medical_record_id,
    )

    for field, value in data.items():
        setattr(vital_sign, field, value)
    vital_sign.imc = _calculate_imc(vital_sign.peso_kg, vital_sign.altura_cm)

    db.commit()
    db.refresh(vital_sign)
    return vital_sign
