from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ExamResultStatus(str, Enum):
    DRAFT = "draft"
    PRELIMINARY = "preliminary"
    FINAL = "final"
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


class ExamResultItemBase(BaseModel):
    exam_order_item_id: int = Field(..., ge=1, examples=[1])
    resultado: str = Field(..., min_length=1, examples=["Hemoglobina: 13,8 g/dL"])
    unidade: str | None = Field(None, max_length=64, examples=["g/dL"])
    valor_referencia: str | None = Field(None, max_length=255, examples=["12,0 a 16,0 g/dL"])
    interpretacao: str | None = Field(None, examples=["Resultado dentro da faixa de referência."])

    @field_validator("resultado")
    @classmethod
    def validate_resultado(cls, value: str) -> str:
        return _normalize_required_text(value)

    _normalize_unidade = field_validator("unidade", mode="before")(_blank_to_none)
    _normalize_valor_referencia = field_validator("valor_referencia", mode="before")(_blank_to_none)
    _normalize_interpretacao = field_validator("interpretacao", mode="before")(_blank_to_none)


class ExamResultItemCreate(ExamResultItemBase):
    pass


class ExamResultItemRead(ExamResultItemBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome_exame: str
    codigo: str | None
    created_at: datetime
    updated_at: datetime


class ExamResultBase(BaseModel):
    exam_order_id: int = Field(..., ge=1, examples=[1])
    professional_id: int = Field(..., ge=1, examples=[1])
    coletado_em: datetime | None = Field(None, examples=["2026-08-14T10:00:00"])
    liberado_em: datetime | None = Field(None, examples=["2026-08-14T15:00:00"])
    laudo: str | None = Field(None, examples=["Laudo laboratorial fictício para testes."])
    observacoes: str | None = Field(None, examples=["Resultado validado pela equipe técnica."])
    items: list[ExamResultItemCreate] = Field(..., min_length=1)

    _normalize_laudo = field_validator("laudo", mode="before")(_blank_to_none)
    _normalize_observacoes = field_validator("observacoes", mode="before")(_blank_to_none)


class ExamResultCreate(ExamResultBase):
    pass


class ExamResultUpdate(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    professional_id: int | None = Field(None, ge=1)
    status: ExamResultStatus | None = None
    coletado_em: datetime | None = None
    liberado_em: datetime | None = None
    laudo: str | None = None
    observacoes: str | None = None
    items: list[ExamResultItemCreate] | None = Field(None, min_length=1)

    _normalize_laudo = field_validator("laudo", mode="before")(_blank_to_none)
    _normalize_observacoes = field_validator("observacoes", mode="before")(_blank_to_none)


class ExamResultRead(ExamResultBase):
    model_config = ConfigDict(from_attributes=True, use_enum_values=True)

    id: int
    patient_id: int
    status: ExamResultStatus
    items: list[ExamResultItemRead]
    created_at: datetime
    updated_at: datetime


class ExamResultList(BaseModel):
    items: list[ExamResultRead]
    total: int
    page: int
    page_size: int


class ExamResultSearch(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    exam_order_id: int | None = Field(None, ge=1)
    patient_id: int | None = Field(None, ge=1)
    professional_id: int | None = Field(None, ge=1)
    status: ExamResultStatus | None = None
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)
