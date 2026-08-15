from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.appointment import Appointment
    from app.models.health_professional import HealthProfessional
    from app.models.medical_record import MedicalRecord
    from app.models.patient import Patient


class ClinicalDiagnosis(Base):
    __tablename__ = "clinical_diagnoses"
    __table_args__ = (
        CheckConstraint("tipo IN ('hipotese', 'confirmado', 'problema')", name="ck_clinical_diagnoses_tipo"),
        CheckConstraint("status IN ('ativo', 'resolvido')", name="ck_clinical_diagnoses_status"),
        CheckConstraint("data_resolucao IS NULL OR data_inicio IS NULL OR data_resolucao >= data_inicio", name="ck_clinical_diagnoses_date_range"),
        Index("ix_clinical_diagnoses_patient_status", "patient_id", "status"),
        Index("ix_clinical_diagnoses_patient_created", "patient_id", "created_at"),
        Index("ix_clinical_diagnoses_professional_created", "professional_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id", ondelete="RESTRICT"), nullable=False, index=True)
    professional_id: Mapped[int] = mapped_column(ForeignKey("health_professionals.id", ondelete="RESTRICT"), nullable=False, index=True)
    appointment_id: Mapped[int | None] = mapped_column(ForeignKey("appointments.id", ondelete="SET NULL"), nullable=True, index=True)
    medical_record_id: Mapped[int | None] = mapped_column(ForeignKey("medical_records.id", ondelete="SET NULL"), nullable=True, index=True)
    cid10_codigo: Mapped[str | None] = mapped_column(String(16), nullable=True, index=True)
    descricao: Mapped[str] = mapped_column(String(255), nullable=False)
    tipo: Mapped[str] = mapped_column(String(32), nullable=False, default="hipotese", server_default="hipotese", index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="ativo", server_default="ativo", index=True)
    data_inicio: Mapped[date | None] = mapped_column(Date, nullable=True)
    data_resolucao: Mapped[date | None] = mapped_column(Date, nullable=True)
    observacoes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    patient: Mapped[Patient] = relationship("Patient")
    professional: Mapped[HealthProfessional] = relationship("HealthProfessional")
    appointment: Mapped[Appointment | None] = relationship("Appointment")
    medical_record: Mapped[MedicalRecord | None] = relationship("MedicalRecord")
