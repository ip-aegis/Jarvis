"""
DNS Analytics Background Tasks.

Runs detection loops, generates alerts, and enriches data with LLM analysis.
"""

import asyncio
import uuid
from datetime import datetime, timedelta
from typing import Optional

import structlog
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import DnsClient, DnsQueryLog, DnsSecurityAlert

logger = structlog.get_logger()


class DnsAnalyticsProcessor:
    """Background processor for DNS analytics and threat detection."""

    def __init__(
        self,
        analysis_interval: int = 30,  # seconds
        baseline_interval: int = 3600,  # 1 hour
        reputation_interval: int = 300,  # 5 minutes
        enrichment_interval: int = 60,  # 1 minute
    ):
        self._analysis_interval = analysis_interval
        self._baseline_interval = baseline_interval
        self._reputation_interval = reputation_interval
        self._enrichment_interval = enrichment_interval
        self._running = False
        self._tasks: list[asyncio.Task] = []
        self._alert_callback = None

    def set_alert_callback(self, callback):
        """Set callback function for new alerts (for WebSocket broadcasting)."""
        self._alert_callback = callback

    async def start(self):
        """Start all analytics background loops."""
        if self._running:
            logger.warning("analytics_processor_already_running")
            return

        self._running = True
        logger.info("starting_dns_analytics_processor")

        # Start background tasks
        self._tasks = [
            asyncio.create_task(self._real_time_analysis_loop()),
            asyncio.create_task(self._baseline_update_loop()),
            asyncio.create_task(self._reputation_scoring_loop()),
            asyncio.create_task(self._alert_enrichment_loop()),
        ]

    async def stop(self):
        """Stop all background tasks."""
        self._running = False
        for task in self._tasks:
            task.cancel()
        self._tasks = []
        logger.info("dns_analytics_processor_stopped")

    async def _real_time_analysis_loop(self):
        """
        Analyze recent queries for threats.
        Runs every 30 seconds.
        """
        logger.info("starting_real_time_analysis_loop", interval=self._analysis_interval)

        while self._running:
            try:
                await self._run_threat_detection()
            except Exception as e:
                logger.error("real_time_analysis_error", error=str(e))

            await asyncio.sleep(self._analysis_interval)

    async def _run_threat_detection(self):
        """Run threat detection on recent queries."""
        from app.services.dns_advanced_detection import get_detection_service
        from app.services.dns_client_profiling import get_profiling_service

        db = SessionLocal()
        try:
            detection = get_detection_service()
            profiling = get_profiling_service()

            # Get queries from last analysis window
            cutoff = datetime.utcnow() - timedelta(seconds=self._analysis_interval * 2)
            recent_queries = db.query(DnsQueryLog).filter(DnsQueryLog.timestamp >= cutoff).all()

            if not recent_queries:
                return

            # Track new alerts
            new_alerts = []

            # Analyze unique domains for DGA
            unique_domains = set(q.domain for q in recent_queries)
            for domain in unique_domains:
                dga_result = detection.detect_dga(domain)
                if dga_result["is_dga"] and dga_result["confidence"] > 0.7:
                    # Get associated client
                    client_queries = [q for q in recent_queries if q.domain == domain]
                    client_ips = set(q.client_ip for q in client_queries)

                    for client_ip in client_ips:
                        alert = await self._create_alert(
                            db=db,
                            alert_type="dga",
                            severity="high" if dga_result["confidence"] > 0.85 else "medium",
                            client_ip=client_ip,
                            domain=domain,
                            title=f"Possible DGA domain detected: {domain}",
                            description=f"Domain {domain} has characteristics of a Domain Generation Algorithm (entropy: {dga_result['metrics']['entropy']:.2f}, consonant ratio: {dga_result['metrics']['consonant_ratio']:.2f})",
                            raw_data=dga_result,
                        )
                        if alert:
                            new_alerts.append(alert)

            # Analyze clients for tunneling
            client_ips = set(q.client_ip for q in recent_queries)
            for client_ip in client_ips:
                tunneling_results = detection.detect_tunneling(client_ip, window_hours=1)
                for tunnel in tunneling_results:
                    if tunnel["confidence"] > 0.6:
                        alert = await self._create_alert(
                            db=db,
                            alert_type="tunneling",
                            severity="high" if tunnel["confidence"] > 0.8 else "medium",
                            client_ip=client_ip,
                            domain=tunnel["base_domain"],
                            title=f"Possible DNS tunneling to {tunnel['base_domain']}",
                            description=f"Client {client_ip} is making suspicious queries to {tunnel['base_domain']} with characteristics of DNS tunneling",
                            raw_data=tunnel,
                        )
                        if alert:
                            new_alerts.append(alert)

                # Check for behavioral anomalies
                anomalies = await profiling.detect_behavioral_anomaly(client_ip)
                for anomaly in anomalies:
                    if anomaly["severity"] in ["medium", "high"]:
                        alert = await self._create_alert(
                            db=db,
                            alert_type="behavioral",
                            severity=anomaly["severity"],
                            client_ip=client_ip,
                            domain=None,
                            title=f"Behavioral anomaly: {anomaly['type']}",
                            description=anomaly["description"],
                            raw_data=anomaly,
                        )
                        if alert:
                            new_alerts.append(alert)

            # Broadcast new alerts
            if new_alerts and self._alert_callback:
                for alert in new_alerts:
                    await self._alert_callback(alert)

            if new_alerts:
                logger.info("threats_detected", count=len(new_alerts))

        finally:
            db.close()

    async def _create_alert(
        self,
        db: Session,
        alert_type: str,
        severity: str,
        client_ip: str,
        domain: Optional[str],
        title: str,
        description: str,
        raw_data: dict,
    ) -> Optional[DnsSecurityAlert]:
        """Create a new security alert if not duplicate."""
        # Check for recent similar alert (deduplication)
        cutoff = datetime.utcnow() - timedelta(hours=1)
        existing = (
            db.query(DnsSecurityAlert)
            .filter(DnsSecurityAlert.alert_type == alert_type)
            .filter(DnsSecurityAlert.client_ip == client_ip)
            .filter(DnsSecurityAlert.domain == domain)
            .filter(DnsSecurityAlert.timestamp >= cutoff)
            .first()
        )

        if existing:
            return None  # Duplicate alert

        alert = DnsSecurityAlert(
            alert_id=uuid.uuid4(),
            timestamp=datetime.utcnow(),
            alert_type=alert_type,
            severity=severity,
            client_ip=client_ip,
            domain=domain,
            title=title,
            description=description,
            raw_data=raw_data,
            status="open",
            created_at=datetime.utcnow(),
        )

        db.add(alert)
        db.commit()
        db.refresh(alert)

        logger.info(
            "alert_created",
            alert_id=str(alert.alert_id),
            alert_type=alert_type,
            severity=severity,
            client_ip=client_ip,
            domain=domain,
        )

        # Update client risk level
        client = db.query(DnsClient).filter(DnsClient.client_id == client_ip).first()
        if client:
            client.last_anomaly_at = datetime.utcnow()
            client.anomaly_count_24h = (client.anomaly_count_24h or 0) + 1
            if severity == "high":
                client.risk_level = "high"
            elif severity == "medium" and client.risk_level != "high":
                client.risk_level = "medium"
            db.commit()

        return alert

    async def _baseline_update_loop(self):
        """
        Update client behavioral baselines.
        Runs every hour.
        """
        logger.info("starting_baseline_update_loop", interval=self._baseline_interval)

        while self._running:
            try:
                await self._update_baselines()
            except Exception as e:
                logger.error("baseline_update_error", error=str(e))

            await asyncio.sleep(self._baseline_interval)

    async def _update_baselines(self):
        """Update baselines for clients."""
        from app.services.dns_client_profiling import get_profiling_service

        db = SessionLocal()
        try:
            profiling = get_profiling_service()

            # Get clients needing baseline
            clients_needing = profiling.get_all_clients_needing_baseline(limit=10)

            for client_ip in clients_needing:
                try:
                    await profiling.build_baseline(client_ip, days=7)
                    logger.info("baseline_built", client_ip=client_ip)
                except Exception as e:
                    logger.error("baseline_build_failed", client_ip=client_ip, error=str(e))

            # Incrementally update existing baselines
            cutoff = datetime.utcnow() - timedelta(hours=24)
            active_clients = (
                db.query(DnsClient.client_id)
                .filter(DnsClient.last_seen >= cutoff)
                .filter(DnsClient.has_profile == True)
                .limit(20)
                .all()
            )

            for (client_ip,) in active_clients:
                try:
                    await profiling.update_baseline_incremental(client_ip)
                except Exception as e:
                    logger.error("baseline_update_failed", client_ip=client_ip, error=str(e))

        finally:
            db.close()

    async def _reputation_scoring_loop(self):
        """
        Score new domains.
        Runs every 5 minutes.
        """
        logger.info("starting_reputation_scoring_loop", interval=self._reputation_interval)

        while self._running:
            try:
                await self._score_new_domains()
            except Exception as e:
                logger.error("reputation_scoring_error", error=str(e))

            await asyncio.sleep(self._reputation_interval)

    async def _score_new_domains(self):
        """Score domains that haven't been scored yet."""
        from app.models import DnsDomainReputation
        from app.services.dns_domain_reputation import get_reputation_service

        db = SessionLocal()
        try:
            reputation = get_reputation_service()

            # Get recent domains not yet scored
            cutoff = datetime.utcnow() - timedelta(minutes=10)
            recent_domains = (
                db.query(DnsQueryLog.domain)
                .filter(DnsQueryLog.timestamp >= cutoff)
                .distinct()
                .limit(100)
                .all()
            )

            for (domain,) in recent_domains:
                # Check if already scored
                existing = (
                    db.query(DnsDomainReputation)
                    .filter(DnsDomainReputation.domain == domain)
                    .first()
                )

                if not existing:
                    reputation.get_or_create_reputation(domain)

        finally:
            db.close()

    async def _alert_enrichment_loop(self):
        """
        Enrich alerts with LLM analysis.
        Runs every minute.
        """
        logger.info("starting_alert_enrichment_loop", interval=self._enrichment_interval)

        while self._running:
            try:
                await self._enrich_alerts()
            except Exception as e:
                logger.error("alert_enrichment_error", error=str(e))

            await asyncio.sleep(self._enrichment_interval)

    async def _enrich_alerts(self):
        """Enrich alerts that don't have LLM analysis."""
        from app.services.dns_llm_analysis import get_llm_analysis_service

        db = SessionLocal()
        try:
            llm_service = get_llm_analysis_service()

            # Get alerts without LLM analysis
            unenriched_alerts = (
                db.query(DnsSecurityAlert)
                .filter(DnsSecurityAlert.llm_analysis == None)
                .filter(DnsSecurityAlert.status == "open")
                .order_by(DnsSecurityAlert.timestamp.desc())
                .limit(5)  # Process a few at a time
                .all()
            )

            for alert in unenriched_alerts:
                try:
                    analysis = await llm_service.analyze_threat(alert)

                    # Update alert with analysis
                    alert.llm_analysis = analysis.get("explanation", "")
                    alert.remediation = "\n".join(analysis.get("remediation", []))
                    alert.confidence = analysis.get("confidence", 0.5)
                    alert.updated_at = datetime.utcnow()

                    db.commit()
                    logger.info("alert_enriched", alert_id=str(alert.alert_id))

                except Exception as e:
                    logger.error(
                        "alert_enrichment_failed", alert_id=str(alert.alert_id), error=str(e)
                    )

        finally:
            db.close()


# Singleton processor
_analytics_processor: Optional[DnsAnalyticsProcessor] = None


def get_analytics_processor() -> DnsAnalyticsProcessor:
    """Get or create the singleton analytics processor."""
    global _analytics_processor
    if _analytics_processor is None:
        _analytics_processor = DnsAnalyticsProcessor()
    return _analytics_processor


async def start_analytics_tasks():
    """Start the analytics background processor."""
    processor = get_analytics_processor()
    await processor.start()


async def stop_analytics_tasks():
    """Stop the analytics background processor."""
    processor = get_analytics_processor()
    await processor.stop()
