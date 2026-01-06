"""Add journal tables with pgvector embeddings

Revision ID: 004_journal_feature
Revises: 003_home_automation
Create Date: 2026-01-05

"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "004_journal_feature"
down_revision: Union[str, None] = "003_home_automation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ==========================================================================
    # Enable pgvector extension for embeddings
    # ==========================================================================
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # ==========================================================================
    # Journal Entries Table
    # ==========================================================================
    op.create_table(
        "journal_entries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("entry_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        # Emotional state tracking
        sa.Column(
            "mood", sa.String(length=50), nullable=True
        ),  # happy, neutral, sad, anxious, excited, etc.
        sa.Column("energy_level", sa.Integer(), nullable=True),  # 1-5 scale
        # Tags for categorization
        sa.Column("tags", sa.JSON(), nullable=True),  # ['work', 'family', 'health']
        # Source tracking
        sa.Column(
            "source", sa.String(length=50), nullable=True, server_default="manual"
        ),  # manual, chat_summary
        sa.Column(
            "source_session_id", sa.String(length=255), nullable=True
        ),  # If from chat summary
        # Timestamps
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("energy_level >= 1 AND energy_level <= 5", name="ck_energy_level_range"),
    )
    op.create_index(op.f("ix_journal_entries_id"), "journal_entries", ["id"], unique=False)
    op.create_index(
        op.f("ix_journal_entries_entry_id"), "journal_entries", ["entry_id"], unique=True
    )
    op.create_index(op.f("ix_journal_entries_date"), "journal_entries", ["date"], unique=False)

    # Add vector column for embeddings (1536 dimensions for OpenAI text-embedding-3-small)
    op.execute("ALTER TABLE journal_entries ADD COLUMN embedding vector(1536)")

    # Create IVFFlat index for approximate nearest neighbor search
    # Note: This index works best with at least 1000 rows; for smaller datasets, use exact search
    op.execute(
        """
        CREATE INDEX ix_journal_entries_embedding
        ON journal_entries
        USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100)
    """
    )

    # ==========================================================================
    # Journal Chat Summaries Table
    # ==========================================================================
    op.create_table(
        "journal_chat_summaries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("summary_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chat_session_id", sa.Integer(), nullable=True),  # Reference to chat_sessions
        sa.Column("journal_entry_id", sa.Integer(), nullable=True),  # Created entry after approval
        # Summary content
        sa.Column("summary_text", sa.Text(), nullable=False),
        sa.Column(
            "key_topics", sa.JSON(), nullable=True
        ),  # ['work stress', 'family dinner', 'exercise']
        sa.Column(
            "sentiment", sa.String(length=50), nullable=True
        ),  # positive, negative, neutral, mixed
        # Generation metadata
        sa.Column("model_used", sa.String(length=100), nullable=True),
        sa.Column("tokens_used", sa.Integer(), nullable=True),
        # Approval workflow
        sa.Column(
            "status", sa.String(length=50), nullable=True, server_default="generated"
        ),  # generated, approved, rejected
        # Timestamps
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["chat_session_id"], ["chat_sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["journal_entry_id"], ["journal_entries.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_journal_chat_summaries_id"), "journal_chat_summaries", ["id"], unique=False
    )
    op.create_index(
        op.f("ix_journal_chat_summaries_summary_id"),
        "journal_chat_summaries",
        ["summary_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_journal_chat_summaries_status"), "journal_chat_summaries", ["status"], unique=False
    )


def downgrade() -> None:
    op.drop_table("journal_chat_summaries")
    op.drop_table("journal_entries")
    op.execute("DROP EXTENSION IF EXISTS vector")
