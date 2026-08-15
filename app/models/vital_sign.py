from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Numeric, SmallInteger, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.appointment import Appointment
    from app.models.health_professional import HealthProfessional
    from app.models.medical_record import MedicalRecord
    from app.models.patient import Patient


class VitalSign(Base):
    __tablename__ = "vital_signs"
    __table_args__ = (
        CheckConstraint("pressao_sistolica IS NULL OR pressao_sistolica BETWEEN 50 AND 300", name="ck_vital_signs_pressao_sistolica"),
        CheckConstraint("pressao_diastolica IS NULL OR pressao_diastolica BETWEEN 30 AND 200", name="ck_vital_signs_pressao_diastolica"),
        CheckConstraint("frequencia_cardiaca IS NULL OR frequencia_cardiaca BETWEEN 20 AND 250", name="ck_vital_signs_frequencia_cardiaca"),
        CheckConstraint("frequencia_respiratoria IS NULL OR frequencia_respiratoria BETWEEN 5 AND 80", name="ck_vital_signs_frequencia_respiratoria"),
        CheckConstraint("temperatura_c IS NULL OR temperatura_c BETWEEN 30 AND 45", name="ck_vital_signs_temperatura_c"),
        CheckConstraint("spo2 IS NULL OR spo2 BETWEEN 0 AND 100", name="ck_vital_signs_spo2"),
        CheckConstraint("peso_kg IS NULL OR peso_kg BETWEEN 0.5 AND 500", name="ck_vital_signs_peso_kg"),
        CheckConstraint("altura_cm IS NULL OR altura_cm BETWEEN 30 AND 250", name="ck_vital_signs_altura_cm"),
        CheckConstraint("imc IS NULL OR imc BETWEEN 5 AND 100", name="ck_vital_signs_imc"),
        CheckConstraint("glicemia_capilar IS NULL OR glicemia_capilar BETWEEN 20 AND 1000", name="ck_vital_signs_glicemia_capilar"),
        CheckConstraint("dor_escala IS NULL OR dor_escala BETWEEN 0 AND 10", name="ck_vital_signs_dor_escala"),
        Index("ix_vital_signs_patient_recorded", "patient_id", "recorded_at"),
        Index("ix_vital_signs_professional_recorded", "professional_id", "recorded_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id", ondelete="RESTRICT"), nullable=False, index=True)
    professional_id: Mapped[int] = mapped_column(ForeignKey("health_professionals.id", ondelete="RESTRICT"), nullable=False, index=True)
    appointment_id: Mapped[int | None] = mapped_column(ForeignKey("appointments.id", ondelete="SET NULL"), nullable=True, index=True)
    medical_record_id: Mapped[int | None] = mapped_column(ForeignKey("medical_records.id", ondelete="SET NULL"), nullable=True, index=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)
    pressao_sistolica: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    pressao_diastolica: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    frequencia_cardiaca: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    frequencia_respiratoria: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    temperatura_c: Mapped[Decimal | None] = mapped_column(Numeric(4, 1), nullable=True)
    spo2: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    peso_kg: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    altura_cm: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    imc: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    glicemia_capilar: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    dor_escala: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    observacoes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    patient: Mapped[Patient] = relationship("Patient")
    professional: Mapped[HealthProfessional] = relationship("HealthProfessional")
    appointment: Mapped[Appointment | None] = relationship("Appointment")
    medical_record: Mapped[MedicalRecord | None] = relationship("MedicalRecord")
