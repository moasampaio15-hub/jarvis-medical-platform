from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.exam_order import ExamOrder, ExamOrderItem
    from app.models.health_professional import HealthProfessional
    from app.models.patient import Patient


class ExamResult(Base):
    __tablename__ = "exam_results"
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'preliminary', 'final', 'canceled')",
            name="ck_exam_results_status",
        ),
        UniqueConstraint("exam_order_id", name="uq_exam_results_exam_order_id"),
        Index("ix_exam_results_patient_created", "patient_id", "created_at"),
        Index("ix_exam_results_professional_created", "professional_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    exam_order_id: Mapped[int] = mapped_column(
        ForeignKey("exam_orders.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    patient_id: Mapped[int] = mapped_column(
        ForeignKey("patients.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    professional_id: Mapped[int] = mapped_column(
        ForeignKey("health_professionals.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="draft", server_default="draft", index=True
    )
    coletado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    liberado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    laudo: Mapped[str | None] = mapped_column(Text, nullable=True)
    observacoes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    exam_order: Mapped[ExamOrder] = relationship("ExamOrder")
    patient: Mapped[Patient] = relationship("Patient")
    professional: Mapped[HealthProfessional] = relationship("HealthProfessional")
    items: Mapped[list[ExamResultItem]] = relationship(
        "ExamResultItem",
        back_populates="exam_result",
        cascade="all, delete-orphan",
        order_by="ExamResultItem.id",
    )


class ExamResultItem(Base):
    __tablename__ = "exam_result_items"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    exam_result_id: Mapped[int] = mapped_column(
        ForeignKey("exam_results.id", ondelete="CASCADE"), nullable=False, index=True
    )
    exam_order_item_id: Mapped[int] = mapped_column(
        ForeignKey("exam_order_items.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    nome_exame: Mapped[str] = mapped_column(String(255), nullable=False)
    codigo: Mapped[str | None] = mapped_column(String(64), nullable=True)
    resultado: Mapped[str] = mapped_column(Text, nullable=False)
    unidade: Mapped[str | None] = mapped_column(String(64), nullable=True)
    valor_referencia: Mapped[str | None] = mapped_column(String(255), nullable=True)
    interpretacao: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    exam_result: Mapped[ExamResult] = relationship("ExamResult", back_populates="items")
    exam_order_item: Mapped[ExamOrderItem] = relationship("ExamOrderItem")
