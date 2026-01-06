"""Add work user profile table

Revision ID: 007_work_user_profile
Revises: 006_user_settings
Create Date: 2026-01-05

"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "007_work_user_profile"
down_revision: Union[str, None] = "006_user_settings"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "work_user_profile",
        sa.Column("id", sa.Integer(), nullable=False),
        # Core identity
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column("role", sa.String(255), nullable=True),
        sa.Column("company", sa.String(255), nullable=True),
        sa.Column("department", sa.String(255), nullable=True),
        # Rich context
        sa.Column("responsibilities", JSON, nullable=True),
        sa.Column("expertise_areas", JSON, nullable=True),
        sa.Column("goals", JSON, nullable=True),
        sa.Column("working_style", sa.Text(), nullable=True),
        sa.Column("key_relationships", JSON, nullable=True),
        sa.Column("communication_prefs", sa.Text(), nullable=True),
        sa.Column("current_priorities", JSON, nullable=True),
        # Learning metadata
        sa.Column("learned_facts", JSON, nullable=True, default=[]),
        sa.Column("last_learned_at", sa.DateTime(), nullable=True),
        # Timestamps
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_work_user_profile_id"), "work_user_profile", ["id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_work_user_profile_id"), table_name="work_user_profile")
    op.drop_table("work_user_profile")
