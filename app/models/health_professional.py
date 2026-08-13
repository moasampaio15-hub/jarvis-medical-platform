from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    func,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class HealthProfessional(Base):
    __tablename__ = "health_professionals"
    __table_args__ = (
        CheckConstraint(
            "conselho_tipo IN ('CRM', 'COREN', 'CRO', 'CRF', 'CREFITO', 'CRP', 'outro')",
            name="ck_health_professionals_conselho_tipo",
        ),
        UniqueConstraint(
            "conselho_numero",
            "conselho_tipo",
            "conselho_uf",
            name="uq_health_professionals_conselho",
        ),
        Index(
            "ix_health_professionals_conselho",
            "conselho_tipo",
            "conselho_uf",
            "conselho_numero",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, unique=True, index=True
    )
    nome_completo: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    nome_social: Mapped[str | None] = mapped_column(String(255), nullable=True)
    cpf: Mapped[str | None] = mapped_column(String(11), nullable=True, unique=True, index=True)
    data_nascimento: Mapped[date | None] = mapped_column(Date, nullable=True)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    telefone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    conselho_tipo: Mapped[str] = mapped_column(String(16), nullable=False)
    conselho_numero: Mapped[str] = mapped_column(String(32), nullable=False)
    conselho_uf: Mapped[str] = mapped_column(String(2), nullable=False)
    especialidade_principal: Mapped[str | None] = mapped_column(String(120), nullable=True)
    outras_especialidades: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    rqe: Mapped[str | None] = mapped_column(String(32), nullable=True)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=true())
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    user: Mapped[User | None] = relationship("User")
