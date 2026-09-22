"""Add per-viewer result history entries.

Revision ID: 0010_history_entries
Revises: 0009_round_submissions
Create Date: 2026-09-22
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0010_history_entries"
down_revision: Union[str, None] = "0009_round_submissions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "history_entries",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("connection_id", sa.String(length=32), nullable=False),
        sa.Column("round_id", sa.String(length=32), nullable=False),
        sa.Column("submission_id", sa.String(length=32), nullable=False),
        sa.Column("viewer_id", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="ACTIVE"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("purge_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["connection_id"], ["connections.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["round_id"], ["rounds.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["submission_id"], ["round_submissions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["viewer_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("viewer_id", "submission_id", name="uq_history_entries_viewer_submission"),
    )
    op.create_index("ix_history_entries_connection_id", "history_entries", ["connection_id"])
    op.create_index("ix_history_entries_round_id", "history_entries", ["round_id"])
    op.create_index("ix_history_entries_submission_id", "history_entries", ["submission_id"])
    op.create_index("ix_history_entries_viewer_id", "history_entries", ["viewer_id"])


def downgrade() -> None:
    op.drop_index("ix_history_entries_viewer_id", table_name="history_entries")
    op.drop_index("ix_history_entries_submission_id", table_name="history_entries")
    op.drop_index("ix_history_entries_round_id", table_name="history_entries")
    op.drop_index("ix_history_entries_connection_id", table_name="history_entries")
    op.drop_table("history_entries")
