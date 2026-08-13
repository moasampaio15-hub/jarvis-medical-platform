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


class Prescription(Base):
    __tablename__ = "prescriptions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'active', 'completed', 'canceled')",
            name="ck_prescriptions_status",
        ),
        Index("ix_prescriptions_patient_created", "patient_id", "created_at"),
        Index("ix_prescriptions_professional_created", "professional_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    patient_id: Mapped[int] = mapped_column(
        ForeignKey("patients.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    professional_id: Mapped[int] = mapped_column(
        ForeignKey("health_professionals.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    appointment_id: Mapped[int | None] = mapped_column(
        ForeignKey("appointments.id", ondelete="SET NULL"), nullable=True, index=True
    )
    medical_record_id: Mapped[int | None] = mapped_column(
        ForeignKey("medical_records.id", ondelete="SET NULL"), nullable=True, index=True
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="draft", server_default="draft", index=True
    )
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
    medical_record: Mapped[MedicalRecord | None] = relationship("MedicalRecord")
    items: Mapped[list[PrescriptionItem]] = relationship(
        "PrescriptionItem",
        back_populates="prescription",
        cascade="all, delete-orphan",
        order_by="PrescriptionItem.id",
    )


class PrescriptionItem(Base):
    __tablename__ = "prescription_items"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    prescription_id: Mapped[int] = mapped_column(
        ForeignKey("prescriptions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    medicamento: Mapped[str] = mapped_column(String(255), nullable=False)
    apresentacao: Mapped[str] = mapped_column(String(255), nullable=False)
    dose: Mapped[str] = mapped_column(String(120), nullable=False)
    via: Mapped[str] = mapped_column(String(64), nullable=False)
    frequencia: Mapped[str] = mapped_column(String(120), nullable=False)
    duracao: Mapped[str] = mapped_column(String(120), nullable=False)
    orientacoes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    prescription: Mapped[Prescription] = relationship("Prescription", back_populates="items")
