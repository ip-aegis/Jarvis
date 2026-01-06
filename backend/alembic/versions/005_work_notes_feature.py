"""Add work notes tables with pgvector embeddings

Revision ID: 005_work_notes_feature
Revises: 004_journal_feature
Create Date: 2026-01-05

"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "005_work_notes_feature"
down_revision: Union[str, None] = "004_journal_feature"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ==========================================================================
    # Work Accounts Table
    # ==========================================================================
    op.create_table(
        "work_accounts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("normalized_name", sa.String(length=255), nullable=False),
        # Semi-structured data
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("contacts", sa.JSON(), nullable=True),  # [{"name": "John", "role": "CTO", ...}]
        sa.Column("extra_data", sa.JSON(), nullable=True),  # {"industry": "mining", ...}
        # Status
        sa.Column("status", sa.String(length=50), nullable=True, server_default="active"),
        # Aliases for fuzzy matching
        sa.Column("aliases", sa.JSON(), nullable=True),  # ["Covia Holdings", "Covia Corp"]
        # Timestamps
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_work_accounts_id"), "work_accounts", ["id"], unique=False)
    op.create_index(
        op.f("ix_work_accounts_account_id"), "work_accounts", ["account_id"], unique=True
    )
    op.create_index(op.f("ix_work_accounts_name"), "work_accounts", ["name"], unique=False)
    op.create_index(
        op.f("ix_work_accounts_normalized_name"), "work_accounts", ["normalized_name"], unique=False
    )
    op.create_index(op.f("ix_work_accounts_status"), "work_accounts", ["status"], unique=False)

    # ==========================================================================
    # Work Notes Table
    # ==========================================================================
    op.create_table(
        "work_notes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("note_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        # Note content
        sa.Column("content", sa.Text(), nullable=False),
        # Activity metadata
        sa.Column(
            "activity_type", sa.String(length=50), nullable=True
        ),  # meeting, call, email, task, note, follow_up
        sa.Column("activity_date", sa.DateTime(), nullable=True),
        # Extracted entities (LLM populated)
        sa.Column("mentioned_contacts", sa.JSON(), nullable=True),  # ["John Smith", "Jane Doe"]
        sa.Column(
            "action_items", sa.JSON(), nullable=True
        ),  # [{"task": "...", "due": "...", "status": "pending"}]
        sa.Column("tags", sa.JSON(), nullable=True),  # ["proposal", "pricing"]
        # Source tracking
        sa.Column("source", sa.String(length=50), nullable=True, server_default="manual"),
        sa.Column("source_session_id", sa.String(length=255), nullable=True),
        # Timestamps
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["account_id"], ["work_accounts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_work_notes_id"), "work_notes", ["id"], unique=False)
    op.create_index(op.f("ix_work_notes_note_id"), "work_notes", ["note_id"], unique=True)
    op.create_index(op.f("ix_work_notes_account_id"), "work_notes", ["account_id"], unique=False)
    op.create_index(
        op.f("ix_work_notes_activity_date"), "work_notes", ["activity_date"], unique=False
    )
    op.create_index(
        op.f("ix_work_notes_activity_type"), "work_notes", ["activity_type"], unique=False
    )

    # Add vector column for embeddings (1536 dimensions for OpenAI text-embedding-3-small)
    op.execute("ALTER TABLE work_notes ADD COLUMN embedding vector(1536)")

    # Create IVFFlat index for approximate nearest neighbor search
    op.execute(
        """
        CREATE INDEX ix_work_notes_embedding
        ON work_notes
        USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100)
    """
    )


def downgrade() -> None:
    op.drop_table("work_notes")
    op.drop_table("work_accounts")
