from datetime import date, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ClinicalDiagnosisType(str, Enum):
    HIPOTESE = "hipotese"
    CONFIRMADO = "confirmado"
    PROBLEMA = "problema"


class ClinicalDiagnosisStatus(str, Enum):
    ATIVO = "ativo"
    RESOLVIDO = "resolvido"


def _blank_to_none(value: Any) -> Any:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return value


def _normalize_required_text(value: str, *, min_length: int = 2) -> str:
    normalized = " ".join(value.strip().split())
    if len(normalized) < min_length:
        raise ValueError("Campo obrigatório não pode ficar vazio.")
    return normalized


class ClinicalDiagnosisBase(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    patient_id: int = Field(..., ge=1, examples=[1])
    professional_id: int = Field(..., ge=1, examples=[1])
    appointment_id: int | None = Field(None, ge=1, examples=[1])
    medical_record_id: int | None = Field(None, ge=1, examples=[1])
    cid10_codigo: str | None = Field(None, max_length=16, examples=["I10"])
    descricao: str = Field(..., min_length=2, max_length=255, examples=["Hipertensão arterial sistêmica"])
    tipo: ClinicalDiagnosisType = Field(ClinicalDiagnosisType.HIPOTESE, examples=[ClinicalDiagnosisType.HIPOTESE])
    status: ClinicalDiagnosisStatus = Field(ClinicalDiagnosisStatus.ATIVO, examples=[ClinicalDiagnosisStatus.ATIVO])
    data_inicio: date | None = Field(None, examples=["2026-08-14"])
    data_resolucao: date | None = Field(None, examples=["2026-08-20"])
    observacoes: str | None = Field(None, examples=["Problema clínico registrado durante consulta."])

    @field_validator("descricao")
    @classmethod
    def validate_descricao(cls, value: str) -> str:
        return _normalize_required_text(value)

    @field_validator("cid10_codigo", mode="before")
    @classmethod
    def normalize_cid10(cls, value: Any) -> Any:
        value = _blank_to_none(value)
        if isinstance(value, str):
            return value.upper()
        return value

    _normalize_observacoes = field_validator("observacoes", mode="before")(_blank_to_none)

    @model_validator(mode="after")
    def validate_date_range(self):
        if self.data_inicio and self.data_resolucao and self.data_resolucao < self.data_inicio:
            raise ValueError("Data de resolução não pode ser anterior à data de início.")
        return self


class ClinicalDiagnosisCreate(ClinicalDiagnosisBase):
    pass


class ClinicalDiagnosisUpdate(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    patient_id: int | None = Field(None, ge=1)
    professional_id: int | None = Field(None, ge=1)
    appointment_id: int | None = Field(None, ge=1)
    medical_record_id: int | None = Field(None, ge=1)
    cid10_codigo: str | None = Field(None, max_length=16)
    descricao: str | None = Field(None, min_length=2, max_length=255)
    tipo: ClinicalDiagnosisType | None = None
    status: ClinicalDiagnosisStatus | None = None
    data_inicio: date | None = None
    data_resolucao: date | None = None
    observacoes: str | None = None

    @field_validator("descricao")
    @classmethod
    def validate_descricao(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return _normalize_required_text(value)

    @field_validator("cid10_codigo", mode="before")
    @classmethod
    def normalize_cid10(cls, value: Any) -> Any:
        value = _blank_to_none(value)
        if isinstance(value, str):
            return value.upper()
        return value

    _normalize_observacoes = field_validator("observacoes", mode="before")(_blank_to_none)


class ClinicalDiagnosisRead(ClinicalDiagnosisBase):
    model_config = ConfigDict(from_attributes=True, use_enum_values=True)

    id: int
    created_at: datetime
    updated_at: datetime


class ClinicalDiagnosisList(BaseModel):
    items: list[ClinicalDiagnosisRead]
    total: int
    page: int
    page_size: int


class ClinicalDiagnosisSearch(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    patient_id: int | None = Field(None, ge=1)
    professional_id: int | None = Field(None, ge=1)
    appointment_id: int | None = Field(None, ge=1)
    medical_record_id: int | None = Field(None, ge=1)
    cid10_codigo: str | None = Field(None, max_length=16)
    tipo: ClinicalDiagnosisType | None = None
    status: ClinicalDiagnosisStatus | None = None
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)

    @field_validator("cid10_codigo", mode="before")
    @classmethod
    def normalize_search_cid10(cls, value: Any) -> Any:
        value = _blank_to_none(value)
        if isinstance(value, str):
            return value.upper()
        return value
