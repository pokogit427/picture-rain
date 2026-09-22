"""Add per-user temporary editor drafts.

Revision ID: 0008_drafts
Revises: 0007_assets
Create Date: 2026-09-22
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0008_drafts"
down_revision: Union[str, None] = "0007_assets"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "drafts",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("round_id", sa.String(length=32), nullable=False),
        sa.Column("editor_id", sa.String(length=32), nullable=False),
        sa.Column("preview_asset_id", sa.String(length=32), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("document_json", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="ACTIVE"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["round_id"], ["rounds.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["editor_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["preview_asset_id"], ["assets.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("round_id", "editor_id", name="uq_drafts_round_editor"),
    )
    op.create_index("ix_drafts_round_id", "drafts", ["round_id"])
    op.create_index("ix_drafts_editor_id", "drafts", ["editor_id"])


def downgrade() -> None:
    op.drop_index("ix_drafts_editor_id", table_name="drafts")
    op.drop_index("ix_drafts_round_id", table_name="drafts")
    op.drop_table("drafts")
