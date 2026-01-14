"""
DNS Domain Reputation Service.

Scores domains based on entropy, age, TLD, patterns, and other factors.
"""

import math
import re
from datetime import datetime
from typing import Optional

import structlog
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import DnsDomainReputation

logger = structlog.get_logger()

# TLD reputation scores (positive = trusted, negative = suspicious)
TLD_SCORES = {
    # Highly trusted
    "gov": 15,
    "edu": 15,
    "mil": 15,
    # Trusted commercial
    "com": 0,
    "org": 0,
    "net": 0,
    "io": 0,
    "co": 0,
    # Country codes (generally trusted)
    "uk": 0,
    "de": 0,
    "fr": 0,
    "jp": 0,
    "au": 0,
    "ca": 0,
    # Newer/cheap TLDs (slightly suspicious)
    "xyz": -5,
    "top": -5,
    "online": -5,
    "site": -5,
    "club": -5,
    "info": -5,
    "biz": -5,
    # Known abuse TLDs
    "tk": -15,
    "ml": -15,
    "ga": -15,
    "cf": -15,
    "gq": -15,
    "work": -10,
    "click": -10,
    "link": -10,
    "loan": -10,
    "download": -10,
}

# Known trusted domains (CDNs, major services)
TRUSTED_DOMAINS = {
    "google.com",
    "googleapis.com",
    "gstatic.com",
    "youtube.com",
    "cloudflare.com",
    "cloudflare-dns.com",
    "amazon.com",
    "amazonaws.com",
    "microsoft.com",
    "windows.com",
    "apple.com",
    "icloud.com",
    "facebook.com",
    "fbcdn.net",
    "twitter.com",
    "github.com",
    "githubusercontent.com",
    "akamai.net",
    "akamaiedge.net",
    "fastly.net",
    "cloudfront.net",
}

# Suspicious patterns
SUSPICIOUS_PATTERNS = [
    r"^[0-9a-f]{32,}",  # Long hex strings
    r"^[a-z]{20,}$",  # Very long random-looking strings
    r"\d{5,}",  # Many consecutive digits
    r"[a-z]\d[a-z]\d[a-z]\d",  # Alternating letters and digits
    r"^xn--",  # Punycode (can be legitimate but often abuse)
]


