"""Add exchange rounds and one input per member.

Revision ID: 0006_rounds
Revises: 0005_photo_owners
Create Date: 2026-09-22
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0006_rounds"
down_revision: Union[str, None] = "0005_photo_owners"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "rounds",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("connection_id", sa.String(length=32), nullable=False),
        sa.Column("created_by_id", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="OPEN", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revealed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["connection_id"], ["connections.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_rounds_connection_id", "rounds", ["connection_id"])
    op.create_index("ix_rounds_created_by_id", "rounds", ["created_by_id"])
    op.create_table(
        "round_inputs",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("round_id", sa.String(length=32), nullable=False),
        sa.Column("sender_id", sa.String(length=32), nullable=False),
        sa.Column("asset_id", sa.String(length=32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["round_id"], ["rounds.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["sender_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("round_id", "sender_id", name="uq_round_inputs_round_sender"),
    )
    op.create_index("ix_round_inputs_round_id", "round_inputs", ["round_id"])
    op.create_index("ix_round_inputs_sender_id", "round_inputs", ["sender_id"])


def downgrade() -> None:
    op.drop_index("ix_round_inputs_sender_id", table_name="round_inputs")
    op.drop_index("ix_round_inputs_round_id", table_name="round_inputs")
    op.drop_table("round_inputs")
    op.drop_index("ix_rounds_created_by_id", table_name="rounds")
    op.drop_index("ix_rounds_connection_id", table_name="rounds")
    op.drop_table("rounds")
