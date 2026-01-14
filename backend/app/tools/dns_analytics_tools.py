"""
LLM tools for DNS analytics and threat intelligence.
"""

from datetime import datetime, timedelta

from app.database import SessionLocal
from app.models import DnsClientProfile, DnsSecurityAlert
from app.tools.base import Tool, tool_registry

# =============================================================================
# Analytics Query Tools
# =============================================================================


async def get_client_dns_behavior_handler(client_ip: str) -> dict:
    """Get behavioral analysis for a DNS client."""
    from app.services.dns_client_profiling import get_profiling_service

    service = get_profiling_service()
    risk = service.get_client_risk_assessment(client_ip)

    # Get profile details if available
    db = SessionLocal()
    try:
        profile = db.query(DnsClientProfile).filter(DnsClientProfile.client_id == client_ip).first()

        if profile:
            risk["profile"] = {
                "device_type": profile.device_type_inference,
                "device_confidence": profile.device_type_confidence,
                "normal_query_rate": profile.normal_query_rate_per_hour,
                "baseline_age_days": (
                    (datetime.utcnow() - profile.baseline_generated_at).days
                    if profile.baseline_generated_at
                    else None
                ),
                "top_domains": list(profile.baseline_domains.keys())[:10]
                if profile.baseline_domains
                else [],
            }
    finally:
        db.close()

    return risk


async def get_domain_reputation_handler(domain: str) -> dict:
    """Get reputation score and threat analysis for a domain."""
    from app.services.dns_domain_reputation import get_reputation_service

    service = get_reputation_service()
    result = service.calculate_domain_score(domain)

    return {
        "domain": domain,
        "reputation_score": result["reputation_score"],
        "is_trusted": result["reputation_score"] >= 70,
        "is_suspicious": result["reputation_score"] < 40,
        "entropy": result["entropy_score"],
        "category": result["category"],
        "threat_indicators": result["threat_indicators"],
        "scoring_factors": result["factors"],
    }


async def get_dns_security_alerts_handler(
    severity: str = None,
    alert_type: str = None,
    status: str = None,
    client_ip: str = None,
    limit: int = 20,
) -> dict:
    """Get recent DNS security alerts."""
    db = SessionLocal()
    try:
        query = db.query(DnsSecurityAlert)

        if severity:
            query = query.filter(DnsSecurityAlert.severity == severity)
        if alert_type:
            query = query.filter(DnsSecurityAlert.alert_type == alert_type)
        if status:
            query = query.filter(DnsSecurityAlert.status == status)
        if client_ip:
            query = query.filter(DnsSecurityAlert.client_ip == client_ip)

        alerts = query.order_by(DnsSecurityAlert.timestamp.desc()).limit(limit).all()

        return {
            "alert_count": len(alerts),
            "alerts": [
                {
                    "alert_id": str(a.alert_id),
                    "type": a.alert_type,
                    "severity": a.severity,
                    "client_ip": a.client_ip,
                    "domain": a.domain,
                    "title": a.title,
                    "status": a.status,
                    "timestamp": a.timestamp.isoformat() if a.timestamp else None,
                }
                for a in alerts
            ],
        }
    finally:
        db.close()


async def analyze_dns_threat_handler(alert_id: str) -> dict:
    """Get detailed LLM analysis of a security threat."""
    from uuid import UUID

    from app.services.dns_llm_analysis import get_llm_analysis_service

    db = SessionLocal()
    try:
        try:
            uuid_id = UUID(alert_id)
        except ValueError:
            return {"error": "Invalid alert ID format"}

        alert = db.query(DnsSecurityAlert).filter(DnsSecurityAlert.alert_id == uuid_id).first()

        if not alert:
            return {"error": "Alert not found"}

        # If already has LLM analysis, return it
        if alert.llm_analysis:
            return {
                "alert_id": alert_id,
                "analysis": alert.llm_analysis,
                "remediation": alert.remediation,
                "confidence": alert.confidence,
                "cached": True,
            }

        # Generate new analysis
        llm_service = get_llm_analysis_service()
        analysis = await llm_service.analyze_threat(alert)

        return {
            "alert_id": alert_id,
            "threat_level": analysis.get("threat_level"),
            "classification": analysis.get("classification"),
            "explanation": analysis.get("explanation"),
            "confidence": analysis.get("confidence"),
            "remediation": analysis.get("remediation", []),
            "false_positive_factors": analysis.get("false_positive_factors", []),
            "cached": False,
        }
    finally:
        db.close()


