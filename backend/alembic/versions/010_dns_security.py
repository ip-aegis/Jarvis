"""Add DNS security tables

Revision ID: 010_dns_security
Revises: 009_journal_fact_extractions
Create Date: 2026-01-13

"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "010_dns_security"
down_revision: Union[str, None] = "009_journal_fact_extractions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ==========================================================================
    # DNS Configuration Table
    # ==========================================================================

    op.create_table(
        "dns_config",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=True, default=True),
        # Upstream DNS
        sa.Column("upstream_dns", sa.JSON(), nullable=True),
        sa.Column("bootstrap_dns", sa.JSON(), nullable=True),
        # Features
        sa.Column("dnssec_enabled", sa.Boolean(), nullable=True, default=True),
        sa.Column("doh_enabled", sa.Boolean(), nullable=True, default=True),
        sa.Column("dot_enabled", sa.Boolean(), nullable=True, default=True),
        # Filtering
        sa.Column("filtering_enabled", sa.Boolean(), nullable=True, default=True),
        sa.Column("safe_browsing", sa.Boolean(), nullable=True, default=True),
        sa.Column("parental_control", sa.Boolean(), nullable=True, default=False),
        # Caching
        sa.Column("cache_size", sa.Integer(), nullable=True, default=4194304),
        sa.Column("cache_ttl_min", sa.Integer(), nullable=True, default=60),
        sa.Column("cache_ttl_max", sa.Integer(), nullable=True, default=86400),
        # Timestamps
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_dns_config_id"), "dns_config", ["id"], unique=False)

    # ==========================================================================
    # DNS Blocklists Table
    # ==========================================================================

    op.create_table(
        "dns_blocklists",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("url", sa.String(length=512), nullable=False),
        sa.Column("category", sa.String(length=50), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=True, default=True),
        sa.Column("rules_count", sa.Integer(), nullable=True, default=0),
        sa.Column("last_updated", sa.DateTime(), nullable=True),
        sa.Column("update_frequency_hours", sa.Integer(), nullable=True, default=24),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_dns_blocklists_id"), "dns_blocklists", ["id"], unique=False)
    op.create_unique_constraint("uq_dns_blocklists_url", "dns_blocklists", ["url"])

    # ==========================================================================
    # DNS Custom Rules Table
    # ==========================================================================

    op.create_table(
        "dns_custom_rules",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("rule_type", sa.String(length=20), nullable=False),
        sa.Column("domain", sa.String(length=255), nullable=False),
        sa.Column("answer", sa.String(length=255), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=True, default=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("created_by", sa.String(length=255), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_dns_custom_rules_id"), "dns_custom_rules", ["id"], unique=False)
    op.create_index(
        op.f("ix_dns_custom_rules_domain"), "dns_custom_rules", ["domain"], unique=False
    )

    # ==========================================================================
    # DNS Clients Table
    # ==========================================================================

    op.create_table(
        "dns_clients",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("client_id", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("ip_addresses", sa.JSON(), nullable=True),
        sa.Column("mac_address", sa.String(length=17), nullable=True),
        # Per-client settings
        sa.Column("use_global_settings", sa.Boolean(), nullable=True, default=True),
        sa.Column("filtering_enabled", sa.Boolean(), nullable=True, default=True),
        sa.Column("safe_browsing", sa.Boolean(), nullable=True),
        sa.Column("parental_control", sa.Boolean(), nullable=True),
        sa.Column("blocked_services", sa.JSON(), nullable=True),
        sa.Column("custom_upstream", sa.JSON(), nullable=True),
        # Statistics
        sa.Column("queries_count", sa.BigInteger(), nullable=True, default=0),
        sa.Column("blocked_count", sa.BigInteger(), nullable=True, default=0),
        sa.Column("last_seen", sa.DateTime(), nullable=True),
        # Timestamps
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_dns_clients_id"), "dns_clients", ["id"], unique=False)
    op.create_unique_constraint("uq_dns_clients_client_id", "dns_clients", ["client_id"])

    # ==========================================================================
    # DNS Query Log Table (Time-series)
    # ==========================================================================

    op.create_table(
        "dns_query_log",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        # Query details
        sa.Column("client_ip", sa.String(length=45), nullable=False),
        sa.Column("client_name", sa.String(length=255), nullable=True),
        sa.Column("domain", sa.String(length=255), nullable=False),
        sa.Column("query_type", sa.String(length=10), nullable=True),
        # Response
        sa.Column("response_code", sa.String(length=20), nullable=True),
        sa.Column("response_ip", sa.String(length=45), nullable=True),
        sa.Column("answer", sa.Text(), nullable=True),
        # Classification
        sa.Column("status", sa.String(length=20), nullable=True),
        sa.Column("block_reason", sa.String(length=100), nullable=True),
        sa.Column("blocklist_id", sa.Integer(), sa.ForeignKey("dns_blocklists.id"), nullable=True),
        # Performance
        sa.Column("upstream", sa.String(length=255), nullable=True),
        sa.Column("response_time_ms", sa.Float(), nullable=True),
        sa.Column("cached", sa.Boolean(), nullable=True, default=False),
        # Security indicators
        sa.Column("is_encrypted", sa.Boolean(), nullable=True),
        sa.Column("dnssec_validated", sa.Boolean(), nullable=True),
        # Composite primary key required for TimescaleDB hypertable
        sa.PrimaryKeyConstraint("id", "timestamp"),
    )
    op.create_index(
        op.f("ix_dns_query_log_timestamp"), "dns_query_log", ["timestamp"], unique=False
    )
    op.create_index(
        op.f("ix_dns_query_log_client_ip"), "dns_query_log", ["client_ip"], unique=False
    )
    op.create_index(op.f("ix_dns_query_log_domain"), "dns_query_log", ["domain"], unique=False)
    op.create_index(op.f("ix_dns_query_log_status"), "dns_query_log", ["status"], unique=False)
    op.create_index(
        "ix_dns_query_log_timestamp_client",
        "dns_query_log",
        ["timestamp", "client_ip"],
        unique=False,
    )

    # Convert to TimescaleDB hypertable for efficient time-series queries
    op.execute("SELECT create_hypertable('dns_query_log', 'timestamp', if_not_exists => TRUE)")

    # ==========================================================================
    # DNS Stats Table (Aggregated)
    # ==========================================================================

    op.create_table(
        "dns_stats",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.Column("period", sa.String(length=10), nullable=True),
        # Counts
        sa.Column("total_queries", sa.BigInteger(), nullable=True, default=0),
        sa.Column("blocked_queries", sa.BigInteger(), nullable=True, default=0),
        sa.Column("cached_queries", sa.BigInteger(), nullable=True, default=0),
        # Performance
        sa.Column("avg_response_time", sa.Float(), nullable=True),
        # Top lists (JSON)
        sa.Column("top_domains", sa.JSON(), nullable=True),
        sa.Column("top_blocked", sa.JSON(), nullable=True),
        sa.Column("top_clients", sa.JSON(), nullable=True),
        # Category breakdown
        sa.Column("block_by_category", sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_dns_stats_id"), "dns_stats", ["id"], unique=False)
    op.create_index(op.f("ix_dns_stats_timestamp"), "dns_stats", ["timestamp"], unique=False)
    op.create_index(
        "ix_dns_stats_timestamp_period",
        "dns_stats",
        ["timestamp", "period"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_table("dns_stats")
    op.drop_table("dns_query_log")
    op.drop_table("dns_clients")
    op.drop_table("dns_custom_rules")
    op.drop_table("dns_blocklists")
    op.drop_table("dns_config")
