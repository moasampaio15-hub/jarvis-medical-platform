from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class MedicalRecordStatus(str, Enum):
    DRAFT = "draft"
    FINALIZED = "finalized"
    AMENDED = "amended"


def _blank_to_none(value: Any) -> Any:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return value


def _normalize_text(value: str) -> str:
    normalized = " ".join(value.strip().split())
    if not normalized:
        raise ValueError("Campo obrigatório não pode ficar vazio.")
    return normalized


class MedicalRecordBase(BaseModel):
    patient_id: int = Field(..., ge=1, examples=[1])
    professional_id: int = Field(..., ge=1, examples=[1])
    appointment_id: int | None = Field(None, ge=1, examples=[1])
    queixa_principal: str = Field(..., min_length=2, max_length=255, examples=["Dor torácica há 2 dias"])
    historia_clinica: str | None = Field(None, examples=["Paciente relata melhora parcial com repouso."])
    exame_fisico: str | None = Field(None, examples=["Bom estado geral, afebril."])
    conduta: str = Field(..., min_length=2, examples=["Solicitado retorno e orientações gerais."])
    observacoes: str | None = Field(None, examples=["Registro fictício para testes."])

    @field_validator("queixa_principal", "conduta")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        return _normalize_text(value)

    _normalize_optional_text = field_validator(
        "historia_clinica",
        "exame_fisico",
        "observacoes",
        mode="before",
    )(_blank_to_none)


class MedicalRecordCreate(MedicalRecordBase):
    pass


class MedicalRecordUpdate(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    patient_id: int | None = Field(None, ge=1)
    professional_id: int | None = Field(None, ge=1)
    appointment_id: int | None = Field(None, ge=1)
    status: MedicalRecordStatus | None = None
    queixa_principal: str | None = Field(None, min_length=2, max_length=255)
    historia_clinica: str | None = None
    exame_fisico: str | None = None
    conduta: str | None = Field(None, min_length=2)
    observacoes: str | None = None

    _blank_required = field_validator("queixa_principal", "conduta", mode="before")(_blank_to_none)
    _normalize_optional_text = field_validator(
        "historia_clinica",
        "exame_fisico",
        "observacoes",
        mode="before",
    )(_blank_to_none)

    @field_validator("queixa_principal", "conduta")
    @classmethod
    def validate_required_text(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return _normalize_text(value)


class MedicalRecordRead(MedicalRecordBase):
    model_config = ConfigDict(from_attributes=True, use_enum_values=True)

    id: int
    status: MedicalRecordStatus
    created_at: datetime
    updated_at: datetime


class MedicalRecordList(BaseModel):
    items: list[MedicalRecordRead]
    total: int
    page: int
    page_size: int


class MedicalRecordSearch(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    patient_id: int | None = Field(None, ge=1)
    professional_id: int | None = Field(None, ge=1)
    appointment_id: int | None = Field(None, ge=1)
    status: MedicalRecordStatus | None = None
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)