class DnsDomainReputationService:
    """Scores domains based on multiple reputation factors."""

    def __init__(self, db: Session = None):
        self._db = db
        self._suspicious_patterns = [re.compile(p) for p in SUSPICIOUS_PATTERNS]

    @property
    def db(self) -> Session:
        if self._db is None:
            self._db = SessionLocal()
        return self._db

    def calculate_entropy(self, domain: str) -> float:
        """
        Calculate Shannon entropy of domain name.
        Higher entropy = more random-looking = potentially suspicious.
        """
        # Remove TLD for entropy calculation
        parts = domain.split(".")
        if len(parts) > 1:
            name = ".".join(parts[:-1])
        else:
            name = domain

        if not name:
            return 0.0

        # Calculate character frequency
        freq = {}
        for char in name.lower():
            freq[char] = freq.get(char, 0) + 1

        # Calculate entropy
        entropy = 0.0
        length = len(name)
        for count in freq.values():
            p = count / length
            entropy -= p * math.log2(p)

        return round(entropy, 3)

    def calculate_consonant_ratio(self, domain: str) -> float:
        """Calculate ratio of consonants to total letters (DGA indicator)."""
        vowels = set("aeiou")
        consonants = set("bcdfghjklmnpqrstvwxyz")

        # Remove TLD
        parts = domain.split(".")
        name = parts[0] if parts else domain

        letters = [c for c in name.lower() if c.isalpha()]
        if not letters:
            return 0.0

        consonant_count = sum(1 for c in letters if c in consonants)
        return round(consonant_count / len(letters), 3)

    def calculate_digit_ratio(self, domain: str) -> float:
        """Calculate ratio of digits in domain name."""
        parts = domain.split(".")
        name = parts[0] if parts else domain

        if not name:
            return 0.0

        digit_count = sum(1 for c in name if c.isdigit())
        return round(digit_count / len(name), 3)

    def get_tld_score(self, domain: str) -> int:
        """Get reputation score based on TLD."""
        tld = domain.split(".")[-1].lower()
        return TLD_SCORES.get(tld, 0)

    def has_suspicious_patterns(self, domain: str) -> bool:
        """Check if domain matches suspicious patterns."""
        name = domain.split(".")[0].lower()
        for pattern in self._suspicious_patterns:
            if pattern.search(name):
                return True
        return False

    def is_trusted_domain(self, domain: str) -> bool:
        """Check if domain is in the trusted list."""
        domain_lower = domain.lower()

        # Check exact match
        if domain_lower in TRUSTED_DOMAINS:
            return True

        # Check if it's a subdomain of a trusted domain
        for trusted in TRUSTED_DOMAINS:
            if domain_lower.endswith("." + trusted):
                return True

        return False

    def get_subdomain_depth(self, domain: str) -> int:
        """Get the number of subdomains (suspicious if very deep)."""
        return len(domain.split(".")) - 1

    def calculate_domain_score(self, domain: str) -> dict:
        """
        Calculate comprehensive reputation score for a domain.

        Returns dict with:
        - reputation_score: 0-100 (100 = fully trusted)
        - entropy_score: Shannon entropy
        - threat_indicators: DGA score, tunneling indicators
        - factors: Breakdown of scoring factors
        """
        domain = domain.lower().strip()

        # Start with base score of 70 (neutral)
        score = 70.0
        factors = {}

        # Check trusted domains first
        if self.is_trusted_domain(domain):
            return {
                "reputation_score": 95.0,
                "entropy_score": self.calculate_entropy(domain),
                "threat_indicators": {"dga_score": 0.0, "tunneling_score": 0.0},
                "factors": {"trusted_domain": True},
                "category": "trusted",
            }

        # Entropy scoring (0-30 point penalty for high entropy)
        entropy = self.calculate_entropy(domain)
        if entropy > 4.5:
            penalty = min(30, (entropy - 4.5) * 20)
            score -= penalty
            factors["entropy_penalty"] = -penalty
        elif entropy < 2.5:
            # Very low entropy is actually suspicious too (repetitive)
            score -= 5
            factors["low_entropy_penalty"] = -5

        # Consonant ratio (DGA indicator)
        consonant_ratio = self.calculate_consonant_ratio(domain)
        if consonant_ratio > 0.75:
            penalty = min(20, (consonant_ratio - 0.75) * 80)
            score -= penalty
            factors["consonant_ratio_penalty"] = -penalty

        # Digit ratio
        digit_ratio = self.calculate_digit_ratio(domain)
        if digit_ratio > 0.3:
            penalty = min(15, (digit_ratio - 0.3) * 50)
            score -= penalty
            factors["digit_ratio_penalty"] = -penalty

        # TLD reputation
        tld_score = self.get_tld_score(domain)
        score += tld_score
        factors["tld_adjustment"] = tld_score

        # Suspicious patterns
        if self.has_suspicious_patterns(domain):
            score -= 15
            factors["suspicious_pattern"] = -15

        # Subdomain depth
        depth = self.get_subdomain_depth(domain)
        if depth > 4:
            penalty = min(10, (depth - 4) * 3)
            score -= penalty
            factors["deep_subdomain"] = -penalty

        # Domain length
        name_length = len(domain.split(".")[0])
        if name_length > 30:
            score -= 10
            factors["long_name"] = -10
        elif name_length < 3:
            score -= 5
            factors["short_name"] = -5

        # Calculate DGA score (0-1, higher = more likely DGA)
        dga_score = 0.0
        if entropy > 4.0:
            dga_score += (entropy - 4.0) * 0.2
        if consonant_ratio > 0.7:
            dga_score += (consonant_ratio - 0.7) * 1.0
        if digit_ratio > 0.2:
            dga_score += digit_ratio * 0.5
        dga_score = min(1.0, dga_score)

        # Calculate tunneling score (based on subdomain patterns)
        tunneling_score = 0.0
        subdomain = domain.split(".")[0]
        if len(subdomain) > 50:
            tunneling_score += 0.5
        if entropy > 4.5 and depth > 2:
            tunneling_score += 0.3
        tunneling_score = min(1.0, tunneling_score)

        # Clamp score to 0-100
        score = max(0, min(100, score))

        return {
            "reputation_score": round(score, 1),
            "entropy_score": entropy,
            "threat_indicators": {
                "dga_score": round(dga_score, 3),
                "tunneling_score": round(tunneling_score, 3),
                "consonant_ratio": consonant_ratio,
                "digit_ratio": digit_ratio,
            },
            "factors": factors,
            "category": self._infer_category(domain, score),
        }

    def _infer_category(self, domain: str, score: float) -> str:
        """Infer domain category based on patterns."""
        domain_lower = domain.lower()

        # CDN patterns
        cdn_patterns = [
            "cdn",
            "static",
            "assets",
            "cache",
            "edge",
            "akamai",
            "cloudflare",
            "fastly",
        ]
        if any(p in domain_lower for p in cdn_patterns):
            return "cdn"

        # Advertising patterns
        ad_patterns = ["ads", "adserver", "doubleclick", "adsense", "advertising", "adnxs", "ad."]
        if any(p in domain_lower for p in ad_patterns):
            return "advertising"

        # Tracking patterns
        track_patterns = ["track", "analytics", "pixel", "beacon", "collect", "telemetry"]
        if any(p in domain_lower for p in track_patterns):
            return "tracking"

        # Social media
        social_patterns = ["facebook", "twitter", "instagram", "linkedin", "tiktok", "snapchat"]
        if any(p in domain_lower for p in social_patterns):
            return "social"

        # Streaming
        stream_patterns = ["youtube", "netflix", "spotify", "twitch", "stream", "video"]
        if any(p in domain_lower for p in stream_patterns):
            return "streaming"

        # Based on score
        if score < 30:
            return "suspicious"
        elif score > 80:
            return "trusted"
        else:
            return "unknown"

    def get_or_create_reputation(self, domain: str) -> DnsDomainReputation:
        """Get existing reputation or create new one."""
        domain = domain.lower().strip()

        # Check cache first
        existing = (
            self.db.query(DnsDomainReputation).filter(DnsDomainReputation.domain == domain).first()
        )

        if existing:
            # Update last_seen and query_count
            existing.last_seen = datetime.utcnow()
            existing.query_count = (existing.query_count or 0) + 1
            self.db.commit()
            return existing

        # Calculate reputation
        result = self.calculate_domain_score(domain)

        # Create new record
        reputation = DnsDomainReputation(
            domain=domain,
            reputation_score=result["reputation_score"],
            entropy_score=result["entropy_score"],
            category=result["category"],
            category_confidence=0.7 if result["category"] != "unknown" else 0.3,
            category_source="heuristic",
            threat_indicators=result["threat_indicators"],
            first_seen=datetime.utcnow(),
            last_seen=datetime.utcnow(),
            query_count=1,
            unique_clients=1,
        )

        try:
            self.db.add(reputation)
            self.db.commit()
            self.db.refresh(reputation)
        except Exception as e:
            self.db.rollback()
            logger.error("failed_to_create_reputation", domain=domain, error=str(e))
            # Return calculated result even if DB fails
            return reputation

        return reputation

    def update_reputation_stats(self, domain: str, client_ip: str):
        """Update query statistics for a domain."""
        reputation = self.get_or_create_reputation(domain)

        # Update unique clients count (simplified - just increment periodically)
        # In production, would track unique IPs properly
        reputation.query_count = (reputation.query_count or 0) + 1
        reputation.last_seen = datetime.utcnow()

        self.db.commit()

    def get_suspicious_domains(self, threshold: float = 50.0, limit: int = 100) -> list:
        """Get domains with reputation below threshold."""
        return (
            self.db.query(DnsDomainReputation)
            .filter(DnsDomainReputation.reputation_score < threshold)
            .order_by(DnsDomainReputation.reputation_score.asc())
            .limit(limit)
            .all()
        )

    def bulk_score_domains(self, domains: list[str]) -> dict[str, dict]:
        """Score multiple domains efficiently."""
        results = {}
        for domain in domains:
            results[domain] = self.calculate_domain_score(domain)
        return results


# Singleton instance
_reputation_service: Optional[DnsDomainReputationService] = None


def get_reputation_service() -> DnsDomainReputationService:
    """Get or create the singleton reputation service."""
    global _reputation_service
    if _reputation_service is None:
        _reputation_service = DnsDomainReputationService()
    return _reputation_service
