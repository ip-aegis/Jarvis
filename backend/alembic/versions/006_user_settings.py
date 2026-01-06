"""Add user settings table

Revision ID: 006_user_settings
Revises: 005_work_notes_feature
Create Date: 2026-01-05

"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "006_user_settings"
down_revision: Union[str, None] = "005_work_notes_feature"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_user_settings_key"), "user_settings", ["key"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_user_settings_key"), table_name="user_settings")
    op.drop_table("user_settings")
