from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, String, func, true
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class Patient(Base):
    __tablename__ = "patients"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    nome_completo: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    nome_social: Mapped[str | None] = mapped_column(String(255), nullable=True)
    data_nascimento: Mapped[date | None] = mapped_column(Date, nullable=True)
    sexo: Mapped[str | None] = mapped_column(String(32), nullable=True)
    cpf: Mapped[str | None] = mapped_column(String(11), nullable=True, unique=True, index=True)
    rg: Mapped[str | None] = mapped_column(String(32), nullable=True)
    cns: Mapped[str | None] = mapped_column(String(15), nullable=True, unique=True, index=True)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    telefone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    telefone_secundario: Mapped[str | None] = mapped_column(String(32), nullable=True)
    nome_mae: Mapped[str | None] = mapped_column(String(255), nullable=True)
    nome_pai: Mapped[str | None] = mapped_column(String(255), nullable=True)
    estado_civil: Mapped[str | None] = mapped_column(String(64), nullable=True)
    profissao: Mapped[str | None] = mapped_column(String(120), nullable=True)
    cep: Mapped[str | None] = mapped_column(String(8), nullable=True)
    logradouro: Mapped[str | None] = mapped_column(String(255), nullable=True)
    numero: Mapped[str | None] = mapped_column(String(32), nullable=True)
    complemento: Mapped[str | None] = mapped_column(String(120), nullable=True)
    bairro: Mapped[str | None] = mapped_column(String(120), nullable=True)
    cidade: Mapped[str | None] = mapped_column(String(120), nullable=True)
    estado: Mapped[str | None] = mapped_column(String(2), nullable=True)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=true())
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
