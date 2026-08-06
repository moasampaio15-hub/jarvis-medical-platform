from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class UserCreate(BaseModel):
    nome: str = Field(..., min_length=2, max_length=255, examples=["Ada Lovelace"])
    email: EmailStr = Field(..., examples=["ada@example.com"])
    senha: str = Field(..., min_length=8, max_length=128, examples=["SenhaForte#123"])

    @field_validator("nome")
    @classmethod
    def validate_nome(cls, value: str) -> str:
        nome = value.strip()
        if len(nome) < 2:
            raise ValueError("O nome deve ter pelo menos 2 caracteres.")
        return nome


class UserRead(BaseModel):
    id: int
    nome: str
    email: EmailStr
    ativo: bool
    superuser: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
