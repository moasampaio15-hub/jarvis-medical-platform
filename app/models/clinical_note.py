from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.appointment import Appointment
    from app.models.health_professional import HealthProfessional
    from app.models.medical_record import MedicalRecord
    from app.models.patient import Patient


class ClinicalNote(Base):
    __tablename__ = "clinical_notes"
    __table_args__ = (
        CheckConstraint(
            "tipo IN ('evolucao', 'atendimento', 'retorno', 'intercorrencia', 'orientacao')",
            name="ck_clinical_notes_tipo",
        ),
        Index("ix_clinical_notes_patient_recorded", "patient_id", "recorded_at"),
        Index("ix_clinical_notes_professional_recorded", "professional_id", "recorded_at"),
        Index("ix_clinical_notes_record_type", "medical_record_id", "tipo"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id", ondelete="RESTRICT"), nullable=False, index=True)
    professional_id: Mapped[int] = mapped_column(ForeignKey("health_professionals.id", ondelete="RESTRICT"), nullable=False, index=True)
    appointment_id: Mapped[int | None] = mapped_column(ForeignKey("appointments.id", ondelete="SET NULL"), nullable=True, index=True)
    medical_record_id: Mapped[int | None] = mapped_column(ForeignKey("medical_records.id", ondelete="SET NULL"), nullable=True, index=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)
    tipo: Mapped[str] = mapped_column(String(32), nullable=False, default="evolucao", server_default="evolucao", index=True)
    queixa_motivo: Mapped[str | None] = mapped_column(String(255), nullable=True)
    historia_clinica: Mapped[str | None] = mapped_column(Text, nullable=True)
    exame_achados: Mapped[str | None] = mapped_column(Text, nullable=True)
    avaliacao: Mapped[str | None] = mapped_column(Text, nullable=True)
    plano_conduta: Mapped[str | None] = mapped_column(Text, nullable=True)
    observacoes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    patient: Mapped[Patient] = relationship("Patient")
    professional: Mapped[HealthProfessional] = relationship("HealthProfessional")
    appointment: Mapped[Appointment | None] = relationship("Appointment")
    medical_record: Mapped[MedicalRecord | None] = relationship("MedicalRecord")
