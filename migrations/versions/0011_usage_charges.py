"""Add idempotent round usage charges.

Revision ID: 0011_usage_charges
Revises: 0010_history_entries
Create Date: 2026-09-22
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0011_usage_charges"
down_revision: Union[str, None] = "0010_history_entries"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "usage_charges",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("user_id", sa.String(length=32), nullable=False),
        sa.Column("connection_id", sa.String(length=32), nullable=False),
        sa.Column("round_id", sa.String(length=32), nullable=False),
        sa.Column("usage_date", sa.Date(), nullable=False),
        sa.Column("units", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["connection_id"], ["connections.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["round_id"], ["rounds.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("round_id", name="uq_usage_charges_round_id"),
    )
    op.create_index("ix_usage_charges_user_id", "usage_charges", ["user_id"])
    op.create_index("ix_usage_charges_connection_id", "usage_charges", ["connection_id"])
    op.create_index("ix_usage_charges_round_id", "usage_charges", ["round_id"])
    op.create_index("ix_usage_charges_usage_date", "usage_charges", ["usage_date"])


def downgrade() -> None:
    op.drop_index("ix_usage_charges_usage_date", table_name="usage_charges")
    op.drop_index("ix_usage_charges_round_id", table_name="usage_charges")
    op.drop_index("ix_usage_charges_connection_id", table_name="usage_charges")
    op.drop_index("ix_usage_charges_user_id", table_name="usage_charges")
    op.drop_table("usage_charges")
