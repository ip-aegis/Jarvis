"""
LLM tools for DNS security and filtering management.
"""

from datetime import datetime, timedelta

from app.database import SessionLocal
from app.models import DnsBlocklist, DnsClient, DnsCustomRule, DnsQueryLog
from app.tools.base import Tool, tool_registry

# =============================================================================
# Query Tools (READ)
# =============================================================================


async def get_dns_stats_handler(hours: int = 24) -> dict:
    """Get DNS query statistics for the specified time period."""
    from app.services.dns import dns_service

    stats = await dns_service.get_stats(hours=hours)
    return {
        "period_hours": hours,
        "total_queries": stats.get("total_queries", 0),
        "blocked_queries": stats.get("blocked_queries", 0),
        "blocked_percentage": stats.get("blocked_percentage", 0),
        "cached_queries": stats.get("cached_queries", 0),
        "avg_response_time_ms": stats.get("avg_response_time", 0),
    }


async def get_dns_top_blocked_handler(limit: int = 10) -> dict:
    """Get the top blocked domains."""
    from app.services.dns import dns_service

    stats = await dns_service.get_stats(hours=24)
    return {
        "top_blocked_domains": stats.get("top_blocked", [])[:limit],
        "period": "24 hours",
    }


async def get_dns_top_queries_handler(limit: int = 10) -> dict:
    """Get the most queried domains."""
    from app.services.dns import dns_service

    stats = await dns_service.get_stats(hours=24)
    return {
        "top_queried_domains": stats.get("top_domains", [])[:limit],
        "period": "24 hours",
    }


async def lookup_domain_handler(domain: str) -> dict:
    """Look up a domain and check if it's blocked."""
    from app.services.dns import dns_service

    result = await dns_service.lookup_domain(domain)
    return {
        "domain": domain,
        "is_blocked": result.get("is_blocked", False),
        "is_allowed": result.get("is_allowed", False),
        "has_custom_rule": result.get("in_custom_rules", False),
        "active_filter_count": result.get("active_filters_count", 0),
    }


async def search_query_log_handler(
    domain: str = None,
    client_ip: str = None,
    status: str = None,
    limit: int = 50,
) -> dict:
    """Search DNS query history."""
    db = SessionLocal()
    try:
        query = db.query(DnsQueryLog)

        if domain:
            query = query.filter(DnsQueryLog.domain.ilike(f"%{domain}%"))
        if client_ip:
            query = query.filter(DnsQueryLog.client_ip == client_ip)
        if status:
            query = query.filter(DnsQueryLog.status == status)

        entries = query.order_by(DnsQueryLog.timestamp.desc()).limit(limit).all()

        return {
            "query_count": len(entries),
            "filters": {
                "domain": domain,
                "client_ip": client_ip,
                "status": status,
            },
            "entries": [
                {
                    "timestamp": e.timestamp.isoformat() if e.timestamp else None,
                    "client_ip": e.client_ip,
                    "domain": e.domain,
                    "status": e.status,
                    "block_reason": e.block_reason,
                    "response_time_ms": e.response_time_ms,
                }
                for e in entries
            ],
        }
    finally:
        db.close()


async def get_dns_client_stats_handler(client_ip: str) -> dict:
    """Get DNS stats for a specific client/device."""
    db = SessionLocal()
    try:
        # Get client from database
        client = db.query(DnsClient).filter_by(client_id=client_ip).first()

        # Get recent queries
        recent_queries = (
            db.query(DnsQueryLog)
            .filter(DnsQueryLog.client_ip == client_ip)
            .order_by(DnsQueryLog.timestamp.desc())
            .limit(100)
            .all()
        )

        blocked = [q for q in recent_queries if q.status == "blocked"]

        return {
            "client_ip": client_ip,
            "client_name": client.name if client else None,
            "total_queries_recent": len(recent_queries),
            "blocked_queries_recent": len(blocked),
            "blocked_percentage": round(len(blocked) / len(recent_queries) * 100, 1)
            if recent_queries
            else 0,
            "top_domains": _count_top_domains([q.domain for q in recent_queries], 5),
            "top_blocked": _count_top_domains([q.domain for q in blocked], 5),
            "last_seen": client.last_seen.isoformat() if client and client.last_seen else None,
        }
    finally:
        db.close()


