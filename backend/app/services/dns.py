"""DNS Service for interacting with AdGuard Home API."""

from datetime import datetime, timedelta
from typing import Optional

import httpx
from sqlalchemy import case, func
from sqlalchemy.orm import Session
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.config import get_settings
from app.core.logging import get_logger
from app.database import SessionLocal
from app.models import (
    DnsBlocklist,
    DnsClient,
    DnsQueryLog,
    DnsStats,
)

settings = get_settings()
logger = get_logger(__name__)

# Default blocklists to install on first setup
DEFAULT_BLOCKLISTS = [
    {
        "name": "AdGuard DNS Filter",
        "url": "https://adguardteam.github.io/HostlistsRegistry/assets/filter_1.txt",
        "category": "ads",
    },
    {
        "name": "EasyList",
        "url": "https://easylist.to/easylist/easylist.txt",
        "category": "ads",
    },
    {
        "name": "EasyPrivacy",
        "url": "https://easylist.to/easylist/easyprivacy.txt",
        "category": "tracking",
    },
    {
        "name": "AdGuard Tracking Protection",
        "url": "https://adguardteam.github.io/HostlistsRegistry/assets/filter_2.txt",
        "category": "tracking",
    },
    {
        "name": "URLhaus Malicious URLs",
        "url": "https://urlhaus.abuse.ch/downloads/hostfile/",
        "category": "malware",
    },
    {
        "name": "Phishing Army",
        "url": "https://phishing.army/download/phishing_army_blocklist.txt",
        "category": "phishing",
    },
    {
        "name": "NoCoin Filter List",
        "url": "https://raw.githubusercontent.com/nickkong/nickkong/master/nickkong.txt",
        "category": "malware",
    },
    {
        "name": "Spam404",
        "url": "https://raw.githubusercontent.com/Spam404/lists/master/main-blacklist.txt",
        "category": "malware",
    },
]


