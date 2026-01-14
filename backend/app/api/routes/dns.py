"""
DNS security and filtering API routes.
Manages AdGuard Home integration for ad blocking, privacy, and security.
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.database import get_db
from app.models import DnsBlocklist, DnsClient, DnsConfig, DnsCustomRule, DnsQueryLog, DnsStats
from app.services.dns import DEFAULT_BLOCKLISTS, dns_service
from app.services.dns_tasks import dns_processor

logger = get_logger(__name__)

router = APIRouter()


# =============================================================================
# Request/Response Models
# =============================================================================


class DnsConfigUpdate(BaseModel):
    """DNS configuration update request."""

    enabled: Optional[bool] = None
    upstream_dns: Optional[list[str]] = None
    bootstrap_dns: Optional[list[str]] = None
    dnssec_enabled: Optional[bool] = None
    filtering_enabled: Optional[bool] = None
    safe_browsing: Optional[bool] = None
    parental_control: Optional[bool] = None


class DnsConfigResponse(BaseModel):
    """DNS configuration response."""

    enabled: bool
    upstream_dns: list[str]
    bootstrap_dns: list[str]
    dnssec_enabled: bool
    doh_enabled: bool
    dot_enabled: bool
    filtering_enabled: bool
    safe_browsing: bool
    parental_control: bool
    cache_size: int
    cache_ttl_min: int
    cache_ttl_max: int


class DnsStatusResponse(BaseModel):
    """DNS service status response."""

    running: bool
    dns_address: str
    dns_port: int
    protection_enabled: bool
    version: str
    processor_status: dict


class BlocklistCreate(BaseModel):
    """Create a new blocklist."""

    name: str
    url: str
    category: Optional[str] = None


class BlocklistUpdate(BaseModel):
    """Update a blocklist."""

    enabled: Optional[bool] = None
    name: Optional[str] = None


class BlocklistResponse(BaseModel):
    """Blocklist response model."""

    id: int
    name: str
    url: str
    category: Optional[str]
    enabled: bool
    rules_count: int
    last_updated: Optional[datetime]

    class Config:
        from_attributes = True


class CustomRuleCreate(BaseModel):
    """Create a custom DNS rule."""

    rule_type: str = Field(..., description="block, allow, or rewrite")
    domain: str
    answer: Optional[str] = None
    comment: Optional[str] = None


class CustomRuleResponse(BaseModel):
    """Custom rule response model."""

    id: int
    rule_type: str
    domain: str
    answer: Optional[str]
    comment: Optional[str]
    enabled: bool
    created_at: datetime

    class Config:
        from_attributes = True


class BulkRulesCreate(BaseModel):
    """Bulk import DNS rules."""

    rules: list[str] = Field(..., description="List of domains to add")
    rule_type: str = Field(..., description="block or allow")
    comment: Optional[str] = None


class ClientUpdate(BaseModel):
    """Update client settings."""

    name: Optional[str] = None
    filtering_enabled: Optional[bool] = None
    safe_browsing: Optional[bool] = None
    parental_control: Optional[bool] = None
    blocked_services: Optional[list[str]] = None


class ClientResponse(BaseModel):
    """DNS client response model."""

    id: int
    client_id: str
    name: Optional[str]
    ip_addresses: list[str]
    mac_address: Optional[str]
    use_global_settings: bool
    filtering_enabled: bool
    safe_browsing: Optional[bool]
    parental_control: Optional[bool]
    blocked_services: Optional[list[str]]
    queries_count: int
    blocked_count: int
    last_seen: Optional[datetime]

    class Config:
        from_attributes = True


class QueryLogEntry(BaseModel):
    """Query log entry response."""

    timestamp: datetime
    client_ip: str
    client_name: Optional[str]
    domain: str
    query_type: str
    status: str
    block_reason: Optional[str]
    response_time_ms: float
    cached: bool


class DnsStatsResponse(BaseModel):
    """DNS statistics response."""

    total_queries: int
    blocked_queries: int
    blocked_percentage: float
    cached_queries: int
    avg_response_time: float
    top_domains: list[dict]
    top_blocked: list[dict]
    top_clients: list[dict]
    queries_over_time: list[int]
    blocked_over_time: list[int]


class DomainLookupResponse(BaseModel):
    """Domain lookup response."""

    domain: str
    is_blocked: bool
    is_allowed: bool
    in_custom_rules: bool
    active_filters_count: int


class QuickBlockRequest(BaseModel):
    """Quick block/allow request."""

    domain: str
    comment: Optional[str] = None


# =============================================================================
# Status & Configuration Endpoints
# =============================================================================


@router.get("/status")
async def get_dns_status() -> DnsStatusResponse:
    """Get DNS service status."""
    status = await dns_service.get_status()
    return DnsStatusResponse(
        running=status.get("running", False),
        dns_address=status.get("dns_address", ""),
        dns_port=status.get("dns_port", 53),
        protection_enabled=status.get("protection_enabled", False),
        version=status.get("version", "unknown"),
        processor_status=dns_processor.get_status(),
    )


@router.get("/config")
async def get_dns_config(db: Session = Depends(get_db)) -> dict:
    """Get DNS configuration."""
    # Get from database
    config = db.query(DnsConfig).first()
    if not config:
        # Create default config
        config = DnsConfig(
            enabled=True,
            upstream_dns=["https://dns.cloudflare.com/dns-query", "https://dns.google/dns-query"],
            bootstrap_dns=["9.9.9.9", "1.1.1.1"],
            dnssec_enabled=True,
            doh_enabled=True,
            dot_enabled=True,
            filtering_enabled=True,
            safe_browsing=True,
            parental_control=False,
        )
        db.add(config)
        db.commit()
        db.refresh(config)

    # Also get live config from AdGuard
    adguard_config = await dns_service.get_dns_config()

    return {
        "database": {
            "id": config.id,
            "enabled": config.enabled,
            "upstream_dns": config.upstream_dns or [],
            "bootstrap_dns": config.bootstrap_dns or [],
            "dnssec_enabled": config.dnssec_enabled,
            "filtering_enabled": config.filtering_enabled,
            "safe_browsing": config.safe_browsing,
            "parental_control": config.parental_control,
        },
        "adguard": adguard_config,
    }


@router.put("/config")
async def update_dns_config(
    update: DnsConfigUpdate,
    db: Session = Depends(get_db),
) -> dict:
    """Update DNS configuration."""
    config = db.query(DnsConfig).first()
    if not config:
        config = DnsConfig()
        db.add(config)

    # Update database config
    if update.enabled is not None:
        config.enabled = update.enabled
    if update.upstream_dns is not None:
        config.upstream_dns = update.upstream_dns
        # Also update in AdGuard
        await dns_service.set_upstream_dns(update.upstream_dns, update.bootstrap_dns)
    if update.bootstrap_dns is not None:
        config.bootstrap_dns = update.bootstrap_dns
    if update.dnssec_enabled is not None:
        config.dnssec_enabled = update.dnssec_enabled
    if update.filtering_enabled is not None:
        config.filtering_enabled = update.filtering_enabled
        await dns_service.set_filtering_enabled(update.filtering_enabled)
    if update.safe_browsing is not None:
        config.safe_browsing = update.safe_browsing
    if update.parental_control is not None:
        config.parental_control = update.parental_control

    db.commit()
    return {"message": "Configuration updated", "config": update.model_dump(exclude_none=True)}


@router.post("/restart")
async def restart_dns_service():
    """Restart the DNS service (background tasks)."""
    await dns_processor.stop()
    await dns_processor.start()
    return {"message": "DNS background tasks restarted"}


# =============================================================================
# Statistics Endpoints
# =============================================================================


@router.get("/stats")
async def get_dns_stats(hours: int = 24) -> DnsStatsResponse:
    """Get DNS query statistics."""
    stats = await dns_service.get_stats(hours=hours)
    return DnsStatsResponse(
        total_queries=stats.get("total_queries", 0),
        blocked_queries=stats.get("blocked_queries", 0),
        blocked_percentage=stats.get("blocked_percentage", 0),
        cached_queries=stats.get("cached_queries", 0),
        avg_response_time=stats.get("avg_response_time", 0),
        top_domains=stats.get("top_domains", []),
        top_blocked=stats.get("top_blocked", []),
        top_clients=stats.get("top_clients", []),
        queries_over_time=stats.get("queries_over_time", []),
        blocked_over_time=stats.get("blocked_over_time", []),
    )


@router.get("/stats/history")
async def get_stats_history(
    hours: int = 24,
    db: Session = Depends(get_db),
) -> list[dict]:
    """Get historical DNS statistics."""
    from datetime import timedelta

    cutoff = datetime.utcnow() - timedelta(hours=hours)
    stats = (
        db.query(DnsStats)
        .filter(DnsStats.timestamp >= cutoff)
        .order_by(DnsStats.timestamp.desc())
        .all()
    )
    return [
        {
            "timestamp": s.timestamp.isoformat(),
            "period": s.period,
            "total_queries": s.total_queries,
            "blocked_queries": s.blocked_queries,
            "cached_queries": s.cached_queries,
            "avg_response_time": s.avg_response_time,
        }
        for s in stats
    ]


# =============================================================================
# Blocklist Endpoints
# =============================================================================


@router.get("/blocklists")
async def list_blocklists(db: Session = Depends(get_db)) -> dict:
    """List all blocklists."""
    blocklists = db.query(DnsBlocklist).all()

    # Also get from AdGuard
    filtering = await dns_service.get_filtering_status()

    return {
        "blocklists": [BlocklistResponse.model_validate(b) for b in blocklists],
        "adguard_filters": filtering.get("filters", []),
    }


@router.post("/blocklists")
async def add_blocklist(
    blocklist: BlocklistCreate,
    db: Session = Depends(get_db),
) -> dict:
    """Add a new blocklist."""
    # Check if already exists
    existing = db.query(DnsBlocklist).filter_by(url=blocklist.url).first()
    if existing:
        raise HTTPException(status_code=400, detail="Blocklist already exists")

    # Add to AdGuard
    success = await dns_service.add_filter_url(blocklist.name, blocklist.url)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to add blocklist to AdGuard")

    # Save to database
    new_blocklist = DnsBlocklist(
        name=blocklist.name,
        url=blocklist.url,
        category=blocklist.category,
        enabled=True,
    )
    db.add(new_blocklist)
    db.commit()
    db.refresh(new_blocklist)

    return {
        "message": "Blocklist added",
        "blocklist": BlocklistResponse.model_validate(new_blocklist),
    }


@router.delete("/blocklists/{blocklist_id}")
async def remove_blocklist(
    blocklist_id: int,
    db: Session = Depends(get_db),
) -> dict:
    """Remove a blocklist."""
    blocklist = db.query(DnsBlocklist).filter_by(id=blocklist_id).first()
    if not blocklist:
        raise HTTPException(status_code=404, detail="Blocklist not found")

    # Remove from AdGuard
    await dns_service.remove_filter_url(blocklist.url)

    # Remove from database
    db.delete(blocklist)
    db.commit()

    return {"message": "Blocklist removed"}


@router.put("/blocklists/{blocklist_id}")
async def update_blocklist(
    blocklist_id: int,
    update: BlocklistUpdate,
    db: Session = Depends(get_db),
) -> dict:
    """Update a blocklist (enable/disable, rename)."""
    blocklist = db.query(DnsBlocklist).filter_by(id=blocklist_id).first()
    if not blocklist:
        raise HTTPException(status_code=404, detail="Blocklist not found")

    # Update enabled state in AdGuard
    if update.enabled is not None:
        success = await dns_service.set_filter_enabled(blocklist.url, update.enabled)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to update blocklist in AdGuard")
        blocklist.enabled = update.enabled

    # Update name if provided
    if update.name is not None:
        blocklist.name = update.name

    db.commit()
    db.refresh(blocklist)

    return {
        "message": "Blocklist updated",
        "blocklist": BlocklistResponse.model_validate(blocklist),
    }


@router.post("/blocklists/{blocklist_id}/update")
async def force_update_blocklist(blocklist_id: int) -> dict:
    """Force update a specific blocklist."""
    success = await dns_service.refresh_filters()
    return {"message": "Blocklist update triggered", "success": success}


@router.get("/blocklists/recommended")
async def get_recommended_blocklists() -> dict:
    """Get list of recommended blocklists."""
    return {"blocklists": DEFAULT_BLOCKLISTS}


@router.post("/blocklists/setup-defaults")
async def setup_default_blocklists(db: Session = Depends(get_db)) -> dict:
    """Set up default blocklists."""
    result = await dns_service.setup_default_blocklists()

    # Sync to database
    await dns_service.sync_blocklists_to_db(db)

    return result


# =============================================================================
# Custom Rules Endpoints
# =============================================================================


@router.get("/rules")
async def list_custom_rules(db: Session = Depends(get_db)) -> dict:
    """List custom DNS rules."""
    rules = db.query(DnsCustomRule).all()

    # Also get from AdGuard
    adguard_rules = await dns_service.get_custom_rules()

    return {
        "rules": [CustomRuleResponse.model_validate(r) for r in rules],
        "adguard_rules": adguard_rules,
    }


@router.post("/rules")
async def add_custom_rule(
    rule: CustomRuleCreate,
    db: Session = Depends(get_db),
) -> dict:
    """Add a custom DNS rule."""
    # Apply to AdGuard
    if rule.rule_type == "block":
        success = await dns_service.block_domain(rule.domain)
    elif rule.rule_type == "allow":
        success = await dns_service.allow_domain(rule.domain)
    elif rule.rule_type == "rewrite":
        if not rule.answer:
            raise HTTPException(
                status_code=400,
                detail="Rewrite rules require an 'answer' field (IP address or domain)",
            )
        success = await dns_service.add_rewrite(rule.domain, rule.answer)
    else:
        raise HTTPException(
            status_code=400, detail="Invalid rule type. Use 'block', 'allow', or 'rewrite'"
        )

    if not success:
        raise HTTPException(status_code=500, detail="Failed to add rule to AdGuard")

    # Save to database
    new_rule = DnsCustomRule(
        rule_type=rule.rule_type,
        domain=rule.domain,
        answer=rule.answer,
        comment=rule.comment,
        enabled=True,
    )
    db.add(new_rule)
    db.commit()
    db.refresh(new_rule)

    return {"message": "Rule added", "rule": CustomRuleResponse.model_validate(new_rule)}


@router.delete("/rules/{rule_id}")
async def remove_custom_rule(
    rule_id: int,
    db: Session = Depends(get_db),
) -> dict:
    """Remove a custom DNS rule."""
    rule = db.query(DnsCustomRule).filter_by(id=rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    # Remove from AdGuard based on rule type
    if rule.rule_type == "rewrite":
        if rule.answer:
            await dns_service.remove_rewrite(rule.domain, rule.answer)
    else:
        await dns_service.remove_rule(rule.domain)

    # Remove from database
    db.delete(rule)
    db.commit()

    return {"message": "Rule removed"}


@router.post("/rules/bulk")
async def bulk_import_rules(
    bulk: BulkRulesCreate,
    db: Session = Depends(get_db),
) -> dict:
    """Bulk import DNS rules."""
    if bulk.rule_type not in ("block", "allow"):
        raise HTTPException(status_code=400, detail="Invalid rule type. Use 'block' or 'allow'")

    added = []
    failed = []
    skipped = []

    for domain in bulk.rules:
        domain = domain.strip()
        if not domain or domain.startswith("#"):
            continue

        # Check if rule already exists
        existing = db.query(DnsCustomRule).filter_by(domain=domain).first()
        if existing:
            skipped.append(domain)
            continue

        try:
            # Apply to AdGuard
            if bulk.rule_type == "block":
                success = await dns_service.block_domain(domain)
            else:
                success = await dns_service.allow_domain(domain)

            if success:
                # Save to database
                new_rule = DnsCustomRule(
                    rule_type=bulk.rule_type,
                    domain=domain,
                    comment=bulk.comment,
                    enabled=True,
                )
                db.add(new_rule)
                added.append(domain)
            else:
                failed.append(domain)
        except Exception as e:
            logger.error("bulk_rule_import_error", domain=domain, error=str(e))
            failed.append(domain)

    db.commit()

    return {
        "message": f"Bulk import complete: {len(added)} added, {len(skipped)} skipped, {len(failed)} failed",
        "added": added,
        "skipped": skipped,
        "failed": failed,
    }


# =============================================================================
# Quick Block/Allow Endpoints
# =============================================================================


@router.post("/block")
async def quick_block_domain(
    request: QuickBlockRequest,
    db: Session = Depends(get_db),
) -> dict:
    """Quick block a domain."""
    success = await dns_service.block_domain(request.domain)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to block domain")

    # Save to database
    rule = DnsCustomRule(
        rule_type="block",
        domain=request.domain,
        comment=request.comment,
        enabled=True,
    )
    db.add(rule)
    db.commit()

    return {"message": f"Domain {request.domain} blocked", "domain": request.domain}


@router.post("/allow")
async def quick_allow_domain(
    request: QuickBlockRequest,
    db: Session = Depends(get_db),
) -> dict:
    """Quick allow (whitelist) a domain."""
    success = await dns_service.allow_domain(request.domain)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to allow domain")

    # Save to database
    rule = DnsCustomRule(
        rule_type="allow",
        domain=request.domain,
        comment=request.comment,
        enabled=True,
    )
    db.add(rule)
    db.commit()

    return {"message": f"Domain {request.domain} allowed", "domain": request.domain}


# =============================================================================
# DNS Rewrite Endpoints (Custom DNS Entries)
# =============================================================================


class RewriteCreate(BaseModel):
    """Create a DNS rewrite rule (custom DNS entry)."""

    domain: str = Field(
        ..., description="Domain name to rewrite (e.g., 'jarvis' or 'myserver.local')"
    )
    answer: str = Field(
        ..., description="IP address or domain to resolve to (e.g., '10.10.20.235')"
    )
    comment: Optional[str] = None


class RewriteResponse(BaseModel):
    """DNS rewrite response."""

    id: int
    domain: str
    answer: str
    comment: Optional[str]
    enabled: bool
    created_at: datetime

    class Config:
        from_attributes = True


@router.get("/rewrites")
async def list_rewrites(db: Session = Depends(get_db)) -> dict:
    """List all DNS rewrite rules (custom DNS entries)."""
    # Get from database
    db_rewrites = db.query(DnsCustomRule).filter_by(rule_type="rewrite").all()

    # Also get from AdGuard
    adguard_rewrites = await dns_service.get_rewrites()

    return {
        "rewrites": [
            {
                "id": r.id,
                "domain": r.domain,
                "answer": r.answer,
                "comment": r.comment,
                "enabled": r.enabled,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in db_rewrites
        ],
        "adguard_rewrites": adguard_rewrites,
    }


@router.post("/rewrites")
async def add_rewrite(
    rewrite: RewriteCreate,
    db: Session = Depends(get_db),
) -> dict:
    """Add a DNS rewrite rule (custom DNS entry).

    This allows you to create custom DNS entries like:
    - 'jarvis' -> '10.10.20.235' (so anyone querying 'jarvis' gets this IP)
    - 'myserver.local' -> '192.168.1.100'
    """
    # Check if already exists
    existing = (
        db.query(DnsCustomRule)
        .filter_by(
            rule_type="rewrite",
            domain=rewrite.domain,
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Rewrite for domain '{rewrite.domain}' already exists. Delete it first to update.",
        )

    # Add to AdGuard
    success = await dns_service.add_rewrite(rewrite.domain, rewrite.answer)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to add rewrite to AdGuard Home")

    # Save to database
    rule = DnsCustomRule(
        rule_type="rewrite",
        domain=rewrite.domain,
        answer=rewrite.answer,
        comment=rewrite.comment,
        enabled=True,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)

    return {
        "message": f"DNS rewrite added: {rewrite.domain} -> {rewrite.answer}",
        "rewrite": {
            "id": rule.id,
            "domain": rule.domain,
            "answer": rule.answer,
            "comment": rule.comment,
            "enabled": rule.enabled,
            "created_at": rule.created_at.isoformat() if rule.created_at else None,
        },
    }


@router.delete("/rewrites/{rewrite_id}")
async def remove_rewrite(
    rewrite_id: int,
    db: Session = Depends(get_db),
) -> dict:
    """Remove a DNS rewrite rule."""
    rule = db.query(DnsCustomRule).filter_by(id=rewrite_id, rule_type="rewrite").first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rewrite not found")

    # Remove from AdGuard
    if rule.answer:
        await dns_service.remove_rewrite(rule.domain, rule.answer)

    # Remove from database
    db.delete(rule)
    db.commit()

    return {"message": f"DNS rewrite removed: {rule.domain}"}


@router.put("/rewrites/{rewrite_id}")
async def update_rewrite(
    rewrite_id: int,
    rewrite: RewriteCreate,
    db: Session = Depends(get_db),
) -> dict:
    """Update a DNS rewrite rule."""
    rule = db.query(DnsCustomRule).filter_by(id=rewrite_id, rule_type="rewrite").first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rewrite not found")

    old_domain = rule.domain
    old_answer = rule.answer

    # Update in AdGuard (remove old, add new)
    if old_answer:
        await dns_service.remove_rewrite(old_domain, old_answer)
    success = await dns_service.add_rewrite(rewrite.domain, rewrite.answer)
    if not success:
        # Try to restore the old rule
        if old_answer:
            await dns_service.add_rewrite(old_domain, old_answer)
        raise HTTPException(status_code=500, detail="Failed to update rewrite in AdGuard Home")

    # Update database
    rule.domain = rewrite.domain
    rule.answer = rewrite.answer
    if rewrite.comment is not None:
        rule.comment = rewrite.comment
    db.commit()
    db.refresh(rule)

    return {
        "message": f"DNS rewrite updated: {rewrite.domain} -> {rewrite.answer}",
        "rewrite": {
            "id": rule.id,
            "domain": rule.domain,
            "answer": rule.answer,
            "comment": rule.comment,
            "enabled": rule.enabled,
            "created_at": rule.created_at.isoformat() if rule.created_at else None,
        },
    }


# =============================================================================
# Query Log Endpoints
# =============================================================================


@router.get("/querylog")
async def get_query_log(
    limit: int = 100,
    offset: int = 0,
    search: Optional[str] = None,
    status: Optional[str] = None,
    client_ip: Optional[str] = None,
) -> dict:
    """Get DNS query log from AdGuard."""
    entries = await dns_service.get_query_log(
        limit=limit,
        offset=offset,
        search=search,
        response_status=status,
    )
    # Filter by client_ip if specified (post-filter since AdGuard doesn't support it)
    if client_ip:
        entries = [e for e in entries if e.get("client_ip") == client_ip]
    return {"entries": entries, "count": len(entries)}


@router.get("/querylog/db")
async def get_query_log_from_db(
    limit: int = 100,
    offset: int = 0,
    client_ip: Optional[str] = None,
    domain: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
) -> dict:
    """Get DNS query log from database."""
    query = db.query(DnsQueryLog)

    if client_ip:
        query = query.filter(DnsQueryLog.client_ip == client_ip)
    if domain:
        query = query.filter(DnsQueryLog.domain.ilike(f"%{domain}%"))
    if status:
        query = query.filter(DnsQueryLog.status == status)

    total = query.count()
    entries = query.order_by(DnsQueryLog.timestamp.desc()).offset(offset).limit(limit).all()

    return {
        "entries": [
            {
                "timestamp": e.timestamp.isoformat(),
                "client_ip": e.client_ip,
                "domain": e.domain,
                "query_type": e.query_type,
                "status": e.status,
                "block_reason": e.block_reason,
                "response_time_ms": e.response_time_ms,
                "cached": e.cached,
            }
            for e in entries
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


# =============================================================================
# Client Endpoints
# =============================================================================


@router.get("/clients")
async def list_clients(db: Session = Depends(get_db)) -> dict:
    """List known DNS clients."""
    clients = db.query(DnsClient).order_by(DnsClient.last_seen.desc()).all()

    # Also get from AdGuard
    adguard_clients = await dns_service.get_clients()

    return {
        "clients": [ClientResponse.model_validate(c) for c in clients],
        "adguard_clients": adguard_clients,
    }


@router.get("/clients/{client_id}")
async def get_client(
    client_id: int,
    db: Session = Depends(get_db),
) -> ClientResponse:
    """Get a specific client."""
    client = db.query(DnsClient).filter_by(id=client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return ClientResponse.model_validate(client)


@router.put("/clients/{client_id}")
async def update_client(
    client_id: int,
    update: ClientUpdate,
    db: Session = Depends(get_db),
) -> dict:
    """Update client settings."""
    client = db.query(DnsClient).filter_by(id=client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    if update.name is not None:
        client.name = update.name
    if update.filtering_enabled is not None:
        client.filtering_enabled = update.filtering_enabled
        client.use_global_settings = False
    if update.safe_browsing is not None:
        client.safe_browsing = update.safe_browsing
        client.use_global_settings = False
    if update.parental_control is not None:
        client.parental_control = update.parental_control
        client.use_global_settings = False
    if update.blocked_services is not None:
        client.blocked_services = update.blocked_services

    db.commit()

    # Sync to AdGuard if needed
    if not client.use_global_settings:
        await dns_service.update_client(
            client.client_id,
            {
                "name": client.name,
                "ids": client.ip_addresses or [client.client_id],
                "filtering_enabled": client.filtering_enabled,
                "safebrowsing_enabled": client.safe_browsing,
                "parental_enabled": client.parental_control,
                "blocked_services": client.blocked_services or [],
            },
        )

    return {"message": "Client updated", "client": ClientResponse.model_validate(client)}


@router.post("/clients/sync")
async def sync_clients(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> dict:
    """Sync clients from AdGuard to database."""
    await dns_service.sync_clients_to_db(db)
    return {"message": "Clients synced"}


# =============================================================================
# Domain Lookup Endpoint
# =============================================================================


@router.get("/lookup/{domain}")
async def lookup_domain(domain: str) -> DomainLookupResponse:
    """Look up a domain and check if it's blocked."""
    result = await dns_service.lookup_domain(domain)
    return DomainLookupResponse(**result)


