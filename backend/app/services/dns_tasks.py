"""Background tasks for DNS log sync, stats aggregation, and anomaly detection."""

import asyncio
from datetime import datetime, timedelta
from typing import Any, Optional

from app.core.logging import get_logger
from app.database import SessionLocal
from app.models import DnsQueryLog

logger = get_logger(__name__)


class DnsBackgroundProcessor:
    """Background processor for DNS analytics and sync.

    Handles:
    - Syncing query logs from AdGuard Home
    - Aggregating hourly/daily statistics
    - Updating blocklists
    - Detecting DNS anomalies (DGA, tunneling, etc.)
    """

    def __init__(
        self,
        sync_interval: int = 60,
        stats_interval: int = 3600,
        blocklist_interval: int = 86400,
    ):
        """Initialize processor.

        Args:
            sync_interval: Seconds between query log syncs (default: 60).
            stats_interval: Seconds between stats aggregation (default: 3600 = 1 hour).
            blocklist_interval: Seconds between blocklist updates (default: 86400 = 24 hours).
        """
        self._sync_interval = sync_interval
        self._stats_interval = stats_interval
        self._blocklist_interval = blocklist_interval
        self._running = False
        self._last_sync: Optional[datetime] = None
        self._last_stats: Optional[datetime] = None
        self._last_blocklist_update: Optional[datetime] = None

    async def start(self):
        """Start the background processing loops."""
        if self._running:
            return

        self._running = True
        logger.info(
            "dns_processor_started",
            sync_interval=self._sync_interval,
            stats_interval=self._stats_interval,
        )

        # Start all processing tasks
        asyncio.create_task(self._sync_loop())
        asyncio.create_task(self._stats_loop())
        asyncio.create_task(self._blocklist_loop())

    async def stop(self):
        """Stop all background processing loops."""
        self._running = False
        logger.info("dns_processor_stopped")

    async def _sync_loop(self):
        """Query log sync loop."""
        while self._running:
            try:
                await self._sync_query_log()
                self._last_sync = datetime.utcnow()
            except Exception as e:
                logger.error("dns_sync_loop_error", error=str(e))

            await asyncio.sleep(self._sync_interval)

    async def _stats_loop(self):
        """Statistics aggregation loop."""
        while self._running:
            try:
                await self._aggregate_stats()
                self._last_stats = datetime.utcnow()
            except Exception as e:
                logger.error("dns_stats_loop_error", error=str(e))

            await asyncio.sleep(self._stats_interval)

    async def _blocklist_loop(self):
        """Blocklist update loop."""
        while self._running:
            try:
                await self._update_blocklists()
                self._last_blocklist_update = datetime.utcnow()
            except Exception as e:
                logger.error("dns_blocklist_loop_error", error=str(e))

            await asyncio.sleep(self._blocklist_interval)

    async def _sync_query_log(self):
        """Sync query logs from AdGuard to database."""
        from app.services.dns import dns_service

        db = SessionLocal()
        try:
            count = await dns_service.sync_query_log_to_db(db, limit=500)
            if count > 0:
                logger.info("dns_query_log_synced", entries=count)
        finally:
            db.close()

    async def _aggregate_stats(self):
        """Aggregate hourly DNS statistics."""
        from app.services.dns import dns_service

        db = SessionLocal()
        try:
            await dns_service.aggregate_stats(db)
            logger.info("dns_stats_aggregated")
        finally:
            db.close()

    async def _update_blocklists(self):
        """Check and update blocklists."""
        from app.services.dns import dns_service

        try:
            success = await dns_service.refresh_filters()
            if success:
                logger.info("dns_blocklists_refreshed")

            # Sync to database
            db = SessionLocal()
            try:
                await dns_service.sync_blocklists_to_db(db)
            finally:
                db.close()
        except Exception as e:
            logger.error("dns_blocklist_update_error", error=str(e))

    async def detect_anomalies(self) -> list[dict[str, Any]]:
        """Detect DNS anomalies like DGA domains or tunneling attempts.

        Returns:
            List of detected anomalies.
        """
        db = SessionLocal()
        anomalies = []

        try:
            # Get recent query logs
            cutoff = datetime.utcnow() - timedelta(hours=1)
            recent_logs = db.query(DnsQueryLog).filter(DnsQueryLog.timestamp >= cutoff).all()

            # Analyze for patterns
            client_domains: dict[str, list[str]] = {}
            for log in recent_logs:
                if log.client_ip not in client_domains:
                    client_domains[log.client_ip] = []
                client_domains[log.client_ip].append(log.domain)

            for client_ip, domains in client_domains.items():
                # Check for DGA-like patterns (high entropy, random-looking domains)
                suspicious_domains = self._detect_dga_domains(domains)
                if suspicious_domains:
                    anomalies.append(
                        {
                            "type": "possible_dga",
                            "client_ip": client_ip,
                            "domains": suspicious_domains[:10],
                            "count": len(suspicious_domains),
                            "severity": "high" if len(suspicious_domains) > 20 else "medium",
                        }
                    )

                # Check for DNS tunneling (high volume to single domain)
                tunneling = self._detect_tunneling(domains)
                if tunneling:
                    anomalies.append(
                        {
                            "type": "possible_tunneling",
                            "client_ip": client_ip,
                            "domain": tunneling["domain"],
                            "query_count": tunneling["count"],
                            "severity": "high",
                        }
                    )

            if anomalies:
                logger.warning(
                    "dns_anomalies_detected",
                    count=len(anomalies),
                    types=[a["type"] for a in anomalies],
                )

        finally:
            db.close()

        return anomalies

    def _detect_dga_domains(self, domains: list[str]) -> list[str]:
        """Detect domains that look like DGA (Domain Generation Algorithm) output.

        Simple heuristics:
        - High ratio of consonants
        - No recognizable words
        - Long random-looking subdomains
        """
        suspicious = []
        vowels = set("aeiou")

        for domain in set(domains):
            # Extract subdomain part
            parts = domain.split(".")
            if len(parts) < 2:
                continue

            subdomain = parts[0]
            if len(subdomain) < 8:
                continue

            # Calculate consonant ratio
            consonant_count = sum(1 for c in subdomain.lower() if c.isalpha() and c not in vowels)
            if len(subdomain) > 0:
                consonant_ratio = consonant_count / len(subdomain)
                if consonant_ratio > 0.7:
                    suspicious.append(domain)
                    continue

            # Check for digit-heavy subdomains
            digit_count = sum(1 for c in subdomain if c.isdigit())
            if len(subdomain) > 0 and digit_count / len(subdomain) > 0.4:
                suspicious.append(domain)

        return suspicious

    def _detect_tunneling(self, domains: list[str]) -> Optional[dict]:
        """Detect possible DNS tunneling.

        Signs:
        - Very high query rate to same base domain
        - Long subdomain labels (data encoding)
        """
        from collections import Counter

        # Extract base domains
        base_domains = []
        for domain in domains:
            parts = domain.split(".")
            if len(parts) >= 2:
                base_domain = ".".join(parts[-2:])
                base_domains.append(base_domain)

        # Count queries per base domain
        counts = Counter(base_domains)
        for domain, count in counts.most_common(5):
            # Threshold: more than 100 queries to same domain in 1 hour
            if count > 100:
                return {"domain": domain, "count": count}

        return None

    def get_status(self) -> dict[str, Any]:
        """Get processor status."""
        return {
            "running": self._running,
            "last_sync": self._last_sync.isoformat() if self._last_sync else None,
            "last_stats": self._last_stats.isoformat() if self._last_stats else None,
            "last_blocklist_update": (
                self._last_blocklist_update.isoformat() if self._last_blocklist_update else None
            ),
            "intervals": {
                "sync": self._sync_interval,
                "stats": self._stats_interval,
                "blocklist": self._blocklist_interval,
            },
        }


# Singleton instance
dns_processor = DnsBackgroundProcessor()


async def start_dns_tasks():
    """Start DNS background tasks."""
    await dns_processor.start()


async def stop_dns_tasks():
    """Stop DNS background tasks."""
    await dns_processor.stop()
