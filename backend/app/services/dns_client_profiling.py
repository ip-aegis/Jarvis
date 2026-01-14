"""
DNS Client Profiling Service.

Learns behavioral baselines for DNS clients and detects anomalies.
"""

import statistics
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import Optional

import structlog
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import DnsClient, DnsClientProfile, DnsQueryLog, DnsSecurityAlert

logger = structlog.get_logger()

# Device type patterns based on query behavior
DEVICE_TYPE_PATTERNS = {
    "iot": {
        "description": "IoT devices have predictable, repetitive query patterns",
        "indicators": {
            "low_domain_diversity": True,  # Few unique domains
            "regular_intervals": True,  # Queries at consistent intervals
            "limited_query_types": True,  # Mostly A records
        },
    },
    "mobile": {
        "description": "Mobile devices have diverse queries with app-specific patterns",
        "indicators": {
            "high_domain_diversity": True,
            "app_domains": True,  # cdn, analytics, push notifications
            "bursty_traffic": True,  # Activity comes in bursts
        },
    },
    "desktop": {
        "description": "Desktops have varied patterns with web browsing",
        "indicators": {
            "high_domain_diversity": True,
            "web_patterns": True,  # Mix of sites
            "longer_sessions": True,
        },
    },
    "server": {
        "description": "Servers have programmatic, service-focused queries",
        "indicators": {
            "specific_services": True,  # API endpoints, databases
            "24_7_activity": True,
            "low_human_domains": True,  # No social media, news, etc.
        },
    },
}


