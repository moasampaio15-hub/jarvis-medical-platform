from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.appointment import Appointment
from app.models.exam_order import ExamOrder, ExamOrderItem
from app.models.health_professional import HealthProfessional
from app.models.medical_record import MedicalRecord
from app.models.patient import Patient
from app.schemas.appointment import AppointmentStatus
from app.schemas.exam_order import (
    ExamOrderCreate,
    ExamOrderPriority,
    ExamOrderSearch,
    ExamOrderStatus,
    ExamOrderUpdate,
)


class ExamOrderNotFoundError(ValueError):
    pass


class ExamOrderPatientNotFoundError(ValueError):
    pass


class ExamOrderProfessionalNotFoundError(ValueError):
    pass


class ExamOrderAppointmentNotFoundError(ValueError):
    pass


class ExamOrderAppointmentMismatchError(ValueError):
    pass


class ExamOrderMedicalRecordNotFoundError(ValueError):
    pass


class ExamOrderMedicalRecordMismatchError(ValueError):
    pass


class ExamOrderMedicalRecordAppointmentMismatchError(ValueError):
    pass


def _status_value(status: ExamOrderStatus | str) -> str:
    return status.value if isinstance(status, ExamOrderStatus) else status


def _priority_value(priority: ExamOrderPriority | str) -> str:
    return priority.value if isinstance(priority, ExamOrderPriority) else priority


def _assert_patient_exists(db: Session, patient_id: int) -> None:
    patient = db.get(Patient, patient_id)
    if patient is None or not patient.ativo:
        raise ExamOrderPatientNotFoundError("Paciente não encontrado ou inativo.")


def _assert_professional_exists(db: Session, professional_id: int) -> None:
    professional = db.get(HealthProfessional, professional_id)
    if professional is None or not professional.ativo:
        raise ExamOrderProfessionalNotFoundError("Profissional de saúde não encontrado ou inativo.")


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
        raise ExamOrderAppointmentNotFoundError("Consulta não encontrada ou cancelada.")
    if appointment.patient_id != patient_id or appointment.professional_id != professional_id:
        raise ExamOrderAppointmentMismatchError(
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
        raise ExamOrderMedicalRecordNotFoundError("Prontuário médico não encontrado.")
    if medical_record.patient_id != patient_id or medical_record.professional_id != professional_id:
        raise ExamOrderMedicalRecordMismatchError(
            "Prontuário não pertence ao paciente e profissional informados."
        )
    if (
        appointment_id is not None
        and medical_record.appointment_id is not None
        and medical_record.appointment_id != appointment_id
    ):
        raise ExamOrderMedicalRecordAppointmentMismatchError(
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


def _build_items(items: list[dict]) -> list[ExamOrderItem]:
    return [ExamOrderItem(**item) for item in items]


def create_exam_order(db: Session, payload: ExamOrderCreate) -> ExamOrder:
    data = payload.model_dump()
    items_data = data.pop("items")
    if "prioridade" in data and data["prioridade"] is not None:
        data["prioridade"] = _priority_value(data["prioridade"])
    _validate_links(
        db,
        patient_id=data["patient_id"],
        professional_id=data["professional_id"],
        appointment_id=data.get("appointment_id"),
        medical_record_id=data.get("medical_record_id"),
    )

    exam_order = ExamOrder(**data, status=ExamOrderStatus.DRAFT.value)
    exam_order.items = _build_items(items_data)
    db.add(exam_order)
    db.commit()
    db.refresh(exam_order)
    return exam_order


def get_exam_order(db: Session, exam_order_id: int) -> ExamOrder:
    statement = (
        select(ExamOrder)
        .options(selectinload(ExamOrder.items))
        .where(ExamOrder.id == exam_order_id)
    )
    exam_order = db.scalar(statement)
    if exam_order is None:
        raise ExamOrderNotFoundError("Solicitação de exame não encontrada.")
    return exam_order


def search_exam_orders(db: Session, search: ExamOrderSearch) -> tuple[list[ExamOrder], int]:
    statement = select(ExamOrder)

    if search.patient_id is not None:
        statement = statement.where(ExamOrder.patient_id == search.patient_id)
    if search.professional_id is not None:
        statement = statement.where(ExamOrder.professional_id == search.professional_id)
    if search.appointment_id is not None:
        statement = statement.where(ExamOrder.appointment_id == search.appointment_id)
    if search.medical_record_id is not None:
        statement = statement.where(ExamOrder.medical_record_id == search.medical_record_id)
    if search.status is not None:
        statement = statement.where(ExamOrder.status == _status_value(search.status))
    if search.prioridade is not None:
        statement = statement.where(ExamOrder.prioridade == _priority_value(search.prioridade))

    count_statement = select(func.count()).select_from(statement.subquery())
    total = int(db.scalar(count_statement) or 0)

    offset = (search.page - 1) * search.page_size
    rows = db.scalars(
        statement.options(selectinload(ExamOrder.items))
        .order_by(ExamOrder.created_at.desc(), ExamOrder.id.desc())
        .offset(offset)
        .limit(search.page_size)
    ).all()
    return list(rows), total


def update_exam_order(db: Session, exam_order_id: int, payload: ExamOrderUpdate) -> ExamOrder:
    exam_order = get_exam_order(db, exam_order_id)
    data = payload.model_dump(exclude_unset=True)
    items_data = data.pop("items", None)

    patient_id = data.get("patient_id", exam_order.patient_id)
    professional_id = data.get("professional_id", exam_order.professional_id)
    appointment_id = data.get("appointment_id", exam_order.appointment_id)
    medical_record_id = data.get("medical_record_id", exam_order.medical_record_id)

    _validate_links(
        db,
        patient_id=patient_id,
        professional_id=professional_id,
        appointment_id=appointment_id,
        medical_record_id=medical_record_id,
    )

    if "status" in data and data["status"] is not None:
        data["status"] = _status_value(data["status"])
    if "prioridade" in data and data["prioridade"] is not None:
        data["prioridade"] = _priority_value(data["prioridade"])

    for field, value in data.items():
        setattr(exam_order, field, value)

    if items_data is not None:
        exam_order.items = _build_items(items_data)

    db.commit()
    db.refresh(exam_order)
    return exam_order
