from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class AppointmentStatus(str, Enum):
    SCHEDULED = "scheduled"
    CONFIRMED = "confirmed"
    CANCELED = "canceled"
    COMPLETED = "completed"
    NO_SHOW = "no_show"


def _blank_to_none(value: Any) -> Any:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return value


class AppointmentBase(BaseModel):
    patient_id: int = Field(..., ge=1, examples=[1])
    professional_id: int = Field(..., ge=1, examples=[1])
    start_at: datetime = Field(..., examples=["2026-09-01T09:00:00"])
    end_at: datetime = Field(..., examples=["2026-09-01T09:30:00"])
    motivo: str | None = Field(None, max_length=255, examples=["Consulta de rotina"])
    observacoes: str | None = Field(None, examples=["Paciente fictício sem observações clínicas."])

    _normalize_motivo = field_validator("motivo", mode="before")(_blank_to_none)
    _normalize_observacoes = field_validator("observacoes", mode="before")(_blank_to_none)

    @model_validator(mode="after")
    def validate_time_range(self) -> "AppointmentBase":
        if self.end_at <= self.start_at:
            raise ValueError("O horário final da consulta deve ser posterior ao horário inicial.")
        return self


class AppointmentCreate(AppointmentBase):
    pass


class AppointmentStatusUpdate(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    status: AppointmentStatus = Field(..., examples=["confirmed"])


class AppointmentCancel(BaseModel):
    cancel_reason: str | None = Field(None, max_length=255, examples=["Solicitação do paciente"])

    _normalize_reason = field_validator("cancel_reason", mode="before")(_blank_to_none)


class AppointmentRead(AppointmentBase):
    model_config = ConfigDict(from_attributes=True, use_enum_values=True)

    id: int
    status: AppointmentStatus
    cancel_reason: str | None
    canceled_at: datetime | None
    created_at: datetime
    updated_at: datetime


class AppointmentList(BaseModel):
    items: list[AppointmentRead]
    total: int
    page: int
    page_size: int


class AppointmentSearch(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    start_at: datetime | None = Field(None, examples=["2026-09-01T00:00:00"])
    end_at: datetime | None = Field(None, examples=["2026-09-30T23:59:59"])
    patient_id: int | None = Field(None, ge=1)
    professional_id: int | None = Field(None, ge=1)
    status: AppointmentStatus | None = None
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)

    @model_validator(mode="after")
    def validate_period(self) -> "AppointmentSearch":
        if self.start_at is not None and self.end_at is not None and self.end_at <= self.start_at:
            raise ValueError("O fim do período deve ser posterior ao início do período.")
        return self
