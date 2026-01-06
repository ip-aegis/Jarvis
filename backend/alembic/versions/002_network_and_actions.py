"""Add network devices and action system tables

Revision ID: 002_network_actions
Revises: 001_initial
Create Date: 2026-01-02

"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "002_network_actions"
down_revision: Union[str, None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ==========================================================================
    # Network Device Tables
    # ==========================================================================

    # Create network_devices table
    op.create_table(
        "network_devices",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("ip_address", sa.String(length=45), nullable=False),
        sa.Column("mac_address", sa.String(length=17), nullable=True),
        # Device classification
        sa.Column("device_type", sa.String(length=50), nullable=False),
        sa.Column("vendor", sa.String(length=50), nullable=True),
        sa.Column("model", sa.String(length=100), nullable=True),
        sa.Column("firmware_version", sa.String(length=100), nullable=True),
        # Connection configuration
        sa.Column("connection_type", sa.String(length=20), nullable=False),
        sa.Column("snmp_community", sa.String(length=100), nullable=True),
        sa.Column("snmp_version", sa.String(length=10), nullable=True, default="2c"),
        sa.Column("snmp_v3_config", sa.JSON(), nullable=True),
        sa.Column("api_url", sa.String(length=255), nullable=True),
        sa.Column("api_credentials", sa.JSON(), nullable=True),
        sa.Column("ssh_username", sa.String(length=100), nullable=True),
        sa.Column("ssh_key_path", sa.String(length=512), nullable=True),
        # Device info
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("port_count", sa.Integer(), nullable=True),
        sa.Column("uplink_ports", sa.JSON(), nullable=True),
        sa.Column("poe_capable", sa.Boolean(), nullable=True, default=False),
        sa.Column("management_vlan", sa.Integer(), nullable=True),
        # Status
        sa.Column("status", sa.String(length=20), nullable=True, default="pending"),
        sa.Column("last_seen", sa.DateTime(), nullable=True),
        sa.Column("uptime_seconds", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_network_devices_id"), "network_devices", ["id"], unique=False)
    op.create_unique_constraint("uq_network_devices_ip_address", "network_devices", ["ip_address"])

    # Create network_ports table
    op.create_table(
        "network_ports",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("device_id", sa.Integer(), nullable=False),
        sa.Column("port_number", sa.Integer(), nullable=False),
        sa.Column("port_name", sa.String(length=50), nullable=True),
        sa.Column("if_index", sa.Integer(), nullable=True),
        # Port configuration
        sa.Column("enabled", sa.Boolean(), nullable=True, default=True),
        sa.Column("speed", sa.String(length=20), nullable=True),
        sa.Column("duplex", sa.String(length=10), nullable=True),
        sa.Column("vlan_id", sa.Integer(), nullable=True),
        sa.Column("vlan_name", sa.String(length=100), nullable=True),
        sa.Column("port_type", sa.String(length=20), nullable=True),
        sa.Column("allowed_vlans", sa.JSON(), nullable=True),
        # PoE
        sa.Column("poe_enabled", sa.Boolean(), nullable=True, default=False),
        sa.Column("poe_power", sa.Float(), nullable=True),
        sa.Column("poe_max_power", sa.Float(), nullable=True),
        # Status
        sa.Column("link_status", sa.String(length=10), nullable=True),
        sa.Column("admin_status", sa.String(length=10), nullable=True),
        # Connected device
        sa.Column("connected_mac", sa.String(length=17), nullable=True),
        sa.Column("connected_device", sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(["device_id"], ["network_devices.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_network_ports_id"), "network_ports", ["id"], unique=False)
    op.create_index(
        "ix_network_ports_device_port", "network_ports", ["device_id", "port_number"], unique=True
    )

    # Create network_metrics table
    op.create_table(
        "network_metrics",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("device_id", sa.Integer(), nullable=False),
        sa.Column("timestamp", sa.DateTime(), nullable=True),
        # System metrics
        sa.Column("cpu_usage", sa.Float(), nullable=True),
        sa.Column("memory_usage", sa.Float(), nullable=True),
        sa.Column("memory_total", sa.BigInteger(), nullable=True),
        sa.Column("temperature", sa.Float(), nullable=True),
        sa.Column("uptime_seconds", sa.Integer(), nullable=True),
        # Aggregate traffic
        sa.Column("total_rx_bytes", sa.BigInteger(), nullable=True),
        sa.Column("total_tx_bytes", sa.BigInteger(), nullable=True),
        sa.Column("total_rx_packets", sa.BigInteger(), nullable=True),
        sa.Column("total_tx_packets", sa.BigInteger(), nullable=True),
        # Error counters
        sa.Column("total_errors", sa.Integer(), nullable=True),
        sa.Column("total_drops", sa.Integer(), nullable=True),
        sa.Column("total_collisions", sa.Integer(), nullable=True),
        # Per-port metrics
        sa.Column("port_metrics", sa.JSON(), nullable=True),
        # WiFi metrics
        sa.Column("wifi_clients", sa.Integer(), nullable=True),
        sa.Column("wifi_channel", sa.Integer(), nullable=True),
        sa.Column("wifi_channel_width", sa.Integer(), nullable=True),
        sa.Column("wifi_noise", sa.Float(), nullable=True),
        sa.Column("wifi_utilization", sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(["device_id"], ["network_devices.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_network_metrics_id"), "network_metrics", ["id"], unique=False)
    op.create_index(
        op.f("ix_network_metrics_timestamp"), "network_metrics", ["timestamp"], unique=False
    )
    op.create_index(
        "ix_network_metrics_device_timestamp",
        "network_metrics",
        ["device_id", "timestamp"],
        unique=False,
    )

    # Create wifi_clients table
    op.create_table(
        "wifi_clients",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("device_id", sa.Integer(), nullable=False),
        sa.Column("mac_address", sa.String(length=17), nullable=False),
        sa.Column("hostname", sa.String(length=255), nullable=True),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        # Connection info
        sa.Column("ssid", sa.String(length=100), nullable=True),
        sa.Column("bssid", sa.String(length=17), nullable=True),
        sa.Column("band", sa.String(length=10), nullable=True),
        sa.Column("channel", sa.Integer(), nullable=True),
        sa.Column("signal_strength", sa.Integer(), nullable=True),
        sa.Column("noise", sa.Integer(), nullable=True),
        sa.Column("snr", sa.Integer(), nullable=True),
        sa.Column("tx_rate", sa.Integer(), nullable=True),
        sa.Column("rx_rate", sa.Integer(), nullable=True),
        # Session info
        sa.Column("connected_at", sa.DateTime(), nullable=True),
        sa.Column("last_seen", sa.DateTime(), nullable=True),
        sa.Column("rx_bytes", sa.BigInteger(), nullable=True, default=0),
        sa.Column("tx_bytes", sa.BigInteger(), nullable=True, default=0),
        # Authentication
        sa.Column("auth_type", sa.String(length=50), nullable=True),
        sa.Column("is_authorized", sa.Boolean(), nullable=True, default=True),
        sa.Column("is_blocked", sa.Boolean(), nullable=True, default=False),
        sa.ForeignKeyConstraint(["device_id"], ["network_devices.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_wifi_clients_id"), "wifi_clients", ["id"], unique=False)
    op.create_index(
        "ix_wifi_clients_device_mac", "wifi_clients", ["device_id", "mac_address"], unique=False
    )

    # ==========================================================================
    # Action System Tables
    # ==========================================================================

    # Create action_audit table
    op.create_table(
        "action_audit",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("action_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("action_name", sa.String(length=255), nullable=False),
        sa.Column("action_type", sa.String(length=50), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=True),
        # Action details
        sa.Column("parameters", sa.JSON(), nullable=True),
        sa.Column("target_type", sa.String(length=50), nullable=True),
        sa.Column("target_id", sa.Integer(), nullable=True),
        sa.Column("target_name", sa.String(length=255), nullable=True),
        # Initiator
        sa.Column("initiated_by", sa.String(length=255), nullable=True),
        sa.Column("session_id", sa.String(length=255), nullable=True),
        sa.Column("natural_language_input", sa.Text(), nullable=True),
        sa.Column("llm_interpretation", sa.Text(), nullable=True),
        # Timing
        sa.Column("initiated_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        # Status and result
        sa.Column("status", sa.String(length=50), nullable=True, default="pending"),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        # Confirmation
        sa.Column("confirmation_required", sa.Boolean(), nullable=True, default=False),
        sa.Column("confirmed_by", sa.String(length=255), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(), nullable=True),
        # Rollback
        sa.Column("rollback_available", sa.Boolean(), nullable=True, default=False),
        sa.Column("rollback_executed", sa.Boolean(), nullable=True, default=False),
        sa.Column("rollback_at", sa.DateTime(), nullable=True),
        sa.Column("rollback_result", sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_action_audit_id"), "action_audit", ["id"], unique=False)
    op.create_index(op.f("ix_action_audit_action_id"), "action_audit", ["action_id"], unique=True)
    op.create_index(
        op.f("ix_action_audit_action_name"), "action_audit", ["action_name"], unique=False
    )
    op.create_index(
        op.f("ix_action_audit_initiated_at"), "action_audit", ["initiated_at"], unique=False
    )

    # Create pending_confirmations table
    op.create_table(
        "pending_confirmations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("action_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("confirmation_prompt", sa.Text(), nullable=False),
        sa.Column("risk_summary", sa.Text(), nullable=True),
        sa.Column("affected_resources", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["action_id"], ["action_audit.action_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_pending_confirmations_id"), "pending_confirmations", ["id"], unique=False
    )
    op.create_unique_constraint(
        "uq_pending_confirmations_action_id", "pending_confirmations", ["action_id"]
    )

    # Create scheduled_actions table
    op.create_table(
        "scheduled_actions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("action_name", sa.String(length=255), nullable=False),
        sa.Column("parameters", sa.JSON(), nullable=True),
        # Schedule configuration
        sa.Column("schedule_type", sa.String(length=50), nullable=False),
        sa.Column("schedule_config", sa.JSON(), nullable=True),
        # Conditional action fields
        sa.Column("condition_expression", sa.Text(), nullable=True),
        sa.Column("condition_metric", sa.String(length=100), nullable=True),
        sa.Column("condition_operator", sa.String(length=10), nullable=True),
        sa.Column("condition_threshold", sa.Float(), nullable=True),
        sa.Column("condition_duration_seconds", sa.Integer(), nullable=True),
        sa.Column("last_condition_check", sa.DateTime(), nullable=True),
        sa.Column("condition_met_since", sa.DateTime(), nullable=True),
        # Metadata
        sa.Column("created_by", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        # Execution tracking
        sa.Column("next_run", sa.DateTime(), nullable=True),
        sa.Column("last_run", sa.DateTime(), nullable=True),
        sa.Column("last_result", sa.JSON(), nullable=True),
        sa.Column("run_count", sa.Integer(), nullable=True, default=0),
        sa.Column("error_count", sa.Integer(), nullable=True, default=0),
        # Status
        sa.Column("status", sa.String(length=50), nullable=True, default="active"),
        sa.Column("enabled", sa.Boolean(), nullable=True, default=True),
        sa.Column("max_runs", sa.Integer(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_scheduled_actions_id"), "scheduled_actions", ["id"], unique=False)
    op.create_index(
        op.f("ix_scheduled_actions_job_id"), "scheduled_actions", ["job_id"], unique=True
    )


def downgrade() -> None:
    op.drop_table("scheduled_actions")
    op.drop_table("pending_confirmations")
    op.drop_table("action_audit")
    op.drop_table("wifi_clients")
    op.drop_table("network_metrics")
    op.drop_table("network_ports")
    op.drop_table("network_devices")