class DnsService:
    """Service for managing DNS filtering via AdGuard Home."""

    def __init__(self):
        self.base_url = settings.adguard_url
        self.username = settings.adguard_username
        self.password = settings.adguard_password
        self.timeout = httpx.Timeout(30.0)
        self._session_cookie: Optional[str] = None

    async def _get_auth_cookie(self) -> Optional[str]:
        """Authenticate with AdGuard Home and get session cookie."""
        if self._session_cookie:
            return self._session_cookie

        if not self.password:
            logger.warning("adguard_no_password", message="No AdGuard password configured")
            return None

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/control/login",
                    json={"name": self.username, "password": self.password},
                )
                if response.status_code == 200:
                    self._session_cookie = response.cookies.get("agh_session")
                    return self._session_cookie
        except Exception as e:
            logger.error("adguard_auth_error", error=str(e))
        return None

    def _get_cookies(self) -> dict:
        """Get cookies dict for authenticated requests."""
        if self._session_cookie:
            return {"agh_session": self._session_cookie}
        return {}

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError)),
    )
    async def _request(
        self,
        method: str,
        endpoint: str,
        json: Optional[dict] = None,
        params: Optional[dict] = None,
    ) -> Optional[dict]:
        """Make authenticated request to AdGuard Home API."""
        await self._get_auth_cookie()

        async with httpx.AsyncClient(timeout=self.timeout, cookies=self._get_cookies()) as client:
            try:
                response = await client.request(
                    method,
                    f"{self.base_url}{endpoint}",
                    json=json,
                    params=params,
                )
                response.raise_for_status()
                if response.content:
                    return response.json()
                return {"success": True}
            except httpx.HTTPStatusError as e:
                logger.error(
                    "adguard_http_error",
                    status=e.response.status_code,
                    endpoint=endpoint,
                )
                return None
            except Exception as e:
                logger.error("adguard_request_error", error=str(e), endpoint=endpoint)
                return None

    # =========================================================================
    # Status & Health
    # =========================================================================

    async def get_status(self) -> dict:
        """Get AdGuard Home status."""
        result = await self._request("GET", "/control/status")
        if result:
            return {
                "running": result.get("running", False),
                "dns_address": result.get("dns_address", ""),
                "dns_port": result.get("dns_port", 53),
                "protection_enabled": result.get("protection_enabled", False),
                "version": result.get("version", "unknown"),
            }
        return {"running": False, "error": "Unable to connect to AdGuard Home"}

    async def get_global_settings(self) -> dict:
        """Get global DNS filtering settings from AdGuard Home."""
        # Fetch safebrowsing status
        safebrowsing = await self._request("GET", "/control/safebrowsing/status")
        # Fetch parental control status
        parental = await self._request("GET", "/control/parental/status")
        # Fetch safe search status
        safesearch = await self._request("GET", "/control/safesearch/status")
        # Fetch globally blocked services
        blocked_services = await self._request("GET", "/control/blocked_services/list")

        return {
            "safebrowsing_enabled": safebrowsing.get("enabled", False) if safebrowsing else False,
            "parental_enabled": parental.get("enabled", False) if parental else False,
            "safesearch_enabled": safesearch.get("enabled", False) if safesearch else False,
            "blocked_services": blocked_services if isinstance(blocked_services, list) else [],
        }

    async def set_global_safebrowsing(self, enabled: bool) -> bool:
        """Enable or disable global safe browsing."""
        endpoint = "/control/safebrowsing/enable" if enabled else "/control/safebrowsing/disable"
        result = await self._request("POST", endpoint)
        return result is not None

    async def set_global_parental(self, enabled: bool) -> bool:
        """Enable or disable global parental control."""
        endpoint = "/control/parental/enable" if enabled else "/control/parental/disable"
        result = await self._request("POST", endpoint)
        return result is not None

    async def set_global_safesearch(self, enabled: bool) -> bool:
        """Enable or disable global safe search."""
        data = {"enabled": enabled}
        result = await self._request("PUT", "/control/safesearch/settings", data)
        return result is not None

    async def set_global_blocked_services(self, services: list[str]) -> bool:
        """Set globally blocked services."""
        result = await self._request("POST", "/control/blocked_services/set", services)
        return result is not None

    async def health_check(self) -> bool:
        """Check if AdGuard Home is accessible."""
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
                response = await client.get(f"{self.base_url}/control/status")
                return response.status_code == 200
        except Exception:
            return False

    # =========================================================================
    # Statistics
    # =========================================================================

    async def get_stats(self, hours: int = 24) -> dict:
        """Get DNS query statistics for the specified time range.

        Uses pre-aggregated hourly stats from DnsStats table for performance.
        """
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        db = SessionLocal()

        try:
            # Query pre-aggregated hourly stats, deduplicated by timestamp
            # Use subquery to get only the latest entry per hour (by highest id)
            from sqlalchemy import distinct
            from sqlalchemy.orm import aliased

            # Get distinct timestamps with their max id
            subq = (
                db.query(
                    DnsStats.timestamp,
                    func.max(DnsStats.id).label("max_id")
                )
                .filter(DnsStats.period == "hour")
                .filter(DnsStats.timestamp >= cutoff)
                .group_by(DnsStats.timestamp)
                .subquery()
            )

            # Join back to get the full rows for those max ids
            hourly_rows = (
                db.query(DnsStats)
                .join(subq, DnsStats.id == subq.c.max_id)
                .order_by(DnsStats.timestamp)
                .all()
            )

            if not hourly_rows:
                # Fall back to AdGuard if no aggregated data
                db.close()
                return await self._get_stats_from_adguard()

            # Sum up totals from hourly aggregates (now deduplicated)
            total_queries = sum(r.total_queries or 0 for r in hourly_rows)
            blocked_queries = sum(r.blocked_queries or 0 for r in hourly_rows)
            cached_queries = sum(r.cached_queries or 0 for r in hourly_rows)

            # Weighted average response time
            total_weighted_rt = sum(
                (r.avg_response_time or 0) * (r.total_queries or 0)
                for r in hourly_rows
            )
            avg_response_time = total_weighted_rt / total_queries if total_queries > 0 else 0

            # Aggregate top domains across all hours
            domain_counts: dict[str, int] = {}
            blocked_counts: dict[str, int] = {}
            client_counts: dict[str, int] = {}

            for row in hourly_rows:
                if row.top_domains:
                    for item in row.top_domains:
                        domain = item.get("domain", "")
                        count = item.get("count", 0)
                        domain_counts[domain] = domain_counts.get(domain, 0) + count

                if row.top_blocked:
                    for item in row.top_blocked:
                        domain = item.get("domain", "")
                        count = item.get("count", 0)
                        blocked_counts[domain] = blocked_counts.get(domain, 0) + count

                if row.top_clients:
                    for item in row.top_clients:
                        client = item.get("domain", "")  # stored as "domain" in JSON
                        count = item.get("count", 0)
                        client_counts[client] = client_counts.get(client, 0) + count

            # Sort and take top 10
            top_domains = [
                {"domain": d, "count": c}
                for d, c in sorted(domain_counts.items(), key=lambda x: x[1], reverse=True)[:10]
            ]
            top_blocked = [
                {"domain": d, "count": c}
                for d, c in sorted(blocked_counts.items(), key=lambda x: x[1], reverse=True)[:10]
            ]
            top_clients = [
                {"domain": c, "count": cnt}
                for c, cnt in sorted(client_counts.items(), key=lambda x: x[1], reverse=True)[:10]
            ]

            # Build time series arrays
            queries_over_time = []
            blocked_over_time = []

            # Create lookup by timestamp
            stats_by_hour = {row.timestamp: row for row in hourly_rows}

            # Generate all hours in the range
            current = cutoff.replace(minute=0, second=0, microsecond=0)
            end = datetime.utcnow().replace(minute=0, second=0, microsecond=0)

            while current <= end:
                row = stats_by_hour.get(current)
                queries_over_time.append(row.total_queries if row else 0)
                blocked_over_time.append(row.blocked_queries if row else 0)
                current += timedelta(hours=1)

            # Get cache size from AdGuard
            dns_info = await self._request("GET", "/control/dns_info")
            cache_size = dns_info.get("cache_size", 0) if dns_info else 0

        except Exception as e:
            logger.error("get_stats_error", error=str(e))
            db.close()
            return await self._get_stats_from_adguard()
        finally:
            db.close()

        return {
            "total_queries": total_queries,
            "blocked_queries": blocked_queries,
            "blocked_percentage": (
                round(blocked_queries / total_queries * 100, 1) if total_queries > 0 else 0
            ),
            "cached_queries": cached_queries,
            "cache_size": cache_size,
            "avg_response_time": round(avg_response_time, 2) if avg_response_time else 0,
            "top_domains": top_domains,
            "top_blocked": top_blocked,
            "top_clients": top_clients,
            "queries_over_time": queries_over_time,
            "blocked_over_time": blocked_over_time,
        }

    async def _get_stats_from_adguard(self) -> dict:
        """Fallback to get stats directly from AdGuard (no time filtering)."""
        result = await self._request("GET", "/control/stats")
        if not result:
            return {}

        # Calculate totals - AdGuard returns arrays of counts per time interval
        total_queries = result.get("num_dns_queries", 0) or sum(result.get("dns_queries", []))
        blocked_queries = result.get("num_blocked_filtering", 0) or sum(
            result.get("blocked_filtering", [])
        )

        # Get average processing time - AdGuard returns in seconds, convert to ms
        avg_processing_time = result.get("avg_processing_time", 0) or 0
        avg_response_time = avg_processing_time * 1000  # Convert to milliseconds

        # Transform top domains from AdGuard format [{domain: count}] to [{domain, count}]
        def transform_top_list(items: list) -> list:
            """Transform AdGuard's {domain: count} format to {domain, count} format."""
            transformed = []
            for item in items or []:
                if isinstance(item, dict):
                    for domain, count in item.items():
                        transformed.append({"domain": domain, "count": count})
            return transformed

        top_domains = transform_top_list(result.get("top_queried_domains", []))[:10]
        top_blocked = transform_top_list(result.get("top_blocked_domains", []))[:10]
        top_clients = transform_top_list(result.get("top_clients", []))[:10]

        return {
            "total_queries": total_queries,
            "blocked_queries": blocked_queries,
            "blocked_percentage": (
                round(blocked_queries / total_queries * 100, 1) if total_queries > 0 else 0
            ),
            "cached_queries": 0,
            "cache_size": 0,
            "avg_response_time": avg_response_time,
            "top_domains": top_domains,
            "top_blocked": top_blocked,
            "top_clients": top_clients,
            "queries_over_time": result.get("dns_queries", []),
            "blocked_over_time": result.get("blocked_filtering", []),
        }

    async def get_query_log(
        self,
        limit: int = 100,
        offset: int = 0,
        search: Optional[str] = None,
        response_status: Optional[str] = None,
    ) -> list[dict]:
        """Get DNS query log from AdGuard Home."""
        params = {"limit": limit, "offset": offset}
        if search:
            params["search"] = search
        if response_status:
            params["response_status"] = response_status

        result = await self._request("GET", "/control/querylog", params=params)
        if not result:
            return []

        # AdGuard reason values that indicate blocking
        blocked_reasons = {
            "FilteredBlackList",
            "FilteredSafeBrowsing",
            "FilteredParental",
            "FilteredInvalid",
            "FilteredSafeSearch",
            "FilteredBlockedService",
            "Rewrite",  # Rewrite rules can be blocks
        }

        entries = []
        for entry in result.get("data", []):
            reason = entry.get("reason", "")
            # Check if reason indicates blocking (starts with "Filtered" or is in blocked set)
            is_blocked = reason.startswith("Filtered") or reason in blocked_reasons

            # Parse response time - AdGuard returns it as a string
            elapsed = entry.get("elapsed_ms") or entry.get("elapsedMs") or 0
            try:
                response_time = float(elapsed) if isinstance(elapsed, str) else elapsed
            except (ValueError, TypeError):
                response_time = 0

            entries.append(
                {
                    "timestamp": entry.get("time", ""),
                    "client_ip": entry.get("client", ""),
                    "domain": entry.get("question", {}).get("name", ""),
                    "query_type": entry.get("question", {}).get("type", ""),
                    "status": "blocked" if is_blocked else "allowed",
                    "block_reason": reason if is_blocked else "",
                    "response_time_ms": response_time,
                    "upstream": entry.get("upstream", ""),
                    "cached": entry.get("cached", False),
                    "answer": entry.get("answer", []),
                }
            )
        return entries

    # =========================================================================
    # Filtering Rules
    # =========================================================================

    async def get_filtering_status(self) -> dict:
        """Get current filtering configuration."""
        result = await self._request("GET", "/control/filtering/status")
        return result or {}

    async def set_filtering_enabled(self, enabled: bool) -> bool:
        """Enable or disable DNS filtering."""
        result = await self._request(
            "POST",
            "/control/filtering/config",
            json={"enabled": enabled, "interval": 24},
        )
        return result is not None

    async def add_filter_url(self, name: str, url: str, enabled: bool = True) -> bool:
        """Add a filter list URL."""
        result = await self._request(
            "POST",
            "/control/filtering/add_url",
            json={"name": name, "url": url, "whitelist": False},
        )
        return result is not None

    async def remove_filter_url(self, url: str) -> bool:
        """Remove a filter list URL."""
        result = await self._request(
            "POST",
            "/control/filtering/remove_url",
            json={"url": url, "whitelist": False},
        )
        return result is not None

    async def refresh_filters(self) -> bool:
        """Force refresh all filter lists."""
        result = await self._request(
            "POST",
            "/control/filtering/refresh",
            json={"whitelist": False},
        )
        return result is not None

    async def set_filter_enabled(self, url: str, enabled: bool) -> bool:
        """Enable or disable a specific filter list."""
        # Get current filter data
        status = await self.get_filtering_status()
        filters = status.get("filters", [])

        # Find the filter by URL
        target_filter = None
        for f in filters:
            if f.get("url") == url:
                target_filter = f
                break

        if not target_filter:
            logger.warning("filter_not_found", url=url)
            return False

        # Update the filter using AdGuard's set_url endpoint
        result = await self._request(
            "POST",
            "/control/filtering/set_url",
            json={
                "url": url,
                "data": {
                    "name": target_filter.get("name", ""),
                    "url": url,
                    "enabled": enabled,
                },
                "whitelist": False,
            },
        )
        return result is not None

    # =========================================================================
    # Custom Rules (Block/Allow)
    # =========================================================================

    async def get_custom_rules(self) -> list[str]:
        """Get user-defined filtering rules."""
        result = await self._request("GET", "/control/filtering/status")
        if result:
            return result.get("user_rules", [])
        return []

    async def set_custom_rules(self, rules: list[str]) -> bool:
        """Set user-defined filtering rules."""
        result = await self._request(
            "POST",
            "/control/filtering/set_rules",
            json={"rules": rules},
        )
        return result is not None

    async def block_domain(self, domain: str) -> bool:
        """Block a domain."""
        rules = await self.get_custom_rules()
        block_rule = f"||{domain}^"
        if block_rule not in rules:
            rules.append(block_rule)
            return await self.set_custom_rules(rules)
        return True

    async def allow_domain(self, domain: str) -> bool:
        """Allow (whitelist) a domain."""
        rules = await self.get_custom_rules()
        allow_rule = f"@@||{domain}^"
        if allow_rule not in rules:
            rules.append(allow_rule)
            return await self.set_custom_rules(rules)
        return True

    async def remove_rule(self, domain: str) -> bool:
        """Remove block/allow rule for a domain."""
        rules = await self.get_custom_rules()
        block_rule = f"||{domain}^"
        allow_rule = f"@@||{domain}^"
        new_rules = [r for r in rules if r not in (block_rule, allow_rule)]
        if len(new_rules) != len(rules):
            return await self.set_custom_rules(new_rules)
        return True

    # =========================================================================
    # DNS Rewrites (Custom DNS Entries)
    # =========================================================================

    async def get_rewrites(self) -> list[dict]:
        """Get all DNS rewrite rules."""
        result = await self._request("GET", "/control/rewrite/list")
        if result is None:
            return []
        # AdGuard returns a list directly
        if isinstance(result, list):
            return result
        return result.get("rewrites", []) if isinstance(result, dict) else []

    async def add_rewrite(self, domain: str, answer: str) -> bool:
        """Add a DNS rewrite rule (custom DNS entry).

        Args:
            domain: The domain to rewrite (e.g., 'jarvis' or 'myserver.local')
            answer: The IP address or domain to resolve to (e.g., '10.10.20.235')

        Returns:
            True if successful, False otherwise
        """
        result = await self._request(
            "POST",
            "/control/rewrite/add",
            json={"domain": domain, "answer": answer},
        )
        return result is not None

    async def remove_rewrite(self, domain: str, answer: str) -> bool:
        """Remove a DNS rewrite rule.

        Args:
            domain: The domain of the rewrite rule
            answer: The answer of the rewrite rule (must match exactly)

        Returns:
            True if successful, False otherwise
        """
        result = await self._request(
            "POST",
            "/control/rewrite/delete",
            json={"domain": domain, "answer": answer},
        )
        return result is not None

    async def update_rewrite(
        self, old_domain: str, old_answer: str, new_domain: str, new_answer: str
    ) -> bool:
        """Update a DNS rewrite rule by removing and re-adding it.

        Args:
            old_domain: The current domain
            old_answer: The current answer
            new_domain: The new domain
            new_answer: The new answer

        Returns:
            True if successful, False otherwise
        """
        # Remove the old rule
        removed = await self.remove_rewrite(old_domain, old_answer)
        if not removed:
            return False
        # Add the new rule
        return await self.add_rewrite(new_domain, new_answer)

    # =========================================================================
    # Clients
    # =========================================================================

    async def get_clients(self) -> dict:
        """Get client information."""
        result = await self._request("GET", "/control/clients")
        return result or {"clients": [], "auto_clients": []}

    async def add_client(self, client: dict) -> bool:
        """Add a persistent client configuration."""
        result = await self._request("POST", "/control/clients/add", json=client)
        return result is not None

    async def update_client(self, name: str, client: dict) -> bool:
        """Update client configuration."""
        result = await self._request(
            "POST",
            "/control/clients/update",
            json={"name": name, "data": client},
        )
        return result is not None

    async def delete_client(self, name: str) -> bool:
        """Delete a client configuration."""
        result = await self._request(
            "POST",
            "/control/clients/delete",
            json={"name": name},
        )
        return result is not None

    async def get_blocked_services_list(self) -> list[dict]:
        """Get list of all available services that can be blocked.

        Returns:
            List of service objects with id and name fields.
        """
        result = await self._request("GET", "/control/blocked_services/services")

        # Fallback list of common services
        fallback_services = [
            {"id": "facebook", "name": "Facebook"},
            {"id": "instagram", "name": "Instagram"},
            {"id": "tiktok", "name": "TikTok"},
            {"id": "twitter", "name": "Twitter"},
            {"id": "youtube", "name": "YouTube"},
            {"id": "netflix", "name": "Netflix"},
            {"id": "snapchat", "name": "Snapchat"},
            {"id": "discord", "name": "Discord"},
            {"id": "twitch", "name": "Twitch"},
            {"id": "reddit", "name": "Reddit"},
            {"id": "spotify", "name": "Spotify"},
            {"id": "pinterest", "name": "Pinterest"},
            {"id": "amazon", "name": "Amazon"},
            {"id": "ebay", "name": "eBay"},
            {"id": "steam", "name": "Steam"},
            {"id": "epic_games", "name": "Epic Games"},
            {"id": "origin", "name": "EA Origin"},
            {"id": "telegram", "name": "Telegram"},
            {"id": "whatsapp", "name": "WhatsApp"},
            {"id": "viber", "name": "Viber"},
        ]

        # Use fallback if result is None, empty, or not a list
        if not result or not isinstance(result, list):
            return fallback_services

        # Normalize response format - AdGuard may return {id, name, icon_svg}
        # Ensure we always return {id, name} format
        normalized = []
        for s in result:
            if isinstance(s, dict):
                normalized.append({"id": s.get("id", ""), "name": s.get("name", s.get("id", ""))})
            else:
                # Handle case where service is just a string
                normalized.append({"id": str(s), "name": str(s)})

        return normalized if normalized else fallback_services

    # =========================================================================
    # DNS Configuration
    # =========================================================================

    async def get_dns_config(self) -> dict:
        """Get DNS server configuration."""
        result = await self._request("GET", "/control/dns_info")
        return result or {}

    async def get_full_dns_config(self) -> dict:
        """Get comprehensive DNS configuration including DNSSEC, cache, and blocking mode."""
        result = await self._request("GET", "/control/dns_info")
        if not result:
            return {}

        return {
            "dnssec_enabled": result.get("dnssec_enabled", False),
            "cache_size": result.get("cache_size", 4194304),  # Default 4MB
            "cache_ttl_min": result.get("cache_ttl_min", 0),
            "cache_ttl_max": result.get("cache_ttl_max", 86400),
            "cache_optimistic": result.get("cache_optimistic", False),
            "blocking_mode": result.get("blocking_mode", "default"),
            "blocking_ipv4": result.get("blocking_ipv4", ""),
            "blocking_ipv6": result.get("blocking_ipv6", ""),
            "edns_cs_enabled": result.get("edns_cs_enabled", False),
            "edns_cs_use_custom": result.get("edns_cs_use_custom", False),
            "edns_cs_custom_ip": result.get("edns_cs_custom_ip", ""),
            "disable_ipv6": result.get("disable_ipv6", False),
            "upstream_dns": result.get("upstream_dns", []),
            "bootstrap_dns": result.get("bootstrap_dns", []),
            "ratelimit": result.get("ratelimit", 0),
        }

    async def set_dns_server_config(self, config: dict) -> bool:
        """Update DNS server configuration (DNSSEC, cache, blocking mode, etc.).

        Args:
            config: Dictionary with configuration options. Valid keys:
                - dnssec_enabled: bool
                - cache_size: int (bytes)
                - cache_ttl_min: int (seconds)
                - cache_ttl_max: int (seconds)
                - cache_optimistic: bool
                - blocking_mode: str ("default", "refused", "nxdomain", "null_ip", "custom_ip")
                - blocking_ipv4: str (IP address for custom_ip mode)
                - blocking_ipv6: str (IP address for custom_ip mode)
                - disable_ipv6: bool
                - ratelimit: int (queries per second, 0 = unlimited)

        Returns:
            True if successful, False otherwise.
        """
        result = await self._request("POST", "/control/dns_config", config)
        return result is not None

    async def get_safesearch_config(self) -> dict:
        """Get per-engine safe search configuration."""
        result = await self._request("GET", "/control/safesearch/status")
        if not result:
            return {"enabled": False}

        return {
            "enabled": result.get("enabled", False),
            "bing": result.get("bing", True),
            "duckduckgo": result.get("duckduckgo", True),
            "google": result.get("google", True),
            "pixabay": result.get("pixabay", True),
            "yandex": result.get("yandex", True),
            "youtube": result.get("youtube", True),
        }

    async def set_safesearch_config(self, config: dict) -> bool:
        """Set per-engine safe search configuration.

        Args:
            config: Dictionary with safe search options:
                - enabled: bool (master toggle)
                - google: bool
                - bing: bool
                - youtube: bool
                - duckduckgo: bool
                - yandex: bool
                - pixabay: bool

        Returns:
            True if successful, False otherwise.
        """
        result = await self._request("PUT", "/control/safesearch/settings", config)
        return result is not None

    async def get_querylog_config(self) -> dict:
        """Get query log configuration."""
        result = await self._request("GET", "/control/querylog/config")
        if not result:
            return {}

        return {
            "enabled": result.get("enabled", True),
            "interval": result.get("interval", 2160),  # Default 90 days in hours
            "anonymize_client_ip": result.get("anonymize_client_ip", False),
            "ignored": result.get("ignored", []),
        }

    async def set_querylog_config(self, config: dict) -> bool:
        """Set query log configuration.

        Args:
            config: Dictionary with query log options:
                - enabled: bool
                - interval: int (retention in hours: 1, 24, 168, 720, 2160)
                - anonymize_client_ip: bool
                - ignored: list[str] (domains to ignore)

        Returns:
            True if successful, False otherwise.
        """
        result = await self._request("PUT", "/control/querylog/config/update", config)
        return result is not None

    async def set_upstream_dns(self, upstreams: list[str], bootstrap: list[str] = None) -> bool:
        """Set upstream DNS servers."""
        config = {"upstream_dns": upstreams}
        if bootstrap:
            config["bootstrap_dns"] = bootstrap
        result = await self._request("POST", "/control/dns_config", json=config)
        return result is not None

    # =========================================================================
    # Domain Lookup
    # =========================================================================

    async def lookup_domain(self, domain: str) -> dict:
        """Look up a domain and check if it would be blocked."""
        # Check against custom rules
        rules = await self.get_custom_rules()
        is_blocked = any(domain in r and not r.startswith("@@") for r in rules)
        is_allowed = any(domain in r and r.startswith("@@") for r in rules)

        # Check filtering status
        filtering = await self.get_filtering_status()
        filters = filtering.get("filters", [])

        return {
            "domain": domain,
            "is_blocked": is_blocked and not is_allowed,
            "is_allowed": is_allowed,
            "in_custom_rules": is_blocked or is_allowed,
            "active_filters_count": len([f for f in filters if f.get("enabled")]),
        }

    # =========================================================================
    # Database Operations
    # =========================================================================

    async def sync_blocklists_to_db(self, db: Session) -> None:
        """Sync blocklists from AdGuard to database."""
        filtering = await self.get_filtering_status()
        filters = filtering.get("filters", [])

        for f in filters:
            existing = db.query(DnsBlocklist).filter_by(url=f.get("url")).first()
            if existing:
                existing.name = f.get("name", existing.name)
                existing.rules_count = f.get("rules_count", 0)
                existing.enabled = f.get("enabled", True)
                existing.last_updated = datetime.utcnow()
            else:
                blocklist = DnsBlocklist(
                    name=f.get("name", ""),
                    url=f.get("url", ""),
                    enabled=f.get("enabled", True),
                    rules_count=f.get("rules_count", 0),
                    last_updated=datetime.utcnow(),
                )
                db.add(blocklist)
        db.commit()

    async def sync_clients_to_db(self, db: Session) -> int:
        """Sync clients from AdGuard stats to database.

        Uses top_clients from stats (actual DNS query sources) rather than
        auto_clients (ARP/hosts discovery) to get real client activity.

        Returns:
            Number of clients synced.
        """
        stats = await self.get_stats()
        top_clients = stats.get("top_clients", [])

        count = 0
        for client_data in top_clients:
            # AdGuard uses "domain" key for client IP in top_clients
            ip = client_data.get("domain", "")
            if not ip:
                continue

            query_count = client_data.get("count", 0)

            existing = db.query(DnsClient).filter_by(client_id=ip).first()
            if existing:
                existing.queries_count = query_count
                existing.last_seen = datetime.utcnow()
            else:
                dns_client = DnsClient(
                    client_id=ip,
                    ip_addresses=[ip],
                    queries_count=query_count,
                    last_seen=datetime.utcnow(),
                )
                db.add(dns_client)
            count += 1

        db.commit()
        logger.info("clients_synced_from_stats", count=count)
        return count

    async def aggregate_client_stats(self, db: Session, hours: int = 24) -> int:
        """Aggregate query counts per client from stored query logs.

        This provides more accurate per-client statistics including blocked
        counts, which aren't available from the top_clients stats.

        Args:
            db: Database session
            hours: Hours of query log history to aggregate

        Returns:
            Number of clients updated.
        """
        cutoff = datetime.utcnow() - timedelta(hours=hours)

        # Aggregate query counts per client from query log
        results = (
            db.query(
                DnsQueryLog.client_ip,
                func.count().label("total"),
                func.sum(case((DnsQueryLog.status == "blocked", 1), else_=0)).label("blocked"),
            )
            .filter(DnsQueryLog.timestamp >= cutoff)
            .group_by(DnsQueryLog.client_ip)
            .all()
        )

        count = 0
        for client_ip, total, blocked in results:
            if not client_ip:
                continue

            blocked_count = blocked or 0

            client = db.query(DnsClient).filter_by(client_id=client_ip).first()
            if client:
                client.queries_count = total
                client.blocked_count = blocked_count
                client.last_seen = datetime.utcnow()
            else:
                # Create new client from query activity
                db.add(
                    DnsClient(
                        client_id=client_ip,
                        ip_addresses=[client_ip],
                        queries_count=total,
                        blocked_count=blocked_count,
                        last_seen=datetime.utcnow(),
                    )
                )
            count += 1

        db.commit()
        logger.info("client_stats_aggregated", clients=count, hours=hours)
        return count

    async def sync_query_log_to_db(self, db: Session, limit: int = 1000) -> int:
        """Sync recent query log entries to database."""
        entries = await self.get_query_log(limit=limit)
        count = 0

        for entry in entries:
            try:
                timestamp = datetime.fromisoformat(entry["timestamp"].replace("Z", "+00:00"))
            except (ValueError, KeyError):
                timestamp = datetime.utcnow()

            # Check if already exists (by timestamp and domain)
            existing = (
                db.query(DnsQueryLog)
                .filter_by(timestamp=timestamp, domain=entry.get("domain", ""))
                .first()
            )
            if not existing:
                log_entry = DnsQueryLog(
                    timestamp=timestamp,
                    client_ip=entry.get("client_ip", ""),
                    domain=entry.get("domain", ""),
                    query_type=entry.get("query_type", ""),
                    status=entry.get("status", "allowed"),
                    block_reason=entry.get("block_reason"),
                    upstream=entry.get("upstream"),
                    response_time_ms=entry.get("response_time_ms"),
                    cached=entry.get("cached", False),
                )
                db.add(log_entry)
                count += 1

        db.commit()
        return count

    async def aggregate_stats(self, db: Session) -> None:
        """Aggregate hourly statistics from raw query log.

        Computes actual hourly stats from dns_query_log table, not AdGuard cumulative totals.
        """
        hour_timestamp = datetime.utcnow().replace(minute=0, second=0, microsecond=0)
        hour_start = hour_timestamp
        hour_end = hour_timestamp + timedelta(hours=1)

        # Compute stats from raw query log for this hour
        total_queries = (
            db.query(func.count(DnsQueryLog.id))
            .filter(DnsQueryLog.timestamp >= hour_start)
            .filter(DnsQueryLog.timestamp < hour_end)
            .scalar()
        ) or 0

        if total_queries == 0:
            # No queries this hour, skip
            return

        blocked_queries = (
            db.query(func.count(DnsQueryLog.id))
            .filter(DnsQueryLog.timestamp >= hour_start)
            .filter(DnsQueryLog.timestamp < hour_end)
            .filter(DnsQueryLog.status == "blocked")
            .scalar()
        ) or 0

        cached_queries = (
            db.query(func.count(DnsQueryLog.id))
            .filter(DnsQueryLog.timestamp >= hour_start)
            .filter(DnsQueryLog.timestamp < hour_end)
            .filter(DnsQueryLog.cached.is_(True))
            .scalar()
        ) or 0

        avg_response_time = (
            db.query(func.avg(DnsQueryLog.response_time_ms))
            .filter(DnsQueryLog.timestamp >= hour_start)
            .filter(DnsQueryLog.timestamp < hour_end)
            .filter(DnsQueryLog.response_time_ms.isnot(None))
            .scalar()
        ) or 0

        # Top domains for this hour
        top_domains_query = (
            db.query(DnsQueryLog.domain, func.count(DnsQueryLog.id).label("count"))
            .filter(DnsQueryLog.timestamp >= hour_start)
            .filter(DnsQueryLog.timestamp < hour_end)
            .group_by(DnsQueryLog.domain)
            .order_by(func.count(DnsQueryLog.id).desc())
            .limit(10)
            .all()
        )
        top_domains = [{"domain": d, "count": c} for d, c in top_domains_query]

        # Top blocked domains for this hour
        top_blocked_query = (
            db.query(DnsQueryLog.domain, func.count(DnsQueryLog.id).label("count"))
            .filter(DnsQueryLog.timestamp >= hour_start)
            .filter(DnsQueryLog.timestamp < hour_end)
            .filter(DnsQueryLog.status == "blocked")
            .group_by(DnsQueryLog.domain)
            .order_by(func.count(DnsQueryLog.id).desc())
            .limit(10)
            .all()
        )
        top_blocked = [{"domain": d, "count": c} for d, c in top_blocked_query]

        # Top clients for this hour
        top_clients_query = (
            db.query(DnsQueryLog.client_ip, func.count(DnsQueryLog.id).label("count"))
            .filter(DnsQueryLog.timestamp >= hour_start)
            .filter(DnsQueryLog.timestamp < hour_end)
            .group_by(DnsQueryLog.client_ip)
            .order_by(func.count(DnsQueryLog.id).desc())
            .limit(10)
            .all()
        )
        top_clients = [{"domain": ip, "count": c} for ip, c in top_clients_query]

        # Upsert the hourly stats
        existing = (
            db.query(DnsStats)
            .filter(DnsStats.timestamp == hour_timestamp)
            .filter(DnsStats.period == "hour")
            .first()
        )

        if existing:
            existing.total_queries = total_queries
            existing.blocked_queries = blocked_queries
            existing.cached_queries = cached_queries
            existing.avg_response_time = round(avg_response_time, 2) if avg_response_time else 0
            existing.top_domains = top_domains
            existing.top_blocked = top_blocked
            existing.top_clients = top_clients
        else:
            stat_record = DnsStats(
                timestamp=hour_timestamp,
                period="hour",
                total_queries=total_queries,
                blocked_queries=blocked_queries,
                cached_queries=cached_queries,
                avg_response_time=round(avg_response_time, 2) if avg_response_time else 0,
                top_domains=top_domains,
                top_blocked=top_blocked,
                top_clients=top_clients,
            )
            db.add(stat_record)

        db.commit()
        logger.info(
            "hourly_stats_aggregated",
            hour=hour_timestamp.isoformat(),
            total=total_queries,
            blocked=blocked_queries,
        )

    # =========================================================================
    # Setup & Initialization
    # =========================================================================

    async def setup_default_blocklists(self) -> dict:
        """Set up default blocklists on first run."""
        added = []
        errors = []

        for blocklist in DEFAULT_BLOCKLISTS:
            try:
                success = await self.add_filter_url(
                    name=blocklist["name"],
                    url=blocklist["url"],
                )
                if success:
                    added.append(blocklist["name"])
                else:
                    errors.append(blocklist["name"])
            except Exception as e:
                logger.error(
                    "blocklist_add_error",
                    name=blocklist["name"],
                    error=str(e),
                )
                errors.append(blocklist["name"])

        return {"added": added, "errors": errors}


# Global instance
dns_service = DnsService()