class DnsClientProfilingService:
    """Learns and tracks behavioral patterns for DNS clients."""

    def __init__(self, db: Session = None):
        self._db = db

    @property
    def db(self) -> Session:
        if self._db is None:
            self._db = SessionLocal()
        return self._db

    async def build_baseline(self, client_ip: str, days: int = 7) -> Optional[DnsClientProfile]:
        """
        Build behavioral baseline from historical query data.

        Analyzes the last N days of queries to establish:
        - Typical query rate per hour
        - Domain frequency distribution
        - Hour-of-day patterns
        - Query type distribution
        """
        cutoff = datetime.utcnow() - timedelta(days=days)

        # Get all queries for this client in the time period
        queries = (
            self.db.query(DnsQueryLog)
            .filter(DnsQueryLog.client_ip == client_ip)
            .filter(DnsQueryLog.timestamp >= cutoff)
            .order_by(DnsQueryLog.timestamp)
            .all()
        )

        if len(queries) < 100:
            logger.info(
                "insufficient_data_for_baseline",
                client_ip=client_ip,
                query_count=len(queries),
            )
            return None

        # Calculate hourly query rates
        hourly_counts = defaultdict(int)
        for q in queries:
            hour_key = q.timestamp.replace(minute=0, second=0, microsecond=0)
            hourly_counts[hour_key] += 1

        hourly_rates = list(hourly_counts.values())
        avg_rate = statistics.mean(hourly_rates) if hourly_rates else 0
        std_dev = statistics.stdev(hourly_rates) if len(hourly_rates) > 1 else 0
        max_rate = max(hourly_rates) if hourly_rates else 0

        # Calculate hour-of-day distribution
        hour_distribution = defaultdict(int)
        for q in queries:
            hour_distribution[str(q.timestamp.hour)] += 1

        # Calculate domain frequency
        domain_counts = Counter(q.domain for q in queries)
        top_domains = {}
        for domain, count in domain_counts.most_common(50):
            domain_hourly_avg = count / (days * 24)
            top_domains[domain] = {
                "total_count": count,
                "hourly_avg": round(domain_hourly_avg, 2),
            }

        # Calculate query type distribution
        query_types = Counter(q.query_type for q in queries if q.query_type)
        total_typed = sum(query_types.values())
        type_percentages = {
            qt: round((count / total_typed) * 100, 1) for qt, count in query_types.items()
        }

        # Infer device type
        device_type, confidence = self._infer_device_type(
            domain_counts, hour_distribution, query_types, avg_rate
        )

        # Get or create profile
        profile = (
            self.db.query(DnsClientProfile).filter(DnsClientProfile.client_id == client_ip).first()
        )

        if not profile:
            profile = DnsClientProfile(
                client_id=client_ip,
                created_at=datetime.utcnow(),
            )
            self.db.add(profile)

        # Update profile
        profile.baseline_domains = top_domains
        profile.typical_query_hours = dict(hour_distribution)
        profile.typical_query_types = type_percentages
        profile.normal_query_rate_per_hour = round(avg_rate, 2)
        profile.query_rate_std_dev = round(std_dev, 2)
        profile.max_query_rate_observed = max_rate
        profile.baseline_generated_at = datetime.utcnow()
        profile.baseline_data_points = len(queries)
        profile.baseline_days_analyzed = days
        profile.device_type_inference = device_type
        profile.device_type_confidence = confidence
        profile.updated_at = datetime.utcnow()

        # Update client record
        client = self.db.query(DnsClient).filter(DnsClient.client_id == client_ip).first()
        if client:
            client.has_profile = True

        self.db.commit()

        logger.info(
            "baseline_built",
            client_ip=client_ip,
            query_count=len(queries),
            avg_rate=avg_rate,
            device_type=device_type,
        )

        return profile

    def _infer_device_type(
        self,
        domain_counts: Counter,
        hour_distribution: dict,
        query_types: Counter,
        avg_rate: float,
    ) -> tuple[str, float]:
        """Infer device type from query patterns."""
        scores = {"iot": 0.0, "mobile": 0.0, "desktop": 0.0, "server": 0.0}

        # Domain diversity
        unique_domains = len(domain_counts)
        total_queries = sum(domain_counts.values())
        diversity_ratio = unique_domains / max(total_queries, 1)

        if diversity_ratio < 0.05:  # Very few unique domains
            scores["iot"] += 0.4
            scores["server"] += 0.2
        elif diversity_ratio > 0.3:  # Many unique domains
            scores["desktop"] += 0.3
            scores["mobile"] += 0.3

        # Hour distribution (24/7 activity suggests server/IoT)
        active_hours = sum(1 for h, c in hour_distribution.items() if c > avg_rate * 0.1)
        if active_hours >= 20:  # Active almost all hours
            scores["server"] += 0.3
            scores["iot"] += 0.2
        elif active_hours < 12:  # Active fewer hours
            scores["desktop"] += 0.2
            scores["mobile"] += 0.2

        # Query types (servers often have more diverse types)
        if len(query_types) > 3:
            scores["server"] += 0.2
        if query_types.get("A", 0) > 0.9 * sum(query_types.values()):
            scores["iot"] += 0.2

        # Check for mobile-specific patterns
        mobile_indicators = ["apple", "google", "facebook", "push", "notification"]
        mobile_domain_count = sum(
            count
            for domain, count in domain_counts.items()
            if any(ind in domain.lower() for ind in mobile_indicators)
        )
        if mobile_domain_count > total_queries * 0.2:
            scores["mobile"] += 0.3

        # Find highest score
        best_type = max(scores, key=scores.get)
        confidence = scores[best_type] / max(sum(scores.values()), 0.1)

        return best_type, round(min(confidence, 1.0), 2)

    async def detect_behavioral_anomaly(
        self, client_ip: str, window_minutes: int = 30
    ) -> list[dict]:
        """
        Compare recent behavior against baseline to detect anomalies.

        Returns list of anomaly dicts with details.
        """
        anomalies = []

        # Get profile
        profile = (
            self.db.query(DnsClientProfile).filter(DnsClientProfile.client_id == client_ip).first()
        )

        if not profile or not profile.baseline_generated_at:
            return []

        # Get recent queries
        cutoff = datetime.utcnow() - timedelta(minutes=window_minutes)
        recent_queries = (
            self.db.query(DnsQueryLog)
            .filter(DnsQueryLog.client_ip == client_ip)
            .filter(DnsQueryLog.timestamp >= cutoff)
            .all()
        )

        if not recent_queries:
            return []

        # Check 1: Query rate anomaly
        recent_rate = len(recent_queries) / (window_minutes / 60)  # Per hour
        expected_rate = profile.normal_query_rate_per_hour or 0
        std_dev = profile.query_rate_std_dev or 1
        sensitivity = profile.anomaly_sensitivity or 2.0

        if expected_rate > 0 and std_dev > 0:
            deviation = (recent_rate - expected_rate) / std_dev
            if deviation > sensitivity:
                anomalies.append(
                    {
                        "type": "query_rate_spike",
                        "severity": "high" if deviation > sensitivity * 2 else "medium",
                        "current_rate": round(recent_rate, 1),
                        "expected_rate": round(expected_rate, 1),
                        "deviation_std": round(deviation, 2),
                        "description": f"Query rate {recent_rate:.0f}/hr is {deviation:.1f} std dev above normal ({expected_rate:.0f}/hr)",
                    }
                )

        # Check 2: New domain access
        baseline_domains = (
            set(profile.baseline_domains.keys()) if profile.baseline_domains else set()
        )
        recent_domains = set(q.domain for q in recent_queries)
        new_domains = recent_domains - baseline_domains

        # Filter to significant new domains (queried multiple times)
        new_domain_counts = Counter(q.domain for q in recent_queries if q.domain in new_domains)
        significant_new = {d: c for d, c in new_domain_counts.items() if c >= 3}

        if len(significant_new) > 10:  # Many new domains
            anomalies.append(
                {
                    "type": "new_domain_burst",
                    "severity": "medium",
                    "new_domain_count": len(significant_new),
                    "sample_domains": list(significant_new.keys())[:10],
                    "description": f"Client accessing {len(significant_new)} new domains not in baseline",
                }
            )

        # Check 3: Hour-of-day anomaly
        current_hour = str(datetime.utcnow().hour)
        typical_hours = profile.typical_query_hours or {}
        typical_for_hour = typical_hours.get(current_hour, 0)
        total_typical = sum(typical_hours.values()) if typical_hours else 1

        if total_typical > 0:
            expected_ratio = typical_for_hour / total_typical
            if expected_ratio < 0.01 and len(recent_queries) > 20:
                anomalies.append(
                    {
                        "type": "unusual_time_activity",
                        "severity": "low",
                        "current_hour": current_hour,
                        "query_count": len(recent_queries),
                        "description": f"Unusual activity at hour {current_hour} - typically inactive at this time",
                    }
                )

        # Check 4: Query type anomaly
        recent_types = Counter(q.query_type for q in recent_queries if q.query_type)
        typical_types = profile.typical_query_types or {}

        for qtype, count in recent_types.items():
            typical_pct = typical_types.get(qtype, 0)
            recent_pct = (count / len(recent_queries)) * 100

            # Alert if query type is much more prevalent than usual
            if recent_pct > 50 and typical_pct < 10:
                anomalies.append(
                    {
                        "type": "query_type_anomaly",
                        "severity": "medium" if qtype in ["TXT", "NULL"] else "low",
                        "query_type": qtype,
                        "recent_percentage": round(recent_pct, 1),
                        "typical_percentage": round(typical_pct, 1),
                        "description": f"Unusual spike in {qtype} queries ({recent_pct:.0f}% vs typical {typical_pct:.0f}%)",
                    }
                )

        return anomalies

    async def update_baseline_incremental(self, client_ip: str):
        """Incrementally update baseline with recent data using exponential moving average."""
        profile = (
            self.db.query(DnsClientProfile).filter(DnsClientProfile.client_id == client_ip).first()
        )

        if not profile:
            return

        # Get queries from last hour
        cutoff = datetime.utcnow() - timedelta(hours=1)
        recent_queries = (
            self.db.query(DnsQueryLog)
            .filter(DnsQueryLog.client_ip == client_ip)
            .filter(DnsQueryLog.timestamp >= cutoff)
            .all()
        )

        if not recent_queries:
            return

        # Exponential moving average weight
        alpha = 0.1  # Give 10% weight to new data

        # Update query rate (EMA)
        recent_rate = len(recent_queries)
        if profile.normal_query_rate_per_hour:
            new_rate = alpha * recent_rate + (1 - alpha) * profile.normal_query_rate_per_hour
            profile.normal_query_rate_per_hour = round(new_rate, 2)

        # Update max observed
        if profile.max_query_rate_observed is None or recent_rate > profile.max_query_rate_observed:
            profile.max_query_rate_observed = recent_rate

        profile.updated_at = datetime.utcnow()
        self.db.commit()

    def get_client_risk_assessment(self, client_ip: str) -> dict:
        """Get comprehensive risk assessment for a client."""
        profile = (
            self.db.query(DnsClientProfile).filter(DnsClientProfile.client_id == client_ip).first()
        )

        client = self.db.query(DnsClient).filter(DnsClient.client_id == client_ip).first()

        # Count recent alerts
        alert_cutoff = datetime.utcnow() - timedelta(hours=24)
        recent_alerts = (
            self.db.query(DnsSecurityAlert)
            .filter(DnsSecurityAlert.client_ip == client_ip)
            .filter(DnsSecurityAlert.timestamp >= alert_cutoff)
            .count()
        )

        # Calculate risk level
        risk_score = 0
        risk_factors = []

        if recent_alerts > 0:
            risk_score += min(50, recent_alerts * 10)
            risk_factors.append(f"{recent_alerts} alerts in last 24h")

        if profile:
            if profile.device_type_inference == "iot":
                risk_score += 10  # IoT devices are often targeted
                risk_factors.append("IoT device (higher risk profile)")

        # Determine risk level
        if risk_score >= 50:
            risk_level = "high"
        elif risk_score >= 25:
            risk_level = "medium"
        else:
            risk_level = "low"

        return {
            "client_ip": client_ip,
            "client_name": client.name if client else None,
            "risk_level": risk_level,
            "risk_score": risk_score,
            "risk_factors": risk_factors,
            "device_type": profile.device_type_inference if profile else None,
            "device_confidence": profile.device_type_confidence if profile else None,
            "has_baseline": profile is not None and profile.baseline_generated_at is not None,
            "baseline_age_hours": (
                (datetime.utcnow() - profile.baseline_generated_at).total_seconds() / 3600
                if profile and profile.baseline_generated_at
                else None
            ),
            "recent_alert_count": recent_alerts,
        }

    def get_all_clients_needing_baseline(self, limit: int = 50) -> list[str]:
        """Get list of clients that need baseline building."""
        # Get clients without profiles
        clients_without = (
            self.db.query(DnsClient.client_id)
            .outerjoin(DnsClientProfile, DnsClient.client_id == DnsClientProfile.client_id)
            .filter(DnsClientProfile.id == None)
            .limit(limit)
            .all()
        )

        return [c.client_id for c in clients_without]


# Singleton instance
_profiling_service: Optional[DnsClientProfilingService] = None


def get_profiling_service() -> DnsClientProfilingService:
    """Get or create the singleton profiling service."""
    global _profiling_service
    if _profiling_service is None:
        _profiling_service = DnsClientProfilingService()
    return _profiling_service
