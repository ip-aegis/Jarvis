"""Initial schema

Revision ID: 001_initial
Revises:
Create Date: 2026-01-02

"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create servers table
    op.create_table(
        "servers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("hostname", sa.String(length=255), nullable=False),
        sa.Column("ip_address", sa.String(length=45), nullable=False),
        sa.Column("port", sa.Integer(), nullable=True, default=22),
        sa.Column("username", sa.String(length=255), nullable=False),
        sa.Column("ssh_key_path", sa.String(length=512), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=True, default="pending"),
        sa.Column("os_info", sa.Text(), nullable=True),
        sa.Column("cpu_info", sa.String(length=255), nullable=True),
        sa.Column("cpu_cores", sa.Integer(), nullable=True),
        sa.Column("memory_total", sa.String(length=50), nullable=True),
        sa.Column("disk_total", sa.String(length=50), nullable=True),
        sa.Column("gpu_info", sa.String(length=255), nullable=True),
        sa.Column("agent_installed", sa.Boolean(), nullable=True, default=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_servers_id"), "servers", ["id"], unique=False)
    op.create_unique_constraint("uq_servers_ip_address", "servers", ["ip_address"])

    # Create metrics table
    op.create_table(
        "metrics",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("server_id", sa.Integer(), nullable=False),
        sa.Column("timestamp", sa.DateTime(), nullable=True),
        sa.Column("cpu_usage", sa.Float(), nullable=True),
        sa.Column("cpu_per_core", sa.JSON(), nullable=True),
        sa.Column("memory_used", sa.Float(), nullable=True),
        sa.Column("memory_total", sa.Float(), nullable=True),
        sa.Column("memory_percent", sa.Float(), nullable=True),
        sa.Column("memory_available", sa.Float(), nullable=True),
        sa.Column("memory_buffers", sa.Float(), nullable=True),
        sa.Column("memory_cached", sa.Float(), nullable=True),
        sa.Column("swap_used", sa.Float(), nullable=True),
        sa.Column("swap_total", sa.Float(), nullable=True),
        sa.Column("disk_used", sa.Float(), nullable=True),
        sa.Column("disk_total", sa.Float(), nullable=True),
        sa.Column("disk_percent", sa.Float(), nullable=True),
        sa.Column("gpu_utilization", sa.Float(), nullable=True),
        sa.Column("gpu_memory_used", sa.Float(), nullable=True),
        sa.Column("gpu_memory_total", sa.Float(), nullable=True),
        sa.Column("gpu_memory_percent", sa.Float(), nullable=True),
        sa.Column("gpu_temperature", sa.Float(), nullable=True),
        sa.Column("gpu_power", sa.Float(), nullable=True),
        sa.Column("load_avg_1m", sa.Float(), nullable=True),
        sa.Column("load_avg_5m", sa.Float(), nullable=True),
        sa.Column("load_avg_15m", sa.Float(), nullable=True),
        sa.Column("temperatures", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(["server_id"], ["servers.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_metrics_id"), "metrics", ["id"], unique=False)
    op.create_index(op.f("ix_metrics_timestamp"), "metrics", ["timestamp"], unique=False)

    # Create projects table
    op.create_table(
        "projects",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("server_id", sa.Integer(), nullable=False),
        sa.Column("path", sa.String(length=512), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("tech_stack", sa.JSON(), nullable=True),
        sa.Column("urls", sa.JSON(), nullable=True),
        sa.Column("ips", sa.JSON(), nullable=True),
        sa.Column("last_scanned", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["server_id"], ["servers.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_projects_id"), "projects", ["id"], unique=False)

    # Create chat_sessions table
    op.create_table(
        "chat_sessions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.String(length=255), nullable=False),
        sa.Column("context", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_chat_sessions_id"), "chat_sessions", ["id"], unique=False)
    op.create_index(
        op.f("ix_chat_sessions_session_id"), "chat_sessions", ["session_id"], unique=True
    )

    # Create chat_messages table
    op.create_table(
        "chat_messages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("tool_calls", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["session_id"], ["chat_sessions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_chat_messages_id"), "chat_messages", ["id"], unique=False)


def downgrade() -> None:
    op.drop_table("chat_messages")
    op.drop_table("chat_sessions")
    op.drop_table("projects")
    op.drop_table("metrics")
    op.drop_table("servers")
