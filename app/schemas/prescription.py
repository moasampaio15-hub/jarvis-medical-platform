from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PrescriptionStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELED = "canceled"


def _blank_to_none(value: Any) -> Any:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return value


def _normalize_required_text(value: str) -> str:
    normalized = " ".join(value.strip().split())
    if not normalized:
        raise ValueError("Campo obrigatório não pode ficar vazio.")
    return normalized


class PrescriptionItemBase(BaseModel):
    medicamento: str = Field(..., min_length=2, max_length=255, examples=["Dipirona"])
    apresentacao: str = Field(..., min_length=2, max_length=255, examples=["Comprimido 500 mg"])
    dose: str = Field(..., min_length=1, max_length=120, examples=["1 comprimido"])
    via: str = Field(..., min_length=2, max_length=64, examples=["oral"])
    frequencia: str = Field(..., min_length=2, max_length=120, examples=["a cada 6 horas"])
    duracao: str = Field(..., min_length=2, max_length=120, examples=["5 dias"])
    orientacoes: str | None = Field(None, examples=["Tomar após alimentação."])

    @field_validator("medicamento", "apresentacao", "dose", "via", "frequencia", "duracao")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        return _normalize_required_text(value)

    _normalize_orientacoes = field_validator("orientacoes", mode="before")(_blank_to_none)


class PrescriptionItemCreate(PrescriptionItemBase):
    pass


class PrescriptionItemRead(PrescriptionItemBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime


class PrescriptionBase(BaseModel):
    patient_id: int = Field(..., ge=1, examples=[1])
    professional_id: int = Field(..., ge=1, examples=[1])
    appointment_id: int | None = Field(None, ge=1, examples=[1])
    medical_record_id: int | None = Field(None, ge=1, examples=[1])
    observacoes: str | None = Field(None, examples=["Prescrição fictícia para testes."])
    items: list[PrescriptionItemCreate] = Field(..., min_length=1)

    _normalize_observacoes = field_validator("observacoes", mode="before")(_blank_to_none)


class PrescriptionCreate(PrescriptionBase):
    pass


class PrescriptionUpdate(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    patient_id: int | None = Field(None, ge=1)
    professional_id: int | None = Field(None, ge=1)
    appointment_id: int | None = Field(None, ge=1)
    medical_record_id: int | None = Field(None, ge=1)
    status: PrescriptionStatus | None = None
    observacoes: str | None = None
    items: list[PrescriptionItemCreate] | None = Field(None, min_length=1)

    _normalize_observacoes = field_validator("observacoes", mode="before")(_blank_to_none)


class PrescriptionRead(PrescriptionBase):
    model_config = ConfigDict(from_attributes=True, use_enum_values=True)

    id: int
    status: PrescriptionStatus
    items: list[PrescriptionItemRead]
    created_at: datetime
    updated_at: datetime


class PrescriptionList(BaseModel):
    items: list[PrescriptionRead]
    total: int
    page: int
    page_size: int


class PrescriptionSearch(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    patient_id: int | None = Field(None, ge=1)
    professional_id: int | None = Field(None, ge=1)
    appointment_id: int | None = Field(None, ge=1)
    medical_record_id: int | None = Field(None, ge=1)
    status: PrescriptionStatus | None = None
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)
