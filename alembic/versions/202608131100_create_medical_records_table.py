"""create medical records table

Revision ID: 202608131100
Revises: 202608130130
Create Date: 2026-08-13 11:00:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "202608131100"
down_revision: str | None = "202608130130"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "medical_records",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("patient_id", sa.Integer(), nullable=False),
        sa.Column("professional_id", sa.Integer(), nullable=False),
        sa.Column("appointment_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=32), server_default="draft", nullable=False),
        sa.Column("queixa_principal", sa.String(length=255), nullable=False),
        sa.Column("historia_clinica", sa.Text(), nullable=True),
        sa.Column("exame_fisico", sa.Text(), nullable=True),
        sa.Column("conduta", sa.Text(), nullable=False),
        sa.Column("observacoes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "status IN ('draft', 'finalized', 'amended')",
            name="ck_medical_records_status",
        ),
        sa.ForeignKeyConstraint(["appointment_id"], ["appointments.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["professional_id"], ["health_professionals.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_medical_records_appointment_id", "medical_records", ["appointment_id"], unique=True)
    op.create_index("ix_medical_records_patient_id", "medical_records", ["patient_id"], unique=False)
    op.create_index("ix_medical_records_professional_id", "medical_records", ["professional_id"], unique=False)
    op.create_index("ix_medical_records_status", "medical_records", ["status"], unique=False)
    op.create_index(
        "ix_medical_records_patient_created",
        "medical_records",
        ["patient_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_medical_records_professional_created",
        "medical_records",
        ["professional_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_medical_records_professional_created", table_name="medical_records")
    op.drop_index("ix_medical_records_patient_created", table_name="medical_records")
    op.drop_index("ix_medical_records_status", table_name="medical_records")
    op.drop_index("ix_medical_records_professional_id", table_name="medical_records")
    op.drop_index("ix_medical_records_patient_id", table_name="medical_records")
    op.drop_index("ix_medical_records_appointment_id", table_name="medical_records")
    op.drop_table("medical_records")
