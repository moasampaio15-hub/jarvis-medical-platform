from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ExamOrderStatus(str, Enum):
    DRAFT = "draft"
    REQUESTED = "requested"
    COMPLETED = "completed"
    CANCELED = "canceled"


class ExamOrderPriority(str, Enum):
    ROTINA = "rotina"
    URGENTE = "urgente"


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


class ExamOrderItemBase(BaseModel):
    nome_exame: str = Field(..., min_length=2, max_length=255, examples=["Hemograma completo"])
    codigo: str | None = Field(None, max_length=64, examples=["HEM001"])
    material: str | None = Field(None, max_length=120, examples=["Sangue total"])
    orientacoes: str | None = Field(None, examples=["Jejum de 8 horas, se aplicável."])

    @field_validator("nome_exame")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        return _normalize_required_text(value)

    _normalize_optional_text = field_validator(
        "codigo",
        "material",
        "orientacoes",
        mode="before",
    )(_blank_to_none)


class ExamOrderItemCreate(ExamOrderItemBase):
    pass


class ExamOrderItemRead(ExamOrderItemBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime


class ExamOrderBase(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    patient_id: int = Field(..., ge=1, examples=[1])
    professional_id: int = Field(..., ge=1, examples=[1])
    appointment_id: int | None = Field(None, ge=1, examples=[1])
    medical_record_id: int | None = Field(None, ge=1, examples=[1])
    prioridade: ExamOrderPriority = Field(ExamOrderPriority.ROTINA, examples=[ExamOrderPriority.ROTINA])
    justificativa: str | None = Field(None, examples=["Investigação de anemia."])
    observacoes: str | None = Field(None, examples=["Solicitação fictícia para testes."])
    items: list[ExamOrderItemCreate] = Field(..., min_length=1)

    _normalize_optional_text = field_validator(
        "justificativa",
        "observacoes",
        mode="before",
    )(_blank_to_none)


class ExamOrderCreate(ExamOrderBase):
    pass


class ExamOrderUpdate(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    patient_id: int | None = Field(None, ge=1)
    professional_id: int | None = Field(None, ge=1)
    appointment_id: int | None = Field(None, ge=1)
    medical_record_id: int | None = Field(None, ge=1)
    status: ExamOrderStatus | None = None
    prioridade: ExamOrderPriority | None = None
    justificativa: str | None = None
    observacoes: str | None = None
    items: list[ExamOrderItemCreate] | None = Field(None, min_length=1)

    _normalize_optional_text = field_validator(
        "justificativa",
        "observacoes",
        mode="before",
    )(_blank_to_none)


class ExamOrderRead(ExamOrderBase):
    model_config = ConfigDict(from_attributes=True, use_enum_values=True)

    id: int
    status: ExamOrderStatus
    prioridade: ExamOrderPriority
    items: list[ExamOrderItemRead]
    created_at: datetime
    updated_at: datetime


class ExamOrderList(BaseModel):
    items: list[ExamOrderRead]
    total: int
    page: int
    page_size: int


class ExamOrderSearch(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    patient_id: int | None = Field(None, ge=1)
    professional_id: int | None = Field(None, ge=1)
    appointment_id: int | None = Field(None, ge=1)
    medical_record_id: int | None = Field(None, ge=1)
    status: ExamOrderStatus | None = None
    prioridade: ExamOrderPriority | None = None
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)
