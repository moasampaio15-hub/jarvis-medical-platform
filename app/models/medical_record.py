from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.appointment import Appointment
    from app.models.health_professional import HealthProfessional
    from app.models.patient import Patient


class MedicalRecord(Base):
    __tablename__ = "medical_records"
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'finalized', 'amended')",
            name="ck_medical_records_status",
        ),
        Index("ix_medical_records_patient_created", "patient_id", "created_at"),
        Index("ix_medical_records_professional_created", "professional_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    patient_id: Mapped[int] = mapped_column(
        ForeignKey("patients.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    professional_id: Mapped[int] = mapped_column(
        ForeignKey("health_professionals.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    appointment_id: Mapped[int | None] = mapped_column(
        ForeignKey("appointments.id", ondelete="SET NULL"), nullable=True, unique=True, index=True
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="draft", server_default="draft", index=True
    )
    queixa_principal: Mapped[str] = mapped_column(String(255), nullable=False)
    historia_clinica: Mapped[str | None] = mapped_column(Text, nullable=True)
    exame_fisico: Mapped[str | None] = mapped_column(Text, nullable=True)
    conduta: Mapped[str] = mapped_column(Text, nullable=False)
    observacoes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    patient: Mapped[Patient] = relationship("Patient")
    professional: Mapped[HealthProfessional] = relationship("HealthProfessional")
    appointment: Mapped[Appointment | None] = relationship("Appointment")