async def investigate_domain_handler(domain: str) -> dict:
    """Deep investigation of a domain."""
    from app.services.dns_advanced_detection import get_detection_service
    from app.services.dns_domain_reputation import get_reputation_service

    db = SessionLocal()
    try:
        rep_service = get_reputation_service()
        detection_service = get_detection_service()

        # Get reputation
        reputation = rep_service.calculate_domain_score(domain)

        # Check for DGA
        dga_result = detection_service.detect_dga(domain)

        # Get query history
        from app.models import DnsQueryLog

        cutoff = datetime.utcnow() - timedelta(hours=24)
        queries = (
            db.query(DnsQueryLog)
            .filter(DnsQueryLog.domain == domain)
            .filter(DnsQueryLog.timestamp >= cutoff)
            .all()
        )

        unique_clients = set(q.client_ip for q in queries)
        blocked_count = sum(1 for q in queries if q.status == "blocked")

        return {
            "domain": domain,
            "reputation": {
                "score": reputation["reputation_score"],
                "category": reputation["category"],
                "entropy": reputation["entropy_score"],
            },
            "dga_analysis": {
                "is_dga": dga_result["is_dga"],
                "confidence": dga_result["confidence"],
            },
            "query_stats_24h": {
                "total_queries": len(queries),
                "unique_clients": len(unique_clients),
                "blocked_count": blocked_count,
            },
            "assessment": (
                "suspicious"
                if dga_result["is_dga"] or reputation["reputation_score"] < 40
                else "likely_safe"
                if reputation["reputation_score"] >= 70
                else "unknown"
            ),
        }
    finally:
        db.close()


async def investigate_client_handler(client_ip: str) -> dict:
    """Investigate a client's DNS behavior."""
    from app.services.dns_client_profiling import get_profiling_service

    db = SessionLocal()
    try:
        profiling = get_profiling_service()

        # Get risk assessment
        risk = profiling.get_client_risk_assessment(client_ip)

        # Get recent anomalies
        anomalies = await profiling.detect_behavioral_anomaly(client_ip)

        # Get recent alerts
        cutoff = datetime.utcnow() - timedelta(hours=24)
        alerts = (
            db.query(DnsSecurityAlert)
            .filter(DnsSecurityAlert.client_ip == client_ip)
            .filter(DnsSecurityAlert.timestamp >= cutoff)
            .all()
        )

        # Get query summary
        from app.models import DnsQueryLog

        queries = (
            db.query(DnsQueryLog)
            .filter(DnsQueryLog.client_ip == client_ip)
            .filter(DnsQueryLog.timestamp >= cutoff)
            .all()
        )

        blocked = [q for q in queries if q.status == "blocked"]
        unique_domains = set(q.domain for q in queries)

        return {
            "client_ip": client_ip,
            "risk_assessment": risk,
            "current_anomalies": anomalies,
            "recent_alerts": [
                {
                    "type": a.alert_type,
                    "severity": a.severity,
                    "title": a.title,
                }
                for a in alerts
            ],
            "activity_24h": {
                "total_queries": len(queries),
                "blocked_queries": len(blocked),
                "unique_domains": len(unique_domains),
                "blocked_percentage": round(len(blocked) / len(queries) * 100, 1) if queries else 0,
            },
        }
    finally:
        db.close()


async def compare_to_baseline_handler(client_ip: str) -> dict:
    """Compare a client's recent activity to their normal baseline."""
    from app.services.dns_client_profiling import get_profiling_service

    profiling = get_profiling_service()
    anomalies = await profiling.detect_behavioral_anomaly(client_ip, window_minutes=60)

    db = SessionLocal()
    try:
        profile = db.query(DnsClientProfile).filter(DnsClientProfile.client_id == client_ip).first()

        if not profile or not profile.baseline_generated_at:
            return {
                "client_ip": client_ip,
                "has_baseline": False,
                "message": "No baseline available for comparison. Build baseline first.",
            }

        return {
            "client_ip": client_ip,
            "has_baseline": True,
            "baseline_info": {
                "generated_at": profile.baseline_generated_at.isoformat(),
                "data_points": profile.baseline_data_points,
                "normal_rate_per_hour": profile.normal_query_rate_per_hour,
                "device_type": profile.device_type_inference,
            },
            "current_anomalies": anomalies,
            "anomaly_count": len(anomalies),
            "status": "anomalous" if anomalies else "normal",
        }
    finally:
        db.close()


