from datetime import date, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PatientAllergyType(str, Enum):
    ALLERGY = "allergy"
    INTOLERANCE = "intolerance"
    ADVERSE_REACTION = "adverse_reaction"
    UNKNOWN = "unknown"


class PatientAllergyCategory(str, Enum):
    MEDICATION = "medication"
    FOOD = "food"
    ENVIRONMENT = "environment"
    LATEX = "latex"
    OTHER = "other"
    UNKNOWN = "unknown"


class PatientAllergySeverity(str, Enum):
    MILD = "mild"
    MODERATE = "moderate"
    SEVERE = "severe"
    LIFE_THREATENING = "life_threatening"
    UNKNOWN = "unknown"


class PatientAllergyStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    ENTERED_IN_ERROR = "entered_in_error"


def _blank_to_none(value: Any) -> Any:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return value


def _normalize_required_text(value: str, *, min_length: int = 1) -> str:
    normalized = " ".join(value.strip().split())
    if len(normalized) < min_length:
        raise ValueError("Campo obrigatório não pode ficar vazio.")
    return normalized


class PatientAllergyBase(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    patient_id: int = Field(..., ge=1, examples=[1])
    professional_id: int = Field(..., ge=1, examples=[1])
    medical_record_id: int | None = Field(None, ge=1, examples=[1])
    tipo: PatientAllergyType = Field(PatientAllergyType.ALLERGY, examples=[PatientAllergyType.ALLERGY])
    categoria: PatientAllergyCategory = Field(
        PatientAllergyCategory.UNKNOWN,
        examples=[PatientAllergyCategory.MEDICATION],
    )
    substancia: str = Field(..., min_length=2, max_length=255, examples=["Dipirona"])
    reacao: str | None = Field(None, max_length=255, examples=["Urticária"])
    gravidade: PatientAllergySeverity = Field(
        PatientAllergySeverity.UNKNOWN,
        examples=[PatientAllergySeverity.MODERATE],
    )
    observado_em: date | None = Field(None, examples=["2026-08-14"])
    observacoes: str | None = Field(None, examples=["Alergia referida pelo paciente."])

    @field_validator("substancia")
    @classmethod
    def validate_substancia(cls, value: str) -> str:
        return _normalize_required_text(value, min_length=2)

    _normalize_reacao = field_validator("reacao", mode="before")(_blank_to_none)
    _normalize_observacoes = field_validator("observacoes", mode="before")(_blank_to_none)


class PatientAllergyCreate(PatientAllergyBase):
    pass


class PatientAllergyUpdate(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    patient_id: int | None = Field(None, ge=1)
    professional_id: int | None = Field(None, ge=1)
    medical_record_id: int | None = Field(None, ge=1)
    tipo: PatientAllergyType | None = None
    categoria: PatientAllergyCategory | None = None
    substancia: str | None = Field(None, min_length=2, max_length=255)
    reacao: str | None = Field(None, max_length=255)
    gravidade: PatientAllergySeverity | None = None
    status: PatientAllergyStatus | None = None
    observado_em: date | None = None
    observacoes: str | None = None

    @field_validator("substancia")
    @classmethod
    def validate_substancia(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return _normalize_required_text(value, min_length=2)

    _normalize_reacao = field_validator("reacao", mode="before")(_blank_to_none)
    _normalize_observacoes = field_validator("observacoes", mode="before")(_blank_to_none)


class PatientAllergyRead(PatientAllergyBase):
    model_config = ConfigDict(from_attributes=True, use_enum_values=True)

    id: int
    status: PatientAllergyStatus
    created_at: datetime
    updated_at: datetime


class PatientAllergyList(BaseModel):
    items: list[PatientAllergyRead]
    total: int
    page: int
    page_size: int


class PatientAllergySearch(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    patient_id: int | None = Field(None, ge=1)
    professional_id: int | None = Field(None, ge=1)
    medical_record_id: int | None = Field(None, ge=1)
    tipo: PatientAllergyType | None = None
    categoria: PatientAllergyCategory | None = None
    gravidade: PatientAllergySeverity | None = None
    status: PatientAllergyStatus | None = None
    substancia: str | None = Field(None, min_length=1, max_length=255)
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)

    _normalize_substancia = field_validator("substancia", mode="before")(_blank_to_none)
