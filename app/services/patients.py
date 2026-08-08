from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.patient import Patient
from app.schemas.patient import PatientCreate, PatientSearch, PatientUpdate


class PatientNotFoundError(ValueError):
    pass


class PatientDuplicateError(ValueError):
    def __init__(self, field: str) -> None:
        self.field = field
        super().__init__(f"Paciente com {field} já cadastrado.")


def _patient_exists_with_field(
    db: Session,
    field_name: str,
    value: str | None,
    *,
    exclude_patient_id: int | None = None,
) -> bool:
    if value is None:
        return False

    column = getattr(Patient, field_name)
    statement = select(Patient.id).where(column == value)
    if exclude_patient_id is not None:
        statement = statement.where(Patient.id != exclude_patient_id)
    return db.scalar(statement) is not None


def _assert_unique_identifiers(
    db: Session,
    *,
    cpf: str | None,
    cns: str | None,
    exclude_patient_id: int | None = None,
) -> None:
    if _patient_exists_with_field(db, "cpf", cpf, exclude_patient_id=exclude_patient_id):
        raise PatientDuplicateError("cpf")
    if _patient_exists_with_field(db, "cns", cns, exclude_patient_id=exclude_patient_id):
        raise PatientDuplicateError("cns")


def create_patient(db: Session, payload: PatientCreate) -> Patient:
    data = payload.model_dump()
    _assert_unique_identifiers(db, cpf=data.get("cpf"), cns=data.get("cns"))

    patient = Patient(**data)
    db.add(patient)
    db.commit()
    db.refresh(patient)
    return patient


def get_patient(db: Session, patient_id: int) -> Patient:
    patient = db.get(Patient, patient_id)
    if patient is None:
        raise PatientNotFoundError("Paciente não encontrado.")
    return patient


def update_patient(db: Session, patient_id: int, payload: PatientUpdate) -> Patient:
    patient = get_patient(db, patient_id)
    data = payload.model_dump(exclude_unset=True)

    cpf = data.get("cpf", patient.cpf)
    cns = data.get("cns", patient.cns)
    _assert_unique_identifiers(db, cpf=cpf, cns=cns, exclude_patient_id=patient.id)

    for field, value in data.items():
        setattr(patient, field, value)

    db.commit()
    db.refresh(patient)
    return patient


def deactivate_patient(db: Session, patient_id: int) -> Patient:
    patient = get_patient(db, patient_id)
    patient.ativo = False
    db.commit()
    db.refresh(patient)
    return patient


def search_patients(db: Session, search: PatientSearch) -> tuple[list[Patient], int]:
    statement = select(Patient)

    if search.nome:
        nome = f"%{search.nome.strip().lower()}%"
        statement = statement.where(func.lower(Patient.nome_completo).like(nome))
    if search.cpf:
        statement = statement.where(Patient.cpf == search.cpf)
    if search.cns:
        statement = statement.where(Patient.cns == search.cns)

    count_statement = select(func.count()).select_from(statement.subquery())
    total = int(db.scalar(count_statement) or 0)

    offset = (search.page - 1) * search.page_size
    rows = db.scalars(
        statement.order_by(Patient.nome_completo.asc(), Patient.id.asc())
        .offset(offset)
        .limit(search.page_size)
    ).all()
    return list(rows), total