# =============================================================================
# Action Tools
# =============================================================================


async def acknowledge_dns_alert_handler(alert_id: str) -> dict:
    """Acknowledge a DNS security alert."""
    from uuid import UUID

    db = SessionLocal()
    try:
        try:
            uuid_id = UUID(alert_id)
        except ValueError:
            return {"success": False, "error": "Invalid alert ID format"}

        alert = db.query(DnsSecurityAlert).filter(DnsSecurityAlert.alert_id == uuid_id).first()

        if not alert:
            return {"success": False, "error": "Alert not found"}

        alert.status = "acknowledged"
        alert.acknowledged_at = datetime.utcnow()
        alert.acknowledged_by = "llm_assistant"
        db.commit()

        return {
            "success": True,
            "message": f"Alert {alert_id} acknowledged",
            "alert_title": alert.title,
        }
    finally:
        db.close()


async def mark_dns_false_positive_handler(alert_id: str, reason: str = None) -> dict:
    """Mark a DNS alert as false positive."""
    from uuid import UUID

    db = SessionLocal()
    try:
        try:
            uuid_id = UUID(alert_id)
        except ValueError:
            return {"success": False, "error": "Invalid alert ID format"}

        alert = db.query(DnsSecurityAlert).filter(DnsSecurityAlert.alert_id == uuid_id).first()

        if not alert:
            return {"success": False, "error": "Alert not found"}

        alert.status = "false_positive"
        alert.resolved_at = datetime.utcnow()
        alert.resolution_notes = reason or "Marked as false positive"
        db.commit()

        return {
            "success": True,
            "message": f"Alert {alert_id} marked as false positive",
            "alert_title": alert.title,
        }
    finally:
        db.close()


async def block_domain_with_alert_handler(domain: str, reason: str = None) -> dict:
    """Block a domain and create documentation."""
    from app.services.dns import dns_service

    db = SessionLocal()
    try:
        # Block the domain
        success = await dns_service.block_domain(domain)

        if not success:
            return {"success": False, "error": "Failed to block domain"}

        # Create custom rule record
        from app.models import DnsCustomRule

        rule = DnsCustomRule(
            rule_type="block",
            domain=domain,
            comment=reason or "Blocked via LLM assistant",
            enabled=True,
            created_at=datetime.utcnow(),
            created_by="llm_assistant",
        )
        db.add(rule)
        db.commit()

        return {
            "success": True,
            "message": f"Domain {domain} has been blocked",
            "domain": domain,
            "reason": reason,
        }
    finally:
        db.close()


# =============================================================================
# Tool Registrations
# =============================================================================


get_client_dns_behavior_tool = Tool(
    name="get_client_dns_behavior",
    description="Get behavioral analysis for a DNS client including device type inference, risk assessment, and normal patterns.",
    parameters={
        "type": "object",
        "properties": {
            "client_ip": {
                "type": "string",
                "description": "The client IP address to analyze",
            },
        },
        "required": ["client_ip"],
    },
    handler=get_client_dns_behavior_handler,
)

get_domain_reputation_tool = Tool(
    name="get_domain_reputation",
    description="Get reputation score and threat analysis for a domain. Returns trust level, entropy, category, and threat indicators.",
    parameters={
        "type": "object",
        "properties": {
            "domain": {
                "type": "string",
                "description": "The domain to analyze",
            },
        },
        "required": ["domain"],
    },
    handler=get_domain_reputation_handler,
)

