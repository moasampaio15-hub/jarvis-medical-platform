"""create exam results tables

Revision ID: 202608140301
Revises: 202608131720
Create Date: 2026-08-14 03:01:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "202608140301"
down_revision: str | None = "202608131720"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "exam_results",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("exam_order_id", sa.Integer(), nullable=False),
        sa.Column("patient_id", sa.Integer(), nullable=False),
        sa.Column("professional_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="draft", nullable=False),
        sa.Column("coletado_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("liberado_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("laudo", sa.Text(), nullable=True),
        sa.Column("observacoes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "status IN ('draft', 'preliminary', 'final', 'canceled')",
            name="ck_exam_results_status",
        ),
        sa.ForeignKeyConstraint(["exam_order_id"], ["exam_orders.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["professional_id"], ["health_professionals.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("exam_order_id", name="uq_exam_results_exam_order_id"),
    )
    op.create_index("ix_exam_results_exam_order_id", "exam_results", ["exam_order_id"], unique=False)
    op.create_index("ix_exam_results_patient_id", "exam_results", ["patient_id"], unique=False)
    op.create_index("ix_exam_results_professional_id", "exam_results", ["professional_id"], unique=False)
    op.create_index("ix_exam_results_status", "exam_results", ["status"], unique=False)
    op.create_index(
        "ix_exam_results_patient_created",
        "exam_results",
        ["patient_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_exam_results_professional_created",
        "exam_results",
        ["professional_id", "created_at"],
        unique=False,
    )

    op.create_table(
        "exam_result_items",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("exam_result_id", sa.Integer(), nullable=False),
        sa.Column("exam_order_item_id", sa.Integer(), nullable=False),
        sa.Column("nome_exame", sa.String(length=255), nullable=False),
        sa.Column("codigo", sa.String(length=64), nullable=True),
        sa.Column("resultado", sa.Text(), nullable=False),
        sa.Column("unidade", sa.String(length=64), nullable=True),
        sa.Column("valor_referencia", sa.String(length=255), nullable=True),
        sa.Column("interpretacao", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["exam_result_id"], ["exam_results.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["exam_order_item_id"], ["exam_order_items.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_exam_result_items_exam_result_id",
        "exam_result_items",
        ["exam_result_id"],
        unique=False,
    )
    op.create_index(
        "ix_exam_result_items_exam_order_item_id",
        "exam_result_items",
        ["exam_order_item_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_exam_result_items_exam_order_item_id", table_name="exam_result_items")
    op.drop_index("ix_exam_result_items_exam_result_id", table_name="exam_result_items")
    op.drop_table("exam_result_items")
    op.drop_index("ix_exam_results_professional_created", table_name="exam_results")
    op.drop_index("ix_exam_results_patient_created", table_name="exam_results")
    op.drop_index("ix_exam_results_status", table_name="exam_results")
    op.drop_index("ix_exam_results_professional_id", table_name="exam_results")
    op.drop_index("ix_exam_results_patient_id", table_name="exam_results")
    op.drop_index("ix_exam_results_exam_order_id", table_name="exam_results")
    op.drop_table("exam_results")
