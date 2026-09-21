"""Add validated private image assets.

Revision ID: 0007_assets
Revises: 0006_rounds
Create Date: 2026-09-22
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0007_assets"
down_revision: Union[str, None] = "0006_rounds"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "assets",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("connection_id", sa.String(length=32), nullable=False),
        sa.Column("round_id", sa.String(length=32), nullable=True),
        sa.Column("owner_id", sa.String(length=32), nullable=False),
        sa.Column("kind", sa.String(length=20), server_default="INPUT", nullable=False),
        sa.Column("content_type", sa.String(length=100), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("storage_path", sa.String(length=1024), nullable=False),
        sa.Column("state", sa.String(length=20), server_default="ACTIVE", nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["connection_id"], ["connections.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["round_id"], ["rounds.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_assets_connection_id", "assets", ["connection_id"])
    op.create_index("ix_assets_round_id", "assets", ["round_id"])
    op.create_index("ix_assets_owner_id", "assets", ["owner_id"])
    op.create_foreign_key(
        "fk_round_inputs_asset_id_assets",
        "round_inputs",
        "assets",
        ["asset_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_round_inputs_asset_id_assets", "round_inputs", type_="foreignkey")
    op.drop_index("ix_assets_owner_id", table_name="assets")
    op.drop_index("ix_assets_round_id", table_name="assets")
    op.drop_index("ix_assets_connection_id", table_name="assets")
    op.drop_table("assets")
