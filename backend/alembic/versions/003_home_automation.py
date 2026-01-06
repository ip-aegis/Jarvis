"""Add home automation tables

Revision ID: 003_home_automation
Revises: 002_network_actions
Create Date: 2026-01-04

"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "003_home_automation"
down_revision: Union[str, None] = "002_network_actions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ==========================================================================
    # Home Automation Tables
    # ==========================================================================

    # Create home_devices table
    op.create_table(
        "home_devices",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("device_id", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        # Device classification
        sa.Column("device_type", sa.String(length=50), nullable=False),
        sa.Column("platform", sa.String(length=50), nullable=False),
        sa.Column("model", sa.String(length=255), nullable=True),
        sa.Column("firmware_version", sa.String(length=100), nullable=True),
        # Location/grouping
        sa.Column("room", sa.String(length=100), nullable=True),
        sa.Column("zone", sa.String(length=100), nullable=True),
        # Connection status
        sa.Column("status", sa.String(length=20), nullable=True, default="offline"),
        sa.Column("last_seen", sa.DateTime(), nullable=True),
        # Device capabilities and state
        sa.Column("capabilities", sa.JSON(), nullable=True),
        sa.Column("state", sa.JSON(), nullable=True),
        sa.Column("config", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_home_devices_id"), "home_devices", ["id"], unique=False)
    op.create_index(op.f("ix_home_devices_device_id"), "home_devices", ["device_id"], unique=True)
    op.create_index("ix_home_devices_platform", "home_devices", ["platform"], unique=False)
    op.create_index("ix_home_devices_device_type", "home_devices", ["device_type"], unique=False)

    # Create home_device_credentials table
    op.create_table(
        "home_device_credentials",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("device_id", sa.Integer(), nullable=False),
        sa.Column("platform", sa.String(length=50), nullable=False),
        # OAuth tokens
        sa.Column("access_token", sa.Text(), nullable=True),
        sa.Column("refresh_token", sa.Text(), nullable=True),
        sa.Column("token_expires_at", sa.DateTime(), nullable=True),
        # API keys/credentials
        sa.Column("api_key", sa.Text(), nullable=True),
        sa.Column("client_id", sa.String(length=255), nullable=True),
        sa.Column("client_secret", sa.Text(), nullable=True),
        # Platform-specific auth data
        sa.Column("auth_data", sa.JSON(), nullable=True),
        # Token refresh tracking
        sa.Column("last_refresh", sa.DateTime(), nullable=True),
        sa.Column("refresh_failures", sa.Integer(), nullable=True, default=0),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["device_id"], ["home_devices.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_home_device_credentials_id"), "home_device_credentials", ["id"], unique=False
    )
    op.create_unique_constraint(
        "uq_home_device_credentials_device_id", "home_device_credentials", ["device_id"]
    )

    # Create home_events table
    op.create_table(
        "home_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("device_id", sa.Integer(), nullable=False),
        sa.Column("event_id", postgresql.UUID(as_uuid=True), nullable=False),
        # Event classification
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=True, default="info"),
        # Event data
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("data", sa.JSON(), nullable=True),
        # Media attachments
        sa.Column("media_url", sa.String(length=512), nullable=True),
        sa.Column("thumbnail_url", sa.String(length=512), nullable=True),
        # Timestamps
        sa.Column("occurred_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        # Processing status
        sa.Column("acknowledged", sa.Boolean(), nullable=True, default=False),
        sa.Column("acknowledged_at", sa.DateTime(), nullable=True),
        sa.Column("acknowledged_by", sa.String(length=255), nullable=True),
        # Automation trigger tracking
        sa.Column("triggered_automations", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(["device_id"], ["home_devices.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_home_events_id"), "home_events", ["id"], unique=False)
    op.create_index(op.f("ix_home_events_event_id"), "home_events", ["event_id"], unique=True)
    op.create_index(
        op.f("ix_home_events_occurred_at"), "home_events", ["occurred_at"], unique=False
    )
    op.create_index(
        "ix_home_events_device_type", "home_events", ["device_id", "event_type"], unique=False
    )

    # Create home_automations table
    op.create_table(
        "home_automations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("automation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        # Trigger configuration
        sa.Column("trigger_type", sa.String(length=50), nullable=False),
        sa.Column("trigger_config", sa.JSON(), nullable=False),
        # Conditions
        sa.Column("conditions", sa.JSON(), nullable=True),
        # Actions
        sa.Column("actions", sa.JSON(), nullable=False),
        # Execution settings
        sa.Column("enabled", sa.Boolean(), nullable=True, default=True),
        sa.Column("cooldown_seconds", sa.Integer(), nullable=True, default=0),
        sa.Column("last_triggered", sa.DateTime(), nullable=True),
        # Metadata
        sa.Column("created_by", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        # Statistics
        sa.Column("trigger_count", sa.Integer(), nullable=True, default=0),
        sa.Column("last_result", sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_home_automations_id"), "home_automations", ["id"], unique=False)
    op.create_index(
        op.f("ix_home_automations_automation_id"),
        "home_automations",
        ["automation_id"],
        unique=True,
    )

    # Create home_platform_credentials table (platform-level auth like Ring account)
    op.create_table(
        "home_platform_credentials",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("platform", sa.String(length=50), nullable=False),
        # OAuth tokens
        sa.Column("access_token", sa.Text(), nullable=True),
        sa.Column("refresh_token", sa.Text(), nullable=True),
        sa.Column("token_expires_at", sa.DateTime(), nullable=True),
        # API keys/credentials
        sa.Column("api_key", sa.Text(), nullable=True),
        sa.Column("client_id", sa.String(length=255), nullable=True),
        sa.Column("client_secret", sa.Text(), nullable=True),
        # Platform-specific auth data
        sa.Column("auth_data", sa.JSON(), nullable=True),
        # Status
        sa.Column("connected", sa.Boolean(), nullable=True, default=False),
        sa.Column("last_refresh", sa.DateTime(), nullable=True),
        sa.Column("refresh_failures", sa.Integer(), nullable=True, default=0),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_home_platform_credentials_id"), "home_platform_credentials", ["id"], unique=False
    )
    op.create_unique_constraint(
        "uq_home_platform_credentials_platform", "home_platform_credentials", ["platform"]
    )


def downgrade() -> None:
    op.drop_table("home_platform_credentials")
    op.drop_table("home_automations")
    op.drop_table("home_events")
    op.drop_table("home_device_credentials")
    op.drop_table("home_devices")
