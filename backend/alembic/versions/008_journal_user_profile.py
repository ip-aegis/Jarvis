"""Add journal user profile table

Revision ID: 008_journal_user_profile
Revises: 007_work_user_profile
Create Date: 2026-01-09

"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "008_journal_user_profile"
down_revision: Union[str, None] = "007_work_user_profile"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "journal_user_profile",
        sa.Column("id", sa.Integer(), nullable=False),
        # Core identity
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column("nickname", sa.String(255), nullable=True),
        # Life context
        sa.Column("life_context", JSON, nullable=True),
        sa.Column("interests", JSON, nullable=True),
        sa.Column("goals", JSON, nullable=True),
        sa.Column("challenges", JSON, nullable=True),
        sa.Column("values", JSON, nullable=True),
        sa.Column("communication_style", sa.Text(), nullable=True),
        # Learning metadata
        sa.Column("learned_facts", JSON, nullable=True, default=[]),
        sa.Column("last_learned_at", sa.DateTime(), nullable=True),
        # Timestamps
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_journal_user_profile_id"), "journal_user_profile", ["id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_journal_user_profile_id"), table_name="journal_user_profile")
    op.drop_table("journal_user_profile")