get_dns_security_alerts_tool = Tool(
    name="get_dns_security_alerts",
    description="Get recent DNS security alerts. Can filter by severity, type, status, or client.",
    parameters={
        "type": "object",
        "properties": {
            "severity": {
                "type": "string",
                "enum": ["low", "medium", "high", "critical"],
                "description": "Filter by severity level",
            },
            "alert_type": {
                "type": "string",
                "enum": ["dga", "tunneling", "fast_flux", "behavioral", "reputation"],
                "description": "Filter by alert type",
            },
            "status": {
                "type": "string",
                "enum": ["open", "acknowledged", "resolved", "false_positive"],
                "description": "Filter by status",
            },
            "client_ip": {
                "type": "string",
                "description": "Filter by client IP",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum alerts to return (default: 20)",
            },
        },
        "required": [],
    },
    handler=get_dns_security_alerts_handler,
)

analyze_dns_threat_tool = Tool(
    name="analyze_dns_threat",
    description="Get detailed LLM-powered analysis of a security threat including explanation, classification, and remediation recommendations.",
    parameters={
        "type": "object",
        "properties": {
            "alert_id": {
                "type": "string",
                "description": "The alert ID to analyze",
            },
        },
        "required": ["alert_id"],
    },
    handler=analyze_dns_threat_handler,
)

investigate_domain_tool = Tool(
    name="investigate_domain",
    description="Deep investigation of a domain including reputation, DGA analysis, and query history.",
    parameters={
        "type": "object",
        "properties": {
            "domain": {
                "type": "string",
                "description": "The domain to investigate",
            },
        },
        "required": ["domain"],
    },
    handler=investigate_domain_handler,
)

investigate_client_tool = Tool(
    name="investigate_client",
    description="Investigate a client's DNS behavior including risk assessment, anomalies, alerts, and activity summary.",
    parameters={
        "type": "object",
        "properties": {
            "client_ip": {
                "type": "string",
                "description": "The client IP to investigate",
            },
        },
        "required": ["client_ip"],
    },
    handler=investigate_client_handler,
)

compare_to_baseline_tool = Tool(
    name="compare_client_to_baseline",
    description="Compare a client's recent DNS activity to their normal behavioral baseline.",
    parameters={
        "type": "object",
        "properties": {
            "client_ip": {
                "type": "string",
                "description": "The client IP to compare",
            },
        },
        "required": ["client_ip"],
    },
    handler=compare_to_baseline_handler,
)

acknowledge_dns_alert_tool = Tool(
    name="acknowledge_dns_alert",
    description="Acknowledge a DNS security alert.",
    parameters={
        "type": "object",
        "properties": {
            "alert_id": {
                "type": "string",
                "description": "The alert ID to acknowledge",
            },
        },
        "required": ["alert_id"],
    },
    handler=acknowledge_dns_alert_handler,
)

mark_dns_false_positive_tool = Tool(
    name="mark_dns_false_positive",
    description="Mark a DNS alert as false positive. This helps improve detection accuracy over time.",
    parameters={
        "type": "object",
        "properties": {
            "alert_id": {
                "type": "string",
                "description": "The alert ID to mark as false positive",
            },
            "reason": {
                "type": "string",
                "description": "Optional reason explaining why this is a false positive",
            },
        },
        "required": ["alert_id"],
    },
    handler=mark_dns_false_positive_handler,
)

block_domain_with_alert_tool = Tool(
    name="block_domain_with_alert",
    description="Block a domain and create security documentation.",
    parameters={
        "type": "object",
        "properties": {
            "domain": {
                "type": "string",
                "description": "The domain to block",
            },
            "reason": {
                "type": "string",
                "description": "Reason for blocking the domain",
            },
        },
        "required": ["domain"],
    },
    handler=block_domain_with_alert_handler,
)

# Register all analytics tools
tool_registry.register(get_client_dns_behavior_tool)
tool_registry.register(get_domain_reputation_tool)
tool_registry.register(get_dns_security_alerts_tool)
tool_registry.register(analyze_dns_threat_tool)
tool_registry.register(investigate_domain_tool)
tool_registry.register(investigate_client_tool)
tool_registry.register(compare_to_baseline_tool)
tool_registry.register(acknowledge_dns_alert_tool)
tool_registry.register(mark_dns_false_positive_tool)
tool_registry.register(block_domain_with_alert_tool)
