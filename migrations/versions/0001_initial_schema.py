"""Add the user model and establish the initial schema.

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-09-22
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = "0001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    existing_tables = set(inspect(bind).get_table_names())

    if "users" not in existing_tables:
        op.create_table(
            "users",
            sa.Column("id", sa.String(length=32), nullable=False),
            sa.Column("login_identifier", sa.String(length=255), nullable=True),
            sa.Column("password_hash", sa.String(length=255), nullable=True),
            sa.Column("provider_subject", sa.String(length=255), nullable=True),
            sa.Column(
                "status",
                sa.String(length=20),
                server_default=sa.text("'ACTIVE'"),
                nullable=False,
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=False,
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("login_identifier", name="uq_users_login_identifier"),
            sa.UniqueConstraint("provider_subject", name="uq_users_provider_subject"),
        )

    if "photos" not in existing_tables:
        op.create_table(
            "photos",
            sa.Column("id", sa.String(length=32), nullable=False),
            sa.Column("original_filename", sa.String(length=255), nullable=True),
            sa.Column("content_type", sa.String(length=100), nullable=False),
            sa.Column("size", sa.Integer(), nullable=False),
            sa.Column("width", sa.Integer(), nullable=False),
            sa.Column("height", sa.Integer(), nullable=False),
            sa.Column("storage_path", sa.String(length=1024), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=False,
            ),
            sa.PrimaryKeyConstraint("id"),
        )

    if "photo_variants" not in existing_tables:
        op.create_table(
            "photo_variants",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("photo_id", sa.String(length=32), nullable=False),
            sa.Column("output_format", sa.String(length=10), nullable=False),
            sa.Column("content_type", sa.String(length=100), nullable=False),
            sa.Column("width", sa.Integer(), nullable=False),
            sa.Column("height", sa.Integer(), nullable=False),
            sa.Column("size", sa.Integer(), nullable=False),
            sa.Column("storage_path", sa.String(length=1024), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(
                ["photo_id"], ["photos.id"], ondelete="CASCADE"
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "photo_id",
                "width",
                "height",
                "output_format",
                name="uq_photo_variant_request",
            ),
        )
        op.create_index(
            "ix_photo_variants_photo_id", "photo_variants", ["photo_id"]
        )


def downgrade() -> None:
    # Keep legacy photo tables intact on downgrade; this revision may have
    # adopted a database that already contained them.
    op.drop_table("users")