async def get_threat_summary_handler() -> dict:
    """Get a summary of recent security-related blocks."""
    db = SessionLocal()
    try:
        # Get recent blocked queries with security-related reasons
        cutoff = datetime.utcnow() - timedelta(hours=24)
        blocked = (
            db.query(DnsQueryLog)
            .filter(DnsQueryLog.timestamp >= cutoff)
            .filter(DnsQueryLog.status == "blocked")
            .all()
        )

        # Categorize by block reason
        categories = {}
        for q in blocked:
            reason = q.block_reason or "unknown"
            if reason not in categories:
                categories[reason] = {"count": 0, "domains": set()}
            categories[reason]["count"] += 1
            categories[reason]["domains"].add(q.domain)

        return {
            "period": "24 hours",
            "total_blocked": len(blocked),
            "categories": {
                k: {
                    "count": v["count"],
                    "unique_domains": len(v["domains"]),
                    "sample_domains": list(v["domains"])[:5],
                }
                for k, v in categories.items()
            },
        }
    finally:
        db.close()


async def list_blocklists_handler() -> dict:
    """List all active blocklists."""
    db = SessionLocal()
    try:
        blocklists = db.query(DnsBlocklist).all()
        return {
            "blocklists": [
                {
                    "id": b.id,
                    "name": b.name,
                    "category": b.category,
                    "enabled": b.enabled,
                    "rules_count": b.rules_count,
                    "last_updated": b.last_updated.isoformat() if b.last_updated else None,
                }
                for b in blocklists
            ],
            "total": len(blocklists),
            "enabled": len([b for b in blocklists if b.enabled]),
        }
    finally:
        db.close()


async def list_custom_rules_handler() -> dict:
    """List custom DNS rules."""
    db = SessionLocal()
    try:
        rules = db.query(DnsCustomRule).all()
        return {
            "rules": [
                {
                    "id": r.id,
                    "type": r.rule_type,
                    "domain": r.domain,
                    "comment": r.comment,
                    "enabled": r.enabled,
                }
                for r in rules
            ],
            "total": len(rules),
            "blocked": len([r for r in rules if r.rule_type == "block"]),
            "allowed": len([r for r in rules if r.rule_type == "allow"]),
        }
    finally:
        db.close()


# =============================================================================
# Write Tools (Require confirmation for destructive actions)
# =============================================================================


async def block_domain_handler(domain: str, comment: str = None) -> dict:
    """Block a domain network-wide."""
    from app.services.dns import dns_service

    success = await dns_service.block_domain(domain)
    if success:
        # Save to database
        db = SessionLocal()
        try:
            rule = DnsCustomRule(
                rule_type="block",
                domain=domain,
                comment=comment,
                enabled=True,
            )
            db.add(rule)
            db.commit()
        finally:
            db.close()

        return {
            "success": True,
            "action": "blocked",
            "domain": domain,
            "message": f"Domain {domain} has been blocked network-wide",
        }
    return {"success": False, "error": "Failed to block domain"}


async def allow_domain_handler(domain: str, comment: str = None) -> dict:
    """Allow (whitelist) a domain."""
    from app.services.dns import dns_service

    success = await dns_service.allow_domain(domain)
    if success:
        # Save to database
        db = SessionLocal()
        try:
            rule = DnsCustomRule(
                rule_type="allow",
                domain=domain,
                comment=comment,
                enabled=True,
            )
            db.add(rule)
            db.commit()
        finally:
            db.close()

        return {
            "success": True,
            "action": "allowed",
            "domain": domain,
            "message": f"Domain {domain} has been whitelisted",
        }
    return {"success": False, "error": "Failed to allow domain"}


async def detect_dns_anomalies_handler() -> dict:
    """Detect unusual DNS patterns (DGA, tunneling)."""
    from app.services.dns_tasks import dns_processor

    anomalies = await dns_processor.detect_anomalies()
    return {
        "anomaly_count": len(anomalies),
        "anomalies": anomalies,
        "detection_types": ["dga_detection", "tunneling_detection"],
    }


# =============================================================================
# Helper Functions
# =============================================================================


def _count_top_domains(domains: list[str], limit: int = 5) -> list[dict]:
    """Count and return top domains."""
    from collections import Counter

    counts = Counter(domains)
    return [{"domain": d, "count": c} for d, c in counts.most_common(limit)]


# =============================================================================
# Tool Registrations
# =============================================================================

get_dns_stats_tool = Tool(
    name="get_dns_stats",
    description="Get DNS query statistics including total queries, blocked queries, and cache hit rate. Defaults to last 24 hours.",
    parameters={
        "type": "object",
        "properties": {
            "hours": {
                "type": "integer",
                "description": "Number of hours to look back (default: 24)",
            },
        },
        "required": [],
    },
    handler=get_dns_stats_handler,
)

