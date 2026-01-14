"""Fix LLM usage cost precision by changing cost_cents to Float

The cost_cents column was Integer which caused small costs (embeddings, cheap models)
to round down to 0. This migration changes it to Float for proper precision.

Revision ID: 013_fix_llm_usage_cost_precision
Revises: 012_llm_usage_tracking
Create Date: 2026-01-14

"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "013_fix_llm_usage_cost_precision"
down_revision: Union[str, None] = "012_llm_usage_tracking"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Change cost_cents from Integer to Float in llm_usage_log
    op.alter_column(
        "llm_usage_log",
        "cost_cents",
        existing_type=sa.Integer(),
        type_=sa.Float(),
        existing_nullable=False,
    )

    # Change total_cost_cents from BigInteger to Float in llm_usage_stats
    op.alter_column(
        "llm_usage_stats",
        "total_cost_cents",
        existing_type=sa.BigInteger(),
        type_=sa.Float(),
        existing_nullable=True,
    )


def downgrade() -> None:
    # Revert to Integer (will lose precision)
    op.alter_column(
        "llm_usage_log",
        "cost_cents",
        existing_type=sa.Float(),
        type_=sa.Integer(),
        existing_nullable=False,
    )

    op.alter_column(
        "llm_usage_stats",
        "total_cost_cents",
        existing_type=sa.Float(),
        type_=sa.BigInteger(),
        existing_nullable=True,
    )
