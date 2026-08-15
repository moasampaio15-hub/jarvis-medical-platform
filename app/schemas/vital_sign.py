from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _blank_to_none(value: Any) -> Any:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return value


class VitalSignBase(BaseModel):
    patient_id: int = Field(..., ge=1, examples=[1])
    professional_id: int = Field(..., ge=1, examples=[1])
    appointment_id: int | None = Field(None, ge=1, examples=[1])
    medical_record_id: int | None = Field(None, ge=1, examples=[1])
    recorded_at: datetime | None = Field(None, examples=["2026-08-14T09:30:00"])
    pressao_sistolica: int | None = Field(None, ge=50, le=300, examples=[120])
    pressao_diastolica: int | None = Field(None, ge=30, le=200, examples=[80])
    frequencia_cardiaca: int | None = Field(None, ge=20, le=250, examples=[76])
    frequencia_respiratoria: int | None = Field(None, ge=5, le=80, examples=[18])
    temperatura_c: float | None = Field(None, ge=30, le=45, examples=[36.7])
    spo2: int | None = Field(None, ge=0, le=100, examples=[98])
    peso_kg: float | None = Field(None, ge=0.5, le=500, examples=[72.5])
    altura_cm: float | None = Field(None, ge=30, le=250, examples=[175])
    glicemia_capilar: int | None = Field(None, ge=20, le=1000, examples=[95])
    dor_escala: int | None = Field(None, ge=0, le=10, examples=[3])
    observacoes: str | None = Field(None, max_length=500, examples=["Triagem inicial sem queixas adicionais."])

    _normalize_observacoes = field_validator("observacoes", mode="before")(_blank_to_none)


class VitalSignCreate(VitalSignBase):
    pass


class VitalSignUpdate(BaseModel):
    patient_id: int | None = Field(None, ge=1)
    professional_id: int | None = Field(None, ge=1)
    appointment_id: int | None = Field(None, ge=1)
    medical_record_id: int | None = Field(None, ge=1)
    recorded_at: datetime | None = None
    pressao_sistolica: int | None = Field(None, ge=50, le=300)
    pressao_diastolica: int | None = Field(None, ge=30, le=200)
    frequencia_cardiaca: int | None = Field(None, ge=20, le=250)
    frequencia_respiratoria: int | None = Field(None, ge=5, le=80)
    temperatura_c: float | None = Field(None, ge=30, le=45)
    spo2: int | None = Field(None, ge=0, le=100)
    peso_kg: float | None = Field(None, ge=0.5, le=500)
    altura_cm: float | None = Field(None, ge=30, le=250)
    glicemia_capilar: int | None = Field(None, ge=20, le=1000)
    dor_escala: int | None = Field(None, ge=0, le=10)
    observacoes: str | None = Field(None, max_length=500)

    _normalize_observacoes = field_validator("observacoes", mode="before")(_blank_to_none)


class VitalSignRead(VitalSignBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    recorded_at: datetime
    imc: float | None
    created_at: datetime
    updated_at: datetime


class VitalSignList(BaseModel):
    items: list[VitalSignRead]
    total: int
    page: int
    page_size: int


class VitalSignSearch(BaseModel):
    patient_id: int | None = Field(None, ge=1)
    professional_id: int | None = Field(None, ge=1)
    appointment_id: int | None = Field(None, ge=1)
    medical_record_id: int | None = Field(None, ge=1)
    recorded_from: datetime | None = None
    recorded_to: datetime | None = None
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)
