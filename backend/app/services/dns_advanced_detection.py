"""
DNS Advanced Detection Service.

Implements advanced threat detection algorithms:
- DGA (Domain Generation Algorithm) detection
- DNS tunneling detection
- Fast-flux network detection
"""

import math
import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import Optional

import structlog
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import DnsQueryLog
from app.services.dns_domain_reputation import DnsDomainReputationService

logger = structlog.get_logger()

# Detection thresholds (configurable)
DGA_ENTROPY_THRESHOLD = 4.2
DGA_CONSONANT_THRESHOLD = 0.70
DGA_DIGIT_THRESHOLD = 0.30

TUNNELING_SUBDOMAIN_LENGTH_THRESHOLD = 30
TUNNELING_QUERY_RATE_THRESHOLD = 100  # Per hour to same base domain
TUNNELING_TXT_RATIO_THRESHOLD = 0.5

FAST_FLUX_IP_DIVERSITY_THRESHOLD = 10  # Unique IPs in 1 hour
FAST_FLUX_TTL_THRESHOLD = 300  # Seconds


class DnsAdvancedDetectionService:
    """Advanced threat detection for DNS patterns."""

    def __init__(self, db: Session = None):
        self._db = db
        self._reputation_service = None

    @property
    def db(self) -> Session:
        if self._db is None:
            self._db = SessionLocal()
        return self._db

    @property
    def reputation_service(self) -> DnsDomainReputationService:
        if self._reputation_service is None:
            self._reputation_service = DnsDomainReputationService(self.db)
        return self._reputation_service

    # =========================================================================
    # DGA Detection
    # =========================================================================

    def detect_dga(self, domain: str) -> dict:
        """
        Detect Domain Generation Algorithm patterns using entropy and character analysis.

        Returns dict with:
        - is_dga: bool
        - confidence: 0-1
        - indicators: dict of specific indicators
        """
        # Get base metrics from reputation service
        entropy = self.reputation_service.calculate_entropy(domain)
        consonant_ratio = self.reputation_service.calculate_consonant_ratio(domain)
        digit_ratio = self.reputation_service.calculate_digit_ratio(domain)

        # Calculate n-gram analysis for additional signal
        ngram_score = self._calculate_ngram_score(domain)

        # Calculate DGA probability
        dga_score = 0.0
        indicators = {}

        # Entropy component (0-0.4)
        if entropy > DGA_ENTROPY_THRESHOLD:
            entropy_contribution = min(0.4, (entropy - DGA_ENTROPY_THRESHOLD) * 0.2)
            dga_score += entropy_contribution
            indicators["high_entropy"] = {
                "value": entropy,
                "threshold": DGA_ENTROPY_THRESHOLD,
                "contribution": entropy_contribution,
            }

        # Consonant ratio component (0-0.3)
        if consonant_ratio > DGA_CONSONANT_THRESHOLD:
            consonant_contribution = min(0.3, (consonant_ratio - DGA_CONSONANT_THRESHOLD) * 1.0)
            dga_score += consonant_contribution
            indicators["high_consonant_ratio"] = {
                "value": consonant_ratio,
                "threshold": DGA_CONSONANT_THRESHOLD,
                "contribution": consonant_contribution,
            }

        # Digit ratio component (0-0.2)
        if digit_ratio > DGA_DIGIT_THRESHOLD:
            digit_contribution = min(0.2, digit_ratio * 0.5)
            dga_score += digit_contribution
            indicators["high_digit_ratio"] = {
                "value": digit_ratio,
                "threshold": DGA_DIGIT_THRESHOLD,
                "contribution": digit_contribution,
            }

        # N-gram component (0-0.1)
        if ngram_score < 0.3:  # Low n-gram score = unusual character patterns
            ngram_contribution = (0.3 - ngram_score) * 0.33
            dga_score += ngram_contribution
            indicators["unusual_ngrams"] = {
                "value": ngram_score,
                "contribution": ngram_contribution,
            }

        # Check for known DGA patterns
        if self._matches_dga_patterns(domain):
            dga_score += 0.15
            indicators["pattern_match"] = True

        is_dga = dga_score >= 0.5
        confidence = min(1.0, dga_score)

        return {
            "is_dga": is_dga,
            "confidence": round(confidence, 3),
            "dga_score": round(dga_score, 3),
            "indicators": indicators,
            "metrics": {
                "entropy": entropy,
                "consonant_ratio": consonant_ratio,
                "digit_ratio": digit_ratio,
                "ngram_score": ngram_score,
            },
        }

    def _calculate_ngram_score(self, domain: str) -> float:
        """
        Calculate how 'normal' the character n-grams are.
        Lower score = more unusual patterns.
        """
        # Common English bigrams
        common_bigrams = {
            "th",
            "he",
            "in",
            "er",
            "an",
            "re",
            "on",
            "at",
            "en",
            "nd",
            "st",
            "es",
            "ed",
            "to",
            "it",
            "ou",
            "ea",
            "hi",
            "is",
            "or",
            "ti",
            "as",
            "te",
            "et",
            "ng",
            "of",
            "al",
            "de",
            "se",
            "le",
        }

        name = domain.split(".")[0].lower()
        if len(name) < 2:
            return 0.5

        # Extract bigrams
        bigrams = [name[i : i + 2] for i in range(len(name) - 1)]
        if not bigrams:
            return 0.5

        # Count common bigrams
        common_count = sum(1 for bg in bigrams if bg in common_bigrams)
        return common_count / len(bigrams)

    def _matches_dga_patterns(self, domain: str) -> bool:
        """Check if domain matches known DGA patterns."""
        name = domain.split(".")[0].lower()

        # Pattern 1: Alternating consonants and vowels in unnatural way
        if re.match(r"^[bcdfghjklmnpqrstvwxyz]{3,}[aeiou][bcdfghjklmnpqrstvwxyz]{3,}$", name):
            return True

        # Pattern 2: Hex-like strings
        if re.match(r"^[0-9a-f]{16,}$", name):
            return True

        # Pattern 3: Base64-like strings
        if re.match(r"^[A-Za-z0-9+/]{20,}$", name):
            return True

        return False

    def detect_dga_batch(self, domains: list[str]) -> list[dict]:
        """Detect DGA in batch of domains."""
        results = []
        for domain in domains:
            result = self.detect_dga(domain)
            if result["is_dga"]:
                results.append({"domain": domain, **result})
        return results

    # =========================================================================
    # DNS Tunneling Detection
    # =========================================================================

    def detect_tunneling(self, client_ip: str, window_hours: int = 1) -> list[dict]:
        """
        Detect DNS tunneling by analyzing query patterns.

        Tunneling indicators:
        - Very long subdomains (data encoded in DNS queries)
        - High query rate to same base domain
        - High proportion of TXT/NULL records
        - Unique subdomain patterns
        """
        cutoff = datetime.utcnow() - timedelta(hours=window_hours)

        # Get recent queries
        queries = (
            self.db.query(DnsQueryLog)
            .filter(DnsQueryLog.client_ip == client_ip)
            .filter(DnsQueryLog.timestamp >= cutoff)
            .all()
        )

        if not queries:
            return []

        # Group queries by base domain
        domain_groups = defaultdict(list)
        for q in queries:
            parts = q.domain.split(".")
            if len(parts) >= 2:
                base_domain = ".".join(parts[-2:])
                domain_groups[base_domain].append(q)

        tunneling_detections = []

        for base_domain, domain_queries in domain_groups.items():
            if len(domain_queries) < 10:  # Not enough data
                continue

            # Calculate metrics
            subdomains = [q.domain.split(".")[0] for q in domain_queries]
            avg_subdomain_len = sum(len(s) for s in subdomains) / len(subdomains)
            unique_subdomains = len(set(subdomains))
            query_rate = len(domain_queries)  # Per window

            # TXT record ratio
            txt_count = sum(1 for q in domain_queries if q.query_type == "TXT")
            txt_ratio = txt_count / len(domain_queries)

            # Calculate tunneling score
            tunneling_score = 0.0
            indicators = {}

            # Long subdomains (primary indicator)
            if avg_subdomain_len > TUNNELING_SUBDOMAIN_LENGTH_THRESHOLD:
                contribution = min(
                    0.4, (avg_subdomain_len - TUNNELING_SUBDOMAIN_LENGTH_THRESHOLD) / 50
                )
                tunneling_score += contribution
                indicators["long_subdomains"] = {
                    "avg_length": round(avg_subdomain_len, 1),
                    "threshold": TUNNELING_SUBDOMAIN_LENGTH_THRESHOLD,
                }

            # High query rate
            if query_rate > TUNNELING_QUERY_RATE_THRESHOLD:
                contribution = min(0.3, (query_rate - TUNNELING_QUERY_RATE_THRESHOLD) / 200)
                tunneling_score += contribution
                indicators["high_query_rate"] = {
                    "rate": query_rate,
                    "threshold": TUNNELING_QUERY_RATE_THRESHOLD,
                }

            # High unique subdomain ratio
            uniqueness_ratio = unique_subdomains / len(domain_queries)
            if uniqueness_ratio > 0.8:  # Many unique subdomains
                contribution = 0.2 * uniqueness_ratio
                tunneling_score += contribution
                indicators["high_uniqueness"] = {
                    "unique_count": unique_subdomains,
                    "total_count": len(domain_queries),
                    "ratio": round(uniqueness_ratio, 2),
                }

            # TXT record ratio
            if txt_ratio > TUNNELING_TXT_RATIO_THRESHOLD:
                contribution = 0.2 * txt_ratio
                tunneling_score += contribution
                indicators["high_txt_ratio"] = {
                    "ratio": round(txt_ratio, 2),
                    "threshold": TUNNELING_TXT_RATIO_THRESHOLD,
                }

            # Entropy of subdomains (encoded data has high entropy)
            subdomain_entropy = self._calculate_batch_entropy(subdomains)
            if subdomain_entropy > 4.0:
                contribution = min(0.15, (subdomain_entropy - 4.0) * 0.1)
                tunneling_score += contribution
                indicators["high_subdomain_entropy"] = {
                    "entropy": round(subdomain_entropy, 2),
                }

            if tunneling_score >= 0.5:
                tunneling_detections.append(
                    {
                        "is_tunneling": True,
                        "confidence": round(min(1.0, tunneling_score), 3),
                        "base_domain": base_domain,
                        "client_ip": client_ip,
                        "indicators": indicators,
                        "metrics": {
                            "avg_subdomain_length": round(avg_subdomain_len, 1),
                            "unique_subdomains": unique_subdomains,
                            "query_count": len(domain_queries),
                            "txt_ratio": round(txt_ratio, 2),
                        },
                        "sample_queries": [q.domain for q in domain_queries[:5]],
                    }
                )

        return tunneling_detections

    def _calculate_batch_entropy(self, strings: list[str]) -> float:
        """Calculate average entropy across multiple strings."""
        if not strings:
            return 0.0

        total_entropy = 0.0
        for s in strings:
            if len(s) > 1:
                freq = Counter(s.lower())
                entropy = -sum((c / len(s)) * math.log2(c / len(s)) for c in freq.values())
                total_entropy += entropy

        return total_entropy / len(strings)

    # =========================================================================
    # Fast-Flux Detection
    # =========================================================================

    def detect_fast_flux(self, domain: str, window_hours: int = 1) -> dict:
        """
        Detect fast-flux networks by analyzing IP diversity and TTL patterns.

        Fast-flux indicators:
        - Rapidly changing IP addresses
        - Very low TTLs
        - Geographic distribution of IPs
        """
        cutoff = datetime.utcnow() - timedelta(hours=window_hours)

        # Get recent queries for this domain with responses
        queries = (
            self.db.query(DnsQueryLog)
            .filter(DnsQueryLog.domain == domain)
            .filter(DnsQueryLog.timestamp >= cutoff)
            .filter(DnsQueryLog.response_ip != None)
            .all()
        )

        if len(queries) < 5:
            return {
                "is_fast_flux": False,
                "confidence": 0.0,
                "reason": "insufficient_data",
            }

        # Analyze IP diversity
        response_ips = [q.response_ip for q in queries if q.response_ip]
        unique_ips = set(response_ips)

        # Note: We don't have TTL in the current schema, so we'll use other metrics
        fast_flux_score = 0.0
        indicators = {}

        # IP diversity check
        if len(unique_ips) >= FAST_FLUX_IP_DIVERSITY_THRESHOLD:
            diversity_contribution = min(0.5, len(unique_ips) / 20)
            fast_flux_score += diversity_contribution
            indicators["high_ip_diversity"] = {
                "unique_ips": len(unique_ips),
                "threshold": FAST_FLUX_IP_DIVERSITY_THRESHOLD,
                "sample_ips": list(unique_ips)[:10],
            }

        # IP change frequency
        ip_changes = sum(
            1 for i in range(1, len(response_ips)) if response_ips[i] != response_ips[i - 1]
        )
        change_ratio = ip_changes / max(len(response_ips) - 1, 1)

        if change_ratio > 0.5:  # IPs changing frequently
            fast_flux_score += 0.3 * change_ratio
            indicators["frequent_ip_changes"] = {
                "change_ratio": round(change_ratio, 2),
                "total_changes": ip_changes,
            }

        # Check if IPs are from different subnets
        subnets = set()
        for ip in unique_ips:
            parts = ip.split(".")
            if len(parts) >= 3:
                subnets.add(".".join(parts[:3]))

        if len(subnets) >= 5:
            fast_flux_score += 0.2
            indicators["subnet_diversity"] = {
                "unique_subnets": len(subnets),
                "sample_subnets": list(subnets)[:5],
            }

        is_fast_flux = fast_flux_score >= 0.5

        return {
            "is_fast_flux": is_fast_flux,
            "confidence": round(min(1.0, fast_flux_score), 3),
            "domain": domain,
            "indicators": indicators,
            "metrics": {
                "unique_ip_count": len(unique_ips),
                "ip_change_ratio": round(change_ratio, 2),
                "unique_subnets": len(subnets),
                "query_count": len(queries),
            },
        }

    # =========================================================================
    # Comprehensive Analysis
    # =========================================================================

    def analyze_query(self, query: DnsQueryLog) -> dict:
        """
        Run all detection algorithms on a single query.

        Returns combined analysis results.
        """
        results = {
            "domain": query.domain,
            "client_ip": query.client_ip,
            "timestamp": query.timestamp.isoformat(),
            "threats_detected": [],
        }

        # DGA detection
        dga_result = self.detect_dga(query.domain)
        if dga_result["is_dga"]:
            results["threats_detected"].append(
                {
                    "type": "dga",
                    "severity": "high" if dga_result["confidence"] > 0.8 else "medium",
                    "confidence": dga_result["confidence"],
                    "details": dga_result,
                }
            )

        # Add reputation score
        rep_result = self.reputation_service.calculate_domain_score(query.domain)
        results["reputation"] = rep_result

        if rep_result["reputation_score"] < 30:
            results["threats_detected"].append(
                {
                    "type": "low_reputation",
                    "severity": "medium",
                    "confidence": 1 - (rep_result["reputation_score"] / 100),
                    "details": rep_result,
                }
            )

        return results

    def run_full_analysis(self, client_ip: str = None, hours: int = 1) -> dict:
        """
        Run comprehensive analysis on recent DNS activity.

        Returns summary of all detected threats.
        """
        cutoff = datetime.utcnow() - timedelta(hours=hours)

        query = self.db.query(DnsQueryLog).filter(DnsQueryLog.timestamp >= cutoff)
        if client_ip:
            query = query.filter(DnsQueryLog.client_ip == client_ip)

        queries = query.all()

        results = {
            "analysis_window_hours": hours,
            "total_queries_analyzed": len(queries),
            "dga_detections": [],
            "tunneling_detections": [],
            "fast_flux_detections": [],
            "low_reputation_domains": [],
        }

        # Analyze unique domains for DGA
        unique_domains = set(q.domain for q in queries)
        for domain in unique_domains:
            dga_result = self.detect_dga(domain)
            if dga_result["is_dga"]:
                results["dga_detections"].append(
                    {
                        "domain": domain,
                        **dga_result,
                    }
                )

            # Check reputation
            rep = self.reputation_service.calculate_domain_score(domain)
            if rep["reputation_score"] < 40:
                results["low_reputation_domains"].append(
                    {
                        "domain": domain,
                        **rep,
                    }
                )

        # Analyze tunneling per client
        client_ips = set(q.client_ip for q in queries)
        for cip in client_ips:
            tunneling_results = self.detect_tunneling(cip, window_hours=hours)
            results["tunneling_detections"].extend(tunneling_results)

        # Check domains with multiple responses for fast-flux
        domain_query_counts = Counter(q.domain for q in queries)
        for domain, count in domain_query_counts.most_common(20):
            if count >= 5:
                ff_result = self.detect_fast_flux(domain, window_hours=hours)
                if ff_result["is_fast_flux"]:
                    results["fast_flux_detections"].append(ff_result)

        # Summary statistics
        results["summary"] = {
            "dga_count": len(results["dga_detections"]),
            "tunneling_count": len(results["tunneling_detections"]),
            "fast_flux_count": len(results["fast_flux_detections"]),
            "low_reputation_count": len(results["low_reputation_domains"]),
            "total_threats": (
                len(results["dga_detections"])
                + len(results["tunneling_detections"])
                + len(results["fast_flux_detections"])
            ),
        }

        return results


# Singleton instance
_detection_service: Optional[DnsAdvancedDetectionService] = None


def get_detection_service() -> DnsAdvancedDetectionService:
    """Get or create the singleton detection service."""
    global _detection_service
    if _detection_service is None:
        _detection_service = DnsAdvancedDetectionService()
    return _detection_service