get_dns_top_blocked_tool = Tool(
    name="get_dns_top_blocked",
    description="Get the top blocked domains by DNS filtering.",
    parameters={
        "type": "object",
        "properties": {
            "limit": {
                "type": "integer",
                "description": "Number of domains to return (default: 10)",
            },
        },
        "required": [],
    },
    handler=get_dns_top_blocked_handler,
)

get_dns_top_queries_tool = Tool(
    name="get_dns_top_queries",
    description="Get the most queried domains across the network.",
    parameters={
        "type": "object",
        "properties": {
            "limit": {
                "type": "integer",
                "description": "Number of domains to return (default: 10)",
            },
        },
        "required": [],
    },
    handler=get_dns_top_queries_handler,
)

lookup_domain_tool = Tool(
    name="lookup_domain",
    description="Look up a domain to check if it's blocked by DNS filtering.",
    parameters={
        "type": "object",
        "properties": {
            "domain": {
                "type": "string",
                "description": "The domain to look up",
            },
        },
        "required": ["domain"],
    },
    handler=lookup_domain_handler,
)

search_query_log_tool = Tool(
    name="search_query_log",
    description="Search DNS query history. Can filter by domain, client IP, or status (allowed/blocked).",
    parameters={
        "type": "object",
        "properties": {
            "domain": {
                "type": "string",
                "description": "Domain to search for (partial match)",
            },
            "client_ip": {
                "type": "string",
                "description": "Client IP address to filter by",
            },
            "status": {
                "type": "string",
                "enum": ["allowed", "blocked"],
                "description": "Filter by query status",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum results to return (default: 50)",
            },
        },
        "required": [],
    },
    handler=search_query_log_handler,
)

get_dns_client_stats_tool = Tool(
    name="get_dns_client_stats",
    description="Get DNS statistics for a specific client device by IP address.",
    parameters={
        "type": "object",
        "properties": {
            "client_ip": {
                "type": "string",
                "description": "The client IP address",
            },
        },
        "required": ["client_ip"],
    },
    handler=get_dns_client_stats_handler,
)

get_threat_summary_tool = Tool(
    name="get_threat_summary",
    description="Get a summary of recent security-related DNS blocks including malware, phishing, and tracking.",
    parameters={
        "type": "object",
        "properties": {},
        "required": [],
    },
    handler=get_threat_summary_handler,
)

list_blocklists_tool = Tool(
    name="list_blocklists",
    description="List all DNS blocklists including their status and rule counts.",
    parameters={
        "type": "object",
        "properties": {},
        "required": [],
    },
    handler=list_blocklists_handler,
)

list_custom_rules_tool = Tool(
    name="list_custom_rules",
    description="List custom DNS rules (blocks and allows).",
    parameters={
        "type": "object",
        "properties": {},
        "required": [],
    },
    handler=list_custom_rules_handler,
)

block_domain_tool = Tool(
    name="block_domain",
    description="Block a domain network-wide. This will prevent all devices from accessing this domain.",
    parameters={
        "type": "object",
        "properties": {
            "domain": {
                "type": "string",
                "description": "The domain to block",
            },
            "comment": {
                "type": "string",
                "description": "Optional comment explaining why the domain is blocked",
            },
        },
        "required": ["domain"],
    },
    handler=block_domain_handler,
)

allow_domain_tool = Tool(
    name="allow_domain",
    description="Allow (whitelist) a domain that may be blocked by filters.",
    parameters={
        "type": "object",
        "properties": {
            "domain": {
                "type": "string",
                "description": "The domain to allow",
            },
            "comment": {
                "type": "string",
                "description": "Optional comment explaining why the domain is allowed",
            },
        },
        "required": ["domain"],
    },
    handler=allow_domain_handler,
)

detect_dns_anomalies_tool = Tool(
    name="detect_dns_anomalies",
    description="Detect unusual DNS patterns that may indicate security threats like DGA (Domain Generation Algorithm) malware or DNS tunneling.",
    parameters={
        "type": "object",
        "properties": {},
        "required": [],
    },
    handler=detect_dns_anomalies_handler,
)

# Register all tools
tool_registry.register(get_dns_stats_tool)
tool_registry.register(get_dns_top_blocked_tool)
tool_registry.register(get_dns_top_queries_tool)
tool_registry.register(lookup_domain_tool)
tool_registry.register(search_query_log_tool)
tool_registry.register(get_dns_client_stats_tool)
tool_registry.register(get_threat_summary_tool)
tool_registry.register(list_blocklists_tool)
tool_registry.register(list_custom_rules_tool)
tool_registry.register(block_domain_tool)
tool_registry.register(allow_domain_tool)
tool_registry.register(detect_dns_anomalies_tool)
