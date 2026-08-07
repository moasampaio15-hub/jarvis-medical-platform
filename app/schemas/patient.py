from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


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


class PatientBase(BaseModel):
    nome_completo: str = Field(..., min_length=2, max_length=255, examples=["Paciente Fictício Alfa"])
    nome_social: str | None = Field(None, max_length=255, examples=["Alfa"])
    data_nascimento: date | None = Field(None, examples=["1990-01-15"])
    sexo: str | None = Field(None, max_length=32, examples=["feminino"])
    cpf: str | None = Field(None, min_length=11, max_length=11, examples=["12345678901"])
    rg: str | None = Field(None, max_length=32, examples=["RG123456"])
    cns: str | None = Field(None, min_length=15, max_length=15, examples=["123456789012345"])
    email: EmailStr | None = Field(None, examples=["paciente.ficticio@example.com"])
    telefone: str | None = Field(None, max_length=32, examples=["11999990000"])
    telefone_secundario: str | None = Field(None, max_length=32, examples=["11888880000"])
    nome_mae: str | None = Field(None, max_length=255, examples=["Responsável Fictícia"])
    nome_pai: str | None = Field(None, max_length=255, examples=["Responsável Fictício"])
    estado_civil: str | None = Field(None, max_length=64, examples=["solteiro"])
    profissao: str | None = Field(None, max_length=120, examples=["Analista fictício"])
    cep: str | None = Field(None, min_length=8, max_length=8, examples=["01001000"])
    logradouro: str | None = Field(None, max_length=255, examples=["Rua Fictícia"])
    numero: str | None = Field(None, max_length=32, examples=["100"])
    complemento: str | None = Field(None, max_length=120, examples=["Apto 10"])
    bairro: str | None = Field(None, max_length=120, examples=["Centro Fictício"])
    cidade: str | None = Field(None, max_length=120, examples=["Cidade Teste"])
    estado: str | None = Field(None, min_length=2, max_length=2, examples=["SP"])

    @field_validator("nome_completo")
    @classmethod
    def validate_nome_completo(cls, value: str) -> str:
        nome = " ".join(value.strip().split())
        if len(nome) < 2:
            raise ValueError("O nome completo deve ter pelo menos 2 caracteres.")
        return nome

    @field_validator(
        "nome_social",
        "sexo",
        "rg",
        "email",
        "telefone",
        "telefone_secundario",
        "nome_mae",
        "nome_pai",
        "estado_civil",
        "profissao",
        "logradouro",
        "numero",
        "complemento",
        "bairro",
        "cidade",
        mode="before",
    )
    @classmethod
    def normalize_optional_text(cls, value: Any) -> Any:
        return _blank_to_none(value)

    @field_validator("cpf", mode="before")
    @classmethod
    def normalize_cpf(cls, value: Any) -> Any:
        return _digits_or_none(value)

    @field_validator("cns", mode="before")
    @classmethod
    def normalize_cns(cls, value: Any) -> Any:
        return _digits_or_none(value)

    @field_validator("cep", mode="before")
    @classmethod
    def normalize_cep(cls, value: Any) -> Any:
        return _digits_or_none(value)

    @field_validator("estado", mode="before")
    @classmethod
    def normalize_estado(cls, value: Any) -> Any:
        value = _blank_to_none(value)
        if isinstance(value, str):
            return value.upper()
        return value


class PatientCreate(PatientBase):
    pass


class PatientUpdate(BaseModel):
    nome_completo: str | None = Field(None, min_length=2, max_length=255)
    nome_social: str | None = Field(None, max_length=255)
    data_nascimento: date | None = None
    sexo: str | None = Field(None, max_length=32)
    cpf: str | None = Field(None, min_length=11, max_length=11)
    rg: str | None = Field(None, max_length=32)
    cns: str | None = Field(None, min_length=15, max_length=15)
    email: EmailStr | None = None
    telefone: str | None = Field(None, max_length=32)
    telefone_secundario: str | None = Field(None, max_length=32)
    nome_mae: str | None = Field(None, max_length=255)
    nome_pai: str | None = Field(None, max_length=255)
    estado_civil: str | None = Field(None, max_length=64)
    profissao: str | None = Field(None, max_length=120)
    cep: str | None = Field(None, min_length=8, max_length=8)
    logradouro: str | None = Field(None, max_length=255)
    numero: str | None = Field(None, max_length=32)
    complemento: str | None = Field(None, max_length=120)
    bairro: str | None = Field(None, max_length=120)
    cidade: str | None = Field(None, max_length=120)
    estado: str | None = Field(None, min_length=2, max_length=2)
    ativo: bool | None = None

    _normalize_nome = field_validator("nome_completo", mode="before")(_blank_to_none)
    _normalize_optional_text = field_validator(
        "nome_social",
        "sexo",
        "rg",
        "email",
        "telefone",
        "telefone_secundario",
        "nome_mae",
        "nome_pai",
        "estado_civil",
        "profissao",
        "logradouro",
        "numero",
        "complemento",
        "bairro",
        "cidade",
        mode="before",
    )(_blank_to_none)
    _normalize_cpf = field_validator("cpf", mode="before")(_digits_or_none)
    _normalize_cns = field_validator("cns", mode="before")(_digits_or_none)
    _normalize_cep = field_validator("cep", mode="before")(_digits_or_none)

    @field_validator("estado", mode="before")
    @classmethod
    def normalize_estado(cls, value: Any) -> Any:
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


class PatientRead(PatientBase):
    id: int
    ativo: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PatientList(BaseModel):
    items: list[PatientRead]
    total: int
    page: int
    page_size: int


class PatientSearch(BaseModel):
    nome: str | None = Field(None, min_length=1, max_length=255)
    cpf: str | None = None
    cns: str | None = None
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)

    _normalize_nome = field_validator("nome", mode="before")(_blank_to_none)
    _normalize_cpf = field_validator("cpf", mode="before")(_digits_or_none)
    _normalize_cns = field_validator("cns", mode="before")(_digits_or_none)
