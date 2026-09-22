"""Add immutable per-user round submissions.

Revision ID: 0009_round_submissions
Revises: 0008_drafts
Create Date: 2026-09-22
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0009_round_submissions"
down_revision: Union[str, None] = "0008_drafts"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "round_submissions",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("round_id", sa.String(length=32), nullable=False),
        sa.Column("editor_id", sa.String(length=32), nullable=False),
        sa.Column("asset_id", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="SUBMITTED"),
        sa.Column("submitted_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["round_id"], ["rounds.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["editor_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("round_id", "editor_id", name="uq_round_submissions_round_editor"),
    )
    op.create_index("ix_round_submissions_round_id", "round_submissions", ["round_id"])
    op.create_index("ix_round_submissions_editor_id", "round_submissions", ["editor_id"])


def downgrade() -> None:
    op.drop_index("ix_round_submissions_editor_id", table_name="round_submissions")
    op.drop_index("ix_round_submissions_round_id", table_name="round_submissions")
    op.drop_table("round_submissions")
