from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ClinicalNoteType(str, Enum):
    EVOLUCAO = "evolucao"
    ATENDIMENTO = "atendimento"
    RETORNO = "retorno"
    INTERCORRENCIA = "intercorrencia"
    ORIENTACAO = "orientacao"


NOTE_CONTENT_FIELDS = (
    "queixa_motivo",
    "historia_clinica",
    "exame_achados",
    "avaliacao",
    "plano_conduta",
    "observacoes",
)


def _blank_to_none(value: Any) -> Any:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return value


class ClinicalNoteBase(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    patient_id: int = Field(..., ge=1, examples=[1])
    professional_id: int = Field(..., ge=1, examples=[1])
    appointment_id: int | None = Field(None, ge=1, examples=[1])
    medical_record_id: int | None = Field(None, ge=1, examples=[1])
    recorded_at: datetime | None = Field(None, examples=["2026-08-14T10:30:00"])
    tipo: ClinicalNoteType = Field(ClinicalNoteType.EVOLUCAO, examples=[ClinicalNoteType.EVOLUCAO])
    queixa_motivo: str | None = Field(None, max_length=255, examples=["Dor torácica em melhora"])
    historia_clinica: str | None = Field(None, examples=["Paciente relata melhora após repouso."])
    exame_achados: str | None = Field(None, examples=["Bom estado geral, ausculta sem alterações."])
    avaliacao: str | None = Field(None, examples=["Quadro compatível com dor musculoesquelética."])
    plano_conduta: str | None = Field(None, examples=["Manter analgesia e retorno se piora."])
    observacoes: str | None = Field(None, examples=["Nota clínica fictícia para testes."])

    _normalize_text = field_validator(*NOTE_CONTENT_FIELDS, mode="before")(_blank_to_none)

    @model_validator(mode="after")
    def validate_has_content(self):
        if not any(getattr(self, field) for field in NOTE_CONTENT_FIELDS):
            raise ValueError("Informe ao menos um campo clínico da nota.")
        return self


class ClinicalNoteCreate(ClinicalNoteBase):
    pass


class ClinicalNoteUpdate(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    patient_id: int | None = Field(None, ge=1)
    professional_id: int | None = Field(None, ge=1)
    appointment_id: int | None = Field(None, ge=1)
    medical_record_id: int | None = Field(None, ge=1)
    recorded_at: datetime | None = None
    tipo: ClinicalNoteType | None = None
    queixa_motivo: str | None = Field(None, max_length=255)
    historia_clinica: str | None = None
    exame_achados: str | None = None
    avaliacao: str | None = None
    plano_conduta: str | None = None
    observacoes: str | None = None

    _normalize_text = field_validator(*NOTE_CONTENT_FIELDS, mode="before")(_blank_to_none)


class ClinicalNoteRead(ClinicalNoteBase):
    model_config = ConfigDict(from_attributes=True, use_enum_values=True)

    id: int
    recorded_at: datetime
    created_at: datetime
    updated_at: datetime


class ClinicalNoteList(BaseModel):
    items: list[ClinicalNoteRead]
    total: int
    page: int
    page_size: int


class ClinicalNoteSearch(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    patient_id: int | None = Field(None, ge=1)
    professional_id: int | None = Field(None, ge=1)
    appointment_id: int | None = Field(None, ge=1)
    medical_record_id: int | None = Field(None, ge=1)
    tipo: ClinicalNoteType | None = None
    recorded_from: datetime | None = None
    recorded_to: datetime | None = None
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)
