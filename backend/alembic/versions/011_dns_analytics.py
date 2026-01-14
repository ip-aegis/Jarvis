"""Add DNS analytics tables

Revision ID: 011_dns_analytics
Revises: 010_dns_security
Create Date: 2026-01-13

"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "011_dns_analytics"
down_revision: Union[str, None] = "010_dns_security"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ==========================================================================
    # DNS Client Profile Table - Behavioral baselines per client
    # ==========================================================================

    op.create_table(
        "dns_client_profile",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "client_id",
            sa.String(length=100),
            sa.ForeignKey("dns_clients.client_id"),
            nullable=False,
        ),
        # Behavioral baselines
        sa.Column(
            "baseline_domains", sa.JSON(), nullable=True
        ),  # {"google.com": {"hourly_avg": 15, "std_dev": 3}}
        sa.Column(
            "typical_query_hours", sa.JSON(), nullable=True
        ),  # {"0": 2, "1": 1, ... "23": 45}
        sa.Column(
            "typical_query_types", sa.JSON(), nullable=True
        ),  # {"A": 85, "AAAA": 10, "MX": 5}
        sa.Column("typical_categories", sa.JSON(), nullable=True),  # {"cdn": 40, "social": 20}
        # Device inference
        sa.Column(
            "device_type_inference", sa.String(length=50), nullable=True
        ),  # desktop, mobile, iot, server
        sa.Column("device_type_confidence", sa.Float(), nullable=True),
        # Query rate statistics
        sa.Column("normal_query_rate_per_hour", sa.Float(), nullable=True),
        sa.Column("query_rate_std_dev", sa.Float(), nullable=True),
        sa.Column("max_query_rate_observed", sa.Float(), nullable=True),
        # Baseline metadata
        sa.Column("baseline_generated_at", sa.DateTime(), nullable=True),
        sa.Column("baseline_data_points", sa.Integer(), nullable=True, default=0),
        sa.Column("baseline_days_analyzed", sa.Integer(), nullable=True, default=7),
        # Sensitivity settings
        sa.Column(
            "anomaly_sensitivity", sa.Float(), nullable=True, default=2.0
        ),  # Std dev multiplier
        # Timestamps
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_dns_client_profile_id"), "dns_client_profile", ["id"], unique=False)
    op.create_unique_constraint(
        "uq_dns_client_profile_client_id", "dns_client_profile", ["client_id"]
    )

    # ==========================================================================
    # DNS Domain Reputation Table - Cached domain scores
    # ==========================================================================

    op.create_table(
        "dns_domain_reputation",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("domain", sa.String(length=255), nullable=False),
        # Reputation scoring
        sa.Column("reputation_score", sa.Float(), nullable=True),  # 0-100 (100 = trusted)
        sa.Column("entropy_score", sa.Float(), nullable=True),  # Shannon entropy
        # Domain metadata
        sa.Column("domain_age_days", sa.Integer(), nullable=True),  # From WHOIS
        sa.Column("typical_ttl", sa.Integer(), nullable=True),
        sa.Column("registrar", sa.String(length=255), nullable=True),
        # Categorization
        sa.Column(
            "category", sa.String(length=50), nullable=True
        ),  # cdn, advertising, social, etc.
        sa.Column("category_confidence", sa.Float(), nullable=True),
        sa.Column("category_source", sa.String(length=50), nullable=True),  # llm, manual
        # Query statistics
        sa.Column("first_seen", sa.DateTime(), nullable=True),
        sa.Column("last_seen", sa.DateTime(), nullable=True),
        sa.Column("query_count", sa.BigInteger(), nullable=True, default=0),
        sa.Column("unique_clients", sa.Integer(), nullable=True, default=0),
        # Threat indicators
        sa.Column(
            "threat_indicators", sa.JSON(), nullable=True
        ),  # {"dga_score": 0.85, "tunneling_score": 0.1}
        # LLM analysis cache
        sa.Column("llm_analysis", sa.Text(), nullable=True),  # JSON with full analysis
        sa.Column("llm_analyzed_at", sa.DateTime(), nullable=True),
        # External reputation (optional)
        sa.Column("external_reputation", sa.JSON(), nullable=True),  # {"virustotal": {...}}
        # Timestamps
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_dns_domain_reputation_id"), "dns_domain_reputation", ["id"], unique=False
    )
    op.create_unique_constraint(
        "uq_dns_domain_reputation_domain", "dns_domain_reputation", ["domain"]
    )
    op.create_index(
        op.f("ix_dns_domain_reputation_score"),
        "dns_domain_reputation",
        ["reputation_score"],
        unique=False,
    )
    op.create_index(
        op.f("ix_dns_domain_reputation_category"),
        "dns_domain_reputation",
        ["category"],
        unique=False,
    )

    # ==========================================================================
    # DNS Security Alert Table - Alert storage with LLM analysis
    # ==========================================================================

    op.create_table(
        "dns_security_alert",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("alert_id", postgresql.UUID(as_uuid=True), nullable=False),  # Unique identifier
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        # Alert classification
        sa.Column(
            "alert_type", sa.String(length=50), nullable=False
        ),  # dga, tunneling, fast_flux, behavioral, reputation
        sa.Column("severity", sa.String(length=20), nullable=False),  # low, medium, high, critical
        # Context
        sa.Column("client_ip", sa.String(length=45), nullable=True),
        sa.Column("domain", sa.String(length=255), nullable=True),
        sa.Column("domains", sa.JSON(), nullable=True),  # For multi-domain alerts
        # Alert content
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("raw_data", sa.JSON(), nullable=True),  # Full detection context
        # LLM analysis
        sa.Column("llm_analysis", sa.Text(), nullable=True),  # Natural language explanation
        sa.Column("remediation", sa.Text(), nullable=True),  # LLM recommendations
        sa.Column("confidence", sa.Float(), nullable=True),  # Analysis confidence
        # Status tracking
        sa.Column(
            "status", sa.String(length=20), nullable=True, default="open"
        ),  # open, acknowledged, resolved, false_positive
        sa.Column("acknowledged_at", sa.DateTime(), nullable=True),
        sa.Column("acknowledged_by", sa.String(length=255), nullable=True),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.Column("resolution_notes", sa.Text(), nullable=True),
        # Timestamps
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_dns_security_alert_id"), "dns_security_alert", ["id"], unique=False)
    op.create_unique_constraint(
        "uq_dns_security_alert_alert_id", "dns_security_alert", ["alert_id"]
    )
    op.create_index(
        op.f("ix_dns_security_alert_timestamp"),
        "dns_security_alert",
        ["timestamp"],
        unique=False,
    )
    op.create_index(
        op.f("ix_dns_security_alert_type"),
        "dns_security_alert",
        ["alert_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_dns_security_alert_severity"),
        "dns_security_alert",
        ["severity"],
        unique=False,
    )
    op.create_index(
        op.f("ix_dns_security_alert_status"),
        "dns_security_alert",
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_dns_security_alert_client_ip"),
        "dns_security_alert",
        ["client_ip"],
        unique=False,
    )

    # ==========================================================================
    # DNS Threat Analysis Table - Cached LLM analyses
    # ==========================================================================

    op.create_table(
        "dns_threat_analysis",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "analysis_id", postgresql.UUID(as_uuid=True), nullable=False
        ),  # Unique identifier
        # Analysis target
        sa.Column(
            "analysis_type", sa.String(length=50), nullable=False
        ),  # domain, pattern, client_behavior
        sa.Column(
            "target_identifier", sa.String(length=255), nullable=False
        ),  # domain or client_ip
        # Analysis result
        sa.Column("analysis_result", sa.JSON(), nullable=True),  # Full LLM response
        sa.Column("threat_level", sa.String(length=20), nullable=True),
        sa.Column("classification", sa.String(length=50), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("recommendations", sa.JSON(), nullable=True),
        # Metadata
        sa.Column("model_used", sa.String(length=100), nullable=True),
        sa.Column("tokens_used", sa.Integer(), nullable=True),
        sa.Column("analysis_duration_ms", sa.Float(), nullable=True),
        # Cache control
        sa.Column("analyzed_at", sa.DateTime(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_dns_threat_analysis_id"), "dns_threat_analysis", ["id"], unique=False)
    op.create_unique_constraint(
        "uq_dns_threat_analysis_analysis_id", "dns_threat_analysis", ["analysis_id"]
    )
    op.create_index(
        op.f("ix_dns_threat_analysis_target"),
        "dns_threat_analysis",
        ["analysis_type", "target_identifier"],
        unique=False,
    )
    op.create_index(
        op.f("ix_dns_threat_analysis_expires"),
        "dns_threat_analysis",
        ["expires_at"],
        unique=False,
    )

    # ==========================================================================
    # Add columns to existing dns_query_log table
    # ==========================================================================

    op.add_column("dns_query_log", sa.Column("entropy_score", sa.Float(), nullable=True))
    op.add_column("dns_query_log", sa.Column("subdomain_length", sa.Integer(), nullable=True))
    op.add_column("dns_query_log", sa.Column("label_count", sa.Integer(), nullable=True))
    op.add_column("dns_query_log", sa.Column("is_numeric_heavy", sa.Boolean(), nullable=True))
    op.add_column(
        "dns_query_log",
        sa.Column("reputation_score", sa.Float(), nullable=True),
    )
    op.add_column(
        "dns_query_log",
        sa.Column("alert_generated", sa.Boolean(), nullable=True, default=False),
    )

    # ==========================================================================
    # Add columns to existing dns_clients table
    # ==========================================================================

    op.add_column(
        "dns_clients",
        sa.Column("has_profile", sa.Boolean(), nullable=True, default=False),
    )
    op.add_column("dns_clients", sa.Column("last_anomaly_at", sa.DateTime(), nullable=True))
    op.add_column(
        "dns_clients",
        sa.Column("anomaly_count_24h", sa.Integer(), nullable=True, default=0),
    )
    op.add_column(
        "dns_clients",
        sa.Column("risk_level", sa.String(length=20), nullable=True, default="low"),
    )


def downgrade() -> None:
    # Remove columns from dns_clients
    op.drop_column("dns_clients", "risk_level")
    op.drop_column("dns_clients", "anomaly_count_24h")
    op.drop_column("dns_clients", "last_anomaly_at")
    op.drop_column("dns_clients", "has_profile")

    # Remove columns from dns_query_log
    op.drop_column("dns_query_log", "alert_generated")
    op.drop_column("dns_query_log", "reputation_score")
    op.drop_column("dns_query_log", "is_numeric_heavy")
    op.drop_column("dns_query_log", "label_count")
    op.drop_column("dns_query_log", "subdomain_length")
    op.drop_column("dns_query_log", "entropy_score")

    # Drop analytics tables
    op.drop_table("dns_threat_analysis")
    op.drop_table("dns_security_alert")
    op.drop_table("dns_domain_reputation")
    op.drop_table("dns_client_profile")
