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


class ExamOrder(Base):
    __tablename__ = "exam_orders"
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'requested', 'completed', 'canceled')",
            name="ck_exam_orders_status",
        ),
        CheckConstraint(
            "prioridade IN ('rotina', 'urgente')",
            name="ck_exam_orders_prioridade",
        ),
        Index("ix_exam_orders_patient_created", "patient_id", "created_at"),
        Index("ix_exam_orders_professional_created", "professional_id", "created_at"),
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
    prioridade: Mapped[str] = mapped_column(
        String(32), nullable=False, default="rotina", server_default="rotina", index=True
    )
    justificativa: Mapped[str | None] = mapped_column(Text, nullable=True)
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
    items: Mapped[list[ExamOrderItem]] = relationship(
        "ExamOrderItem",
        back_populates="exam_order",
        cascade="all, delete-orphan",
        order_by="ExamOrderItem.id",
    )


class ExamOrderItem(Base):
    __tablename__ = "exam_order_items"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    exam_order_id: Mapped[int] = mapped_column(
        ForeignKey("exam_orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    nome_exame: Mapped[str] = mapped_column(String(255), nullable=False)
    codigo: Mapped[str | None] = mapped_column(String(64), nullable=True)
    material: Mapped[str | None] = mapped_column(String(120), nullable=True)
    orientacoes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    exam_order: Mapped[ExamOrder] = relationship("ExamOrder", back_populates="items")
