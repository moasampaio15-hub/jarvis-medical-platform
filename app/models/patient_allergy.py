from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.health_professional import HealthProfessional
    from app.models.medical_record import MedicalRecord
    from app.models.patient import Patient


class PatientAllergy(Base):
    __tablename__ = "patient_allergies"
    __table_args__ = (
        CheckConstraint(
            "tipo IN ('allergy', 'intolerance', 'adverse_reaction', 'unknown')",
            name="ck_patient_allergies_tipo",
        ),
        CheckConstraint(
            "categoria IN ('medication', 'food', 'environment', 'latex', 'other', 'unknown')",
            name="ck_patient_allergies_categoria",
        ),
        CheckConstraint(
            "gravidade IN ('mild', 'moderate', 'severe', 'life_threatening', 'unknown')",
            name="ck_patient_allergies_gravidade",
        ),
        CheckConstraint(
            "status IN ('active', 'inactive', 'entered_in_error')",
            name="ck_patient_allergies_status",
        ),
        Index("ix_patient_allergies_patient_status", "patient_id", "status"),
        Index("ix_patient_allergies_patient_substancia", "patient_id", "substancia"),
        Index("ix_patient_allergies_professional_created", "professional_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    patient_id: Mapped[int] = mapped_column(
        ForeignKey("patients.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    professional_id: Mapped[int] = mapped_column(
        ForeignKey("health_professionals.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    medical_record_id: Mapped[int | None] = mapped_column(
        ForeignKey("medical_records.id", ondelete="SET NULL"), nullable=True, index=True
    )
    tipo: Mapped[str] = mapped_column(
        String(32), nullable=False, default="allergy", server_default="allergy", index=True
    )
    categoria: Mapped[str] = mapped_column(
        String(32), nullable=False, default="unknown", server_default="unknown", index=True
    )
    substancia: Mapped[str] = mapped_column(String(255), nullable=False)
    reacao: Mapped[str | None] = mapped_column(String(255), nullable=True)
    gravidade: Mapped[str] = mapped_column(
        String(32), nullable=False, default="unknown", server_default="unknown", index=True
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="active", server_default="active", index=True
    )
    observado_em: Mapped[date | None] = mapped_column(Date, nullable=True)
    observacoes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    patient: Mapped[Patient] = relationship("Patient")
    professional: Mapped[HealthProfessional] = relationship("HealthProfessional")
    medical_record: Mapped[MedicalRecord | None] = relationship("MedicalRecord")
