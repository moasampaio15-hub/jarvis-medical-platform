from datetime import date, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class ConselhoTipo(str, Enum):
    CRM = "CRM"
    COREN = "COREN"
    CRO = "CRO"
    CRF = "CRF"
    CREFITO = "CREFITO"
    CRP = "CRP"
    OUTRO = "outro"


def _blank_to_none(value: Any) -> Any:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return value


def _digits_or_none(value: Any) -> Any:
    value = _blank_to_none(value)
    if isinstance(value, str):
        digits = "".join(char for char in value if char.isdigit())
        return digits or None
    return value


def _normalize_conselho_tipo(value: Any) -> Any:
    value = _blank_to_none(value)
    if isinstance(value, str):
        normalized = value.strip()
        return "outro" if normalized.lower() == "outro" else normalized.upper()
    return value


def _normalize_optional_list(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, list):
        normalized = [" ".join(str(item).strip().split()) for item in value if str(item).strip()]
        return normalized or None
    return value


class HealthProfessionalBase(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    user_id: int | None = Field(None, examples=[1])
    nome_completo: str = Field(..., min_length=2, max_length=255, examples=["Dra. Marina Fictícia"])
    nome_social: str | None = Field(None, max_length=255, examples=["Marina"])
    cpf: str | None = Field(None, min_length=11, max_length=11, examples=["12345678901"])
    data_nascimento: date | None = Field(None, examples=["1985-06-20"])
    email: EmailStr | None = Field(None, examples=["marina.ficticia@example.com"])
    telefone: str | None = Field(None, max_length=32, examples=["11988887777"])
    conselho_tipo: ConselhoTipo = Field(..., examples=["CRM"])
    conselho_numero: str = Field(..., min_length=1, max_length=32, examples=["123456"])
    conselho_uf: str = Field(..., min_length=2, max_length=2, examples=["SP"])
    especialidade_principal: str | None = Field(None, max_length=120, examples=["Cardiologia"])
    outras_especialidades: list[str] | None = Field(None, examples=[["Clínica médica"]])
    rqe: str | None = Field(None, max_length=32, examples=["RQE12345"])

    @field_validator("nome_completo")
    @classmethod
    def validate_nome_completo(cls, value: str) -> str:
        nome = " ".join(value.strip().split())
        if len(nome) < 2:
            raise ValueError("O nome completo deve ter pelo menos 2 caracteres.")
        return nome

    @field_validator(
        "nome_social",
        "email",
        "telefone",
        "especialidade_principal",
        "rqe",
        mode="before",
    )
    @classmethod
    def normalize_optional_text(cls, value: Any) -> Any:
        return _blank_to_none(value)

    @field_validator("cpf", mode="before")
    @classmethod
    def normalize_cpf(cls, value: Any) -> Any:
        return _digits_or_none(value)

    @field_validator("conselho_tipo", mode="before")
    @classmethod
    def normalize_tipo(cls, value: Any) -> Any:
        return _normalize_conselho_tipo(value)

    @field_validator("conselho_numero", mode="before")
    @classmethod
    def normalize_conselho_numero(cls, value: Any) -> Any:
        return _blank_to_none(value)

    @field_validator("conselho_uf", mode="before")
    @classmethod
    def normalize_conselho_uf(cls, value: Any) -> Any:
        value = _blank_to_none(value)
        if isinstance(value, str):
            return value.upper()
        return value

    @field_validator("outras_especialidades", mode="before")
    @classmethod
    def normalize_outras_especialidades(cls, value: Any) -> Any:
        return _normalize_optional_list(value)


class HealthProfessionalCreate(HealthProfessionalBase):
    pass


class HealthProfessionalUpdate(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    user_id: int | None = None
    nome_completo: str | None = Field(None, min_length=2, max_length=255)
    nome_social: str | None = Field(None, max_length=255)
    cpf: str | None = Field(None, min_length=11, max_length=11)
    data_nascimento: date | None = None
    email: EmailStr | None = None
    telefone: str | None = Field(None, max_length=32)
    conselho_tipo: ConselhoTipo | None = None
    conselho_numero: str | None = Field(None, min_length=1, max_length=32)
    conselho_uf: str | None = Field(None, min_length=2, max_length=2)
    especialidade_principal: str | None = Field(None, max_length=120)
    outras_especialidades: list[str] | None = None
    rqe: str | None = Field(None, max_length=32)
    ativo: bool | None = None

    _normalize_nome = field_validator("nome_completo", mode="before")(_blank_to_none)
    _normalize_optional_text = field_validator(
        "nome_social",
        "email",
        "telefone",
        "especialidade_principal",
        "rqe",
        mode="before",
    )(_blank_to_none)
    _normalize_cpf = field_validator("cpf", mode="before")(_digits_or_none)
    _normalize_tipo = field_validator("conselho_tipo", mode="before")(_normalize_conselho_tipo)
    _normalize_numero = field_validator("conselho_numero", mode="before")(_blank_to_none)
    _normalize_outras = field_validator("outras_especialidades", mode="before")(_normalize_optional_list)

    @field_validator("conselho_uf", mode="before")
    @classmethod
    def normalize_conselho_uf(cls, value: Any) -> Any:
        value = _blank_to_none(value)
        if isinstance(value, str):
            return value.upper()
        return value

    @field_validator("nome_completo")
    @classmethod
    def validate_nome_completo(cls, value: str | None) -> str | None:
        if value is None:
            return value
        nome = " ".join(value.strip().split())
        if len(nome) < 2:
            raise ValueError("O nome completo deve ter pelo menos 2 caracteres.")
        return nome


class HealthProfessionalRead(HealthProfessionalBase):
    id: int
    ativo: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True, use_enum_values=True)


class HealthProfessionalList(BaseModel):
    items: list[HealthProfessionalRead]
    total: int
    page: int
    page_size: int


class HealthProfessionalSearch(BaseModel):
    nome: str | None = Field(None, min_length=1, max_length=255)
    cpf: str | None = None
    conselho: str | None = Field(None, min_length=1, max_length=64)
    especialidade: str | None = Field(None, min_length=1, max_length=120)
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)

    _normalize_nome = field_validator("nome", mode="before")(_blank_to_none)
    _normalize_cpf = field_validator("cpf", mode="before")(_digits_or_none)
    _normalize_conselho = field_validator("conselho", mode="before")(_blank_to_none)
    _normalize_especialidade = field_validator("especialidade", mode="before")(_blank_to_none)
