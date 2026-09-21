"""Protect legacy photos with explicit owners.

Revision ID: 0005_photo_owners
Revises: 0004_invite_codes
Create Date: 2026-09-22
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0005_photo_owners"
down_revision: Union[str, None] = "0004_invite_codes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("photos", sa.Column("owner_id", sa.String(length=32), nullable=True))
    op.create_index("ix_photos_owner_id", "photos", ["owner_id"])
    op.create_foreign_key(
        "fk_photos_owner_id_users",
        "photos",
        "users",
        ["owner_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_photos_owner_id_users", "photos", type_="foreignkey")
    op.drop_index("ix_photos_owner_id", table_name="photos")
    op.drop_column("photos", "owner_id")
