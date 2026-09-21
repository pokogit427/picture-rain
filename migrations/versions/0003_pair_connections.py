"""Add normalized one-to-one user connections.

Revision ID: 0002_auth_sessions
Revises: 0002_auth_sessions
Create Date: 2026-09-22
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0003_pair_connections"
down_revision: Union[str, None] = "0002_auth_sessions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "connections",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("user_low_id", sa.String(length=32), nullable=False),
        sa.Column("user_high_id", sa.String(length=32), nullable=False),
        sa.Column(
            "status", sa.String(length=20), server_default="ACTIVE", nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("disconnected_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "user_low_id <> user_high_id",
            name="ck_connections_distinct_members",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["user_low_id"], ["users.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["user_high_id"], ["users.id"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint(
            "user_low_id", "user_high_id", name="uq_connections_member_pair"
        ),
    )
    op.create_index("ix_connections_user_low_id", "connections", ["user_low_id"])
    op.create_index("ix_connections_user_high_id", "connections", ["user_high_id"])


def downgrade() -> None:
    op.drop_index("ix_connections_user_high_id", table_name="connections")
    op.drop_index("ix_connections_user_low_id", table_name="connections")
    op.drop_table("connections")
