"""add auth fields to users

Revision ID: 202608061645
Revises: 202608061628
Create Date: 2026-08-06 16:45:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "202608061645"
down_revision: str | None = "202608061628"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("senha_hash", sa.String(length=255), server_default="", nullable=False),
    )
    op.add_column(
        "users",
        sa.Column("ativo", sa.Boolean(), server_default=sa.true(), nullable=False),
    )
    op.add_column(
        "users",
        sa.Column("superuser", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.add_column(
        "users",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.alter_column("users", "senha_hash", server_default=None)
    op.alter_column("users", "email", existing_type=sa.String(length=255), type_=sa.String(length=320))


def downgrade() -> None:
    op.alter_column("users", "email", existing_type=sa.String(length=320), type_=sa.String(length=255))
    op.drop_column("users", "updated_at")
    op.drop_column("users", "superuser")
    op.drop_column("users", "ativo")
    op.drop_column("users", "senha_hash")
