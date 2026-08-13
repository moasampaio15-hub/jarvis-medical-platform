"""create appointments table

Revision ID: 202608130130
Revises: 202608080230
Create Date: 2026-08-13 01:30:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "202608130130"
down_revision: str | None = "202608080230"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "appointments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("patient_id", sa.Integer(), nullable=False),
        sa.Column("professional_id", sa.Integer(), nullable=False),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="scheduled", nullable=False),
        sa.Column("motivo", sa.String(length=255), nullable=True),
        sa.Column("observacoes", sa.Text(), nullable=True),
        sa.Column("cancel_reason", sa.String(length=255), nullable=True),
        sa.Column("canceled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "status IN ('scheduled', 'confirmed', 'canceled', 'completed', 'no_show')",
            name="ck_appointments_status",
        ),
        sa.CheckConstraint("end_at > start_at", name="ck_appointments_time_range"),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["professional_id"], ["health_professionals.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_appointments_patient_id", "appointments", ["patient_id"], unique=False)
    op.create_index("ix_appointments_professional_id", "appointments", ["professional_id"], unique=False)
    op.create_index("ix_appointments_start_at", "appointments", ["start_at"], unique=False)
    op.create_index("ix_appointments_end_at", "appointments", ["end_at"], unique=False)
    op.create_index("ix_appointments_status", "appointments", ["status"], unique=False)
    op.create_index("ix_appointments_period", "appointments", ["start_at", "end_at"], unique=False)
    op.create_index(
        "ix_appointments_patient_period",
        "appointments",
        ["patient_id", "start_at", "end_at"],
        unique=False,
    )
    op.create_index(
        "ix_appointments_professional_period",
        "appointments",
        ["professional_id", "start_at", "end_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_appointments_professional_period", table_name="appointments")
    op.drop_index("ix_appointments_patient_period", table_name="appointments")
    op.drop_index("ix_appointments_period", table_name="appointments")
    op.drop_index("ix_appointments_status", table_name="appointments")
    op.drop_index("ix_appointments_end_at", table_name="appointments")
    op.drop_index("ix_appointments_start_at", table_name="appointments")
    op.drop_index("ix_appointments_professional_id", table_name="appointments")
    op.drop_index("ix_appointments_patient_id", table_name="appointments")
    op.drop_table("appointments")
