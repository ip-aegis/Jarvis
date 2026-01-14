"""Add journal fact extractions table for visibility

Revision ID: 009_journal_fact_extractions
Revises: 008_journal_user_profile
Create Date: 2026-01-09

"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "009_journal_fact_extractions"
down_revision: Union[str, None] = "008_journal_user_profile"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "journal_fact_extractions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.String(255), nullable=True),
        sa.Column("extracted_at", sa.DateTime(), nullable=True),
        sa.Column("fact_text", sa.Text(), nullable=False),
        sa.Column("category", sa.String(50), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("duplicate_of", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_journal_fact_extractions_id"),
        "journal_fact_extractions",
        ["id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_journal_fact_extractions_session_id"),
        "journal_fact_extractions",
        ["session_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_journal_fact_extractions_extracted_at"),
        "journal_fact_extractions",
        ["extracted_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_journal_fact_extractions_extracted_at"),
        table_name="journal_fact_extractions",
    )
    op.drop_index(
        op.f("ix_journal_fact_extractions_session_id"),
        table_name="journal_fact_extractions",
    )
    op.drop_index(
        op.f("ix_journal_fact_extractions_id"),
        table_name="journal_fact_extractions",
    )
    op.drop_table("journal_fact_extractions")