# =============================================================================
# Anomaly Detection Endpoint
# =============================================================================


@router.get("/anomalies")
async def detect_anomalies() -> dict:
    """Detect DNS anomalies (DGA, tunneling, etc.)."""
    anomalies = await dns_processor.detect_anomalies()
    return {"anomalies": anomalies, "count": len(anomalies)}


# =============================================================================
# Security Alerts Endpoints
# =============================================================================


class AlertResponse(BaseModel):
    """Security alert response."""

    id: int
    alert_id: str
    timestamp: datetime
    alert_type: str
    severity: str
    client_ip: Optional[str]
    domain: Optional[str]
    title: str
    description: Optional[str]
    llm_analysis: Optional[str]
    remediation: Optional[str]
    confidence: Optional[float]
    status: str
    acknowledged_at: Optional[datetime]
    resolved_at: Optional[datetime]

    class Config:
        from_attributes = True


class AlertStatusUpdate(BaseModel):
    """Alert status update request."""

    status: str
    resolution_notes: Optional[str] = None


@router.get("/alerts")
async def list_alerts(
    status: Optional[str] = None,
    severity: Optional[str] = None,
    alert_type: Optional[str] = None,
    client_ip: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
) -> dict:
    """List DNS security alerts."""
    from app.models import DnsSecurityAlert

    query = db.query(DnsSecurityAlert)

    if status:
        query = query.filter(DnsSecurityAlert.status == status)
    if severity:
        query = query.filter(DnsSecurityAlert.severity == severity)
    if alert_type:
        query = query.filter(DnsSecurityAlert.alert_type == alert_type)
    if client_ip:
        query = query.filter(DnsSecurityAlert.client_ip == client_ip)

    total = query.count()
    alerts = query.order_by(DnsSecurityAlert.timestamp.desc()).offset(offset).limit(limit).all()

    return {
        "alerts": [
            {
                "id": a.id,
                "alert_id": str(a.alert_id),
                "timestamp": a.timestamp.isoformat() if a.timestamp else None,
                "alert_type": a.alert_type,
                "severity": a.severity,
                "client_ip": a.client_ip,
                "domain": a.domain,
                "title": a.title,
                "description": a.description,
                "llm_analysis": a.llm_analysis,
                "remediation": a.remediation,
                "confidence": a.confidence,
                "status": a.status,
                "acknowledged_at": a.acknowledged_at.isoformat() if a.acknowledged_at else None,
                "resolved_at": a.resolved_at.isoformat() if a.resolved_at else None,
            }
            for a in alerts
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/alerts/{alert_id}")
async def get_alert(
    alert_id: str,
    db: Session = Depends(get_db),
) -> dict:
    """Get a specific security alert."""
    from uuid import UUID

    from app.models import DnsSecurityAlert

    try:
        uuid_id = UUID(alert_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid alert ID format")

    alert = db.query(DnsSecurityAlert).filter(DnsSecurityAlert.alert_id == uuid_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    return {
        "id": alert.id,
        "alert_id": str(alert.alert_id),
        "timestamp": alert.timestamp.isoformat() if alert.timestamp else None,
        "alert_type": alert.alert_type,
        "severity": alert.severity,
        "client_ip": alert.client_ip,
        "domain": alert.domain,
        "domains": alert.domains,
        "title": alert.title,
        "description": alert.description,
        "raw_data": alert.raw_data,
        "llm_analysis": alert.llm_analysis,
        "remediation": alert.remediation,
        "confidence": alert.confidence,
        "status": alert.status,
        "acknowledged_at": alert.acknowledged_at.isoformat() if alert.acknowledged_at else None,
        "acknowledged_by": alert.acknowledged_by,
        "resolved_at": alert.resolved_at.isoformat() if alert.resolved_at else None,
        "resolution_notes": alert.resolution_notes,
    }


@router.post("/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(
    alert_id: str,
    db: Session = Depends(get_db),
) -> dict:
    """Acknowledge a security alert."""
    from uuid import UUID

    from app.models import DnsSecurityAlert

    try:
        uuid_id = UUID(alert_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid alert ID format")

    alert = db.query(DnsSecurityAlert).filter(DnsSecurityAlert.alert_id == uuid_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    alert.status = "acknowledged"
    alert.acknowledged_at = datetime.utcnow()
    alert.acknowledged_by = "user"  # Could be expanded to track actual user
    alert.updated_at = datetime.utcnow()
    db.commit()

    return {"message": "Alert acknowledged", "alert_id": alert_id}


@router.post("/alerts/{alert_id}/resolve")
async def resolve_alert(
    alert_id: str,
    update: AlertStatusUpdate,
    db: Session = Depends(get_db),
) -> dict:
    """Resolve a security alert."""
    from uuid import UUID

    from app.models import DnsSecurityAlert

    try:
        uuid_id = UUID(alert_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid alert ID format")

    alert = db.query(DnsSecurityAlert).filter(DnsSecurityAlert.alert_id == uuid_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    alert.status = "resolved"
    alert.resolved_at = datetime.utcnow()
    alert.resolution_notes = update.resolution_notes
    alert.updated_at = datetime.utcnow()
    db.commit()

    return {"message": "Alert resolved", "alert_id": alert_id}


@router.post("/alerts/{alert_id}/false-positive")
async def mark_false_positive(
    alert_id: str,
    db: Session = Depends(get_db),
) -> dict:
    """Mark alert as false positive."""
    from uuid import UUID

    from app.models import DnsSecurityAlert

    try:
        uuid_id = UUID(alert_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid alert ID format")

    alert = db.query(DnsSecurityAlert).filter(DnsSecurityAlert.alert_id == uuid_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    alert.status = "false_positive"
    alert.resolved_at = datetime.utcnow()
    alert.resolution_notes = "Marked as false positive"
    alert.updated_at = datetime.utcnow()
    db.commit()

    # TODO: Feed back to detection algorithms to improve accuracy

    return {"message": "Alert marked as false positive", "alert_id": alert_id}


# =============================================================================
# Analytics Endpoints
# =============================================================================


@router.get("/analytics/reputation/{domain}")
async def get_domain_reputation(domain: str) -> dict:
    """Get reputation score for a domain."""
    from app.services.dns_domain_reputation import get_reputation_service

    service = get_reputation_service()
    result = service.calculate_domain_score(domain)
    return {"domain": domain, **result}


@router.get("/analytics/client/{client_ip}/behavior")
async def get_client_behavior(
    client_ip: str,
    db: Session = Depends(get_db),
) -> dict:
    """Get behavioral analysis for a client."""
    from app.services.dns_client_profiling import get_profiling_service

    service = get_profiling_service()
    risk = service.get_client_risk_assessment(client_ip)
    return risk


@router.post("/analytics/client/{client_ip}/baseline")
async def build_client_baseline(
    client_ip: str,
    days: int = 7,
) -> dict:
    """Build or rebuild behavioral baseline for a client."""
    from app.services.dns_client_profiling import get_profiling_service

    service = get_profiling_service()
    profile = await service.build_baseline(client_ip, days=days)

    if profile:
        return {
            "message": "Baseline built successfully",
            "client_ip": client_ip,
            "data_points": profile.baseline_data_points,
            "device_type": profile.device_type_inference,
        }
    else:
        return {
            "message": "Insufficient data to build baseline",
            "client_ip": client_ip,
        }


@router.get("/analytics/detection/run")
async def run_detection_analysis(
    client_ip: Optional[str] = None,
    hours: int = 1,
) -> dict:
    """Run comprehensive threat detection analysis."""
    from app.services.dns_advanced_detection import get_detection_service

    service = get_detection_service()
    results = service.run_full_analysis(client_ip=client_ip, hours=hours)
    return results


# =============================================================================
# WebSocket Endpoint for Real-Time Alerts
# =============================================================================


from fastapi import WebSocket, WebSocketDisconnect


@router.websocket("/alerts/ws")
async def alerts_websocket(websocket: WebSocket):
    """WebSocket endpoint for real-time DNS security alerts."""
    from app.services.dns_alert_manager import get_alert_manager

    manager = get_alert_manager()
    await manager.connect(websocket)

    try:
        while True:
            # Receive messages from client (subscription updates, etc.)
            data = await websocket.receive_json()

            if data.get("action") == "subscribe":
                await manager.subscribe(websocket, data.get("filters", {}))
                await websocket.send_json(
                    {"type": "subscribed", "filters": data.get("filters", {})}
                )

            elif data.get("action") == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        await manager.disconnect(websocket)
    except Exception as e:
        logger.error("websocket_error", error=str(e))
        await manager.disconnect(websocket)
