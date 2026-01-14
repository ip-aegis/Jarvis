"""Add LLM usage tracking tables

Revision ID: 012_llm_usage_tracking
Revises: 011_dns_analytics
Create Date: 2026-01-13

"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "012_llm_usage_tracking"
down_revision: Union[str, None] = "011_dns_analytics"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ==========================================================================
    # LLM Usage Log - Per-request tracking
    # ==========================================================================
    op.create_table(
        "llm_usage_log",
        sa.Column("id", sa.BigInteger(), nullable=False, autoincrement=True),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        # Request context
        sa.Column("feature", sa.String(length=50), nullable=False),
        sa.Column("function_name", sa.String(length=100), nullable=True),
        sa.Column("context", sa.String(length=50), nullable=True),
        sa.Column("session_id", sa.String(length=255), nullable=True),
        # Model info
        sa.Column("model", sa.String(length=100), nullable=False),
        # Token counts
        sa.Column("prompt_tokens", sa.Integer(), nullable=False),
        sa.Column("completion_tokens", sa.Integer(), nullable=False),
        sa.Column("total_tokens", sa.Integer(), nullable=False),
        # Cost in cents (for precision)
        sa.Column("cost_cents", sa.Integer(), nullable=False, default=0),
        # Optional metadata
        sa.Column("tool_calls_count", sa.Integer(), nullable=True, default=0),
        sa.Column("cached", sa.Boolean(), nullable=True, default=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_llm_usage_log_timestamp", "llm_usage_log", ["timestamp"])
    op.create_index("ix_llm_usage_log_feature", "llm_usage_log", ["feature"])
    op.create_index("ix_llm_usage_log_function_name", "llm_usage_log", ["function_name"])
    op.create_index("ix_llm_usage_log_model", "llm_usage_log", ["model"])
    op.create_index(
        "ix_llm_usage_log_timestamp_feature",
        "llm_usage_log",
        ["timestamp", "feature"],
    )

    # ==========================================================================
    # LLM Usage Stats - Aggregated statistics
    # ==========================================================================
    op.create_table(
        "llm_usage_stats",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.Column("period", sa.String(length=10), nullable=False),  # hour, day
        # Aggregation keys
        sa.Column("feature", sa.String(length=50), nullable=False),
        sa.Column("model", sa.String(length=100), nullable=True),
        # Totals
        sa.Column("request_count", sa.Integer(), nullable=True, default=0),
        sa.Column("prompt_tokens", sa.BigInteger(), nullable=True, default=0),
        sa.Column("completion_tokens", sa.BigInteger(), nullable=True, default=0),
        sa.Column("total_tokens", sa.BigInteger(), nullable=True, default=0),
        sa.Column("total_cost_cents", sa.BigInteger(), nullable=True, default=0),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_llm_usage_stats_timestamp", "llm_usage_stats", ["timestamp"])
    op.create_index("ix_llm_usage_stats_feature", "llm_usage_stats", ["feature"])
    op.create_index("ix_llm_usage_stats_period", "llm_usage_stats", ["period"])
    op.create_index(
        "ix_llm_usage_stats_timestamp_period_feature",
        "llm_usage_stats",
        ["timestamp", "period", "feature"],
    )


def downgrade() -> None:
    op.drop_table("llm_usage_stats")
    op.drop_table("llm_usage_log")
