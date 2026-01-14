"""
DNS LLM Analysis Service.

Provides natural language threat analysis and explanations using LLM.
"""

import json
import uuid
from datetime import datetime, timedelta
from typing import Optional

import structlog
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import DnsSecurityAlert, DnsThreatAnalysis
from app.services.llm_usage import log_llm_usage
from app.services.openai_service import OpenAIService

logger = structlog.get_logger()

# Prompt templates
THREAT_ANALYSIS_PROMPT = """You are a DNS security analyst. Analyze the following DNS security alert and provide:

1. **Threat Assessment**: Rate the threat level (high/medium/low/none)
2. **Classification**: What type of threat is this? (dga, dns_tunneling, fast_flux, c2_communication, data_exfiltration, adware, tracking, benign)
3. **Explanation**: Clear explanation for a network administrator
4. **Confidence**: How confident are you in this assessment? (0.0-1.0)
5. **Remediation**: What actions should be taken?
6. **False Positive Factors**: What legitimate activity could cause this pattern?

ALERT DATA:
{alert_data}

CLIENT CONTEXT:
{client_context}

HISTORICAL PATTERNS:
{historical_context}

Respond in valid JSON format:
{{
    "threat_level": "medium",
    "classification": "possible_tunneling",
    "explanation": "The client at 10.10.20.50 is making an unusually high number of DNS queries...",
    "confidence": 0.85,
    "remediation": [
        "Investigate the process making these queries on the client machine",
        "Consider blocking domain xyz.com temporarily",
        "Monitor for continued activity"
    ],
    "false_positive_factors": [
        "Could be legitimate software update checks",
        "VPN or proxy software may cause similar patterns"
    ],
    "severity_justification": "Elevated due to high query rate and unusual subdomain patterns"
}}"""

DOMAIN_EXPLANATION_PROMPT = """You are a DNS security expert. Explain what this domain is likely used for based on its name and characteristics.

Domain: {domain}
Reputation Score: {reputation_score}/100
Category (detected): {category}
Entropy: {entropy}
Threat Indicators: {threat_indicators}

Provide a brief, clear explanation suitable for a network administrator. Include:
1. What this domain likely is (CDN, ad network, malware C2, legitimate service, etc.)
2. Whether it's safe to allow or should be blocked
3. Any relevant context

Respond in JSON format:
{{
    "domain_type": "advertising_network",
    "risk_level": "low",
    "explanation": "This appears to be...",
    "recommendation": "safe_to_allow",
    "confidence": 0.9
}}"""

REMEDIATION_PROMPT = """As a DNS security expert, provide consolidated remediation recommendations for the following security alerts.

ALERTS:
{alerts_summary}

NETWORK CONTEXT:
{network_context}

Provide prioritized, actionable recommendations. Focus on:
1. Immediate actions to mitigate threats
2. Investigation steps
3. Long-term preventive measures

Respond in JSON format:
{{
    "priority_actions": [
        {{"action": "Block domain xyz.com", "reason": "Confirmed DGA pattern", "urgency": "immediate"}},
        ...
    ],
    "investigation_steps": [
        "Check client 10.10.20.50 for malware",
        ...
    ],
    "preventive_measures": [
        "Enable DNS-over-HTTPS for all clients",
        ...
    ]
}}"""


class DnsLlmAnalysisService:
    """LLM-powered DNS threat analysis and explanations."""

    def __init__(self, db: Session = None):
        self._db = db
        self._openai = None

    @property
    def db(self) -> Session:
        if self._db is None:
            self._db = SessionLocal()
        return self._db

    @property
    def openai(self) -> OpenAIService:
        if self._openai is None:
            self._openai = OpenAIService()
        return self._openai

    async def analyze_threat(
        self,
        alert: DnsSecurityAlert,
        include_history: bool = True,
    ) -> dict:
        """
        Generate comprehensive threat analysis using LLM.

        Returns analysis dict with threat_level, classification, explanation, etc.
        """
        # Build context
        alert_data = self._format_alert_data(alert)
        client_context = self._get_client_context(alert.client_ip)
        historical_context = (
            self._get_historical_context(alert.client_ip)
            if include_history
            else "No historical context requested"
        )

        prompt = THREAT_ANALYSIS_PROMPT.format(
            alert_data=json.dumps(alert_data, indent=2),
            client_context=client_context,
            historical_context=historical_context,
        )

        try:
            response, usage = await self.openai.chat_with_usage(
                messages=[
                    {
                        "role": "system",
                        "content": "You are a DNS security expert. Respond only in valid JSON.",
                    },
                    {"role": "user", "content": prompt},
                ],
                model="gpt-4o-mini",  # Use smaller model for cost efficiency
            )

            # Log usage
            log_llm_usage(
                feature="dns",
                model=usage.model,
                prompt_tokens=usage.prompt_tokens,
                completion_tokens=usage.completion_tokens,
                function_name="analyze_threat",
            )

            # Parse JSON response
            result = self._parse_json_response(response)

            # Cache the analysis
            await self._cache_analysis(
                analysis_type="alert",
                target_identifier=str(alert.alert_id),
                result=result,
            )

            return result

        except Exception as e:
            logger.error("llm_analysis_failed", alert_id=str(alert.alert_id), error=str(e))
            return {
                "threat_level": alert.severity,
                "classification": alert.alert_type,
                "explanation": f"Automated analysis: {alert.description}",
                "confidence": 0.5,
                "remediation": ["Manual review recommended"],
                "false_positive_factors": [],
                "error": str(e),
            }

    async def explain_domain(self, domain: str, reputation_data: dict) -> dict:
        """
        Get LLM explanation of what a domain is and whether it's safe.
        """
        prompt = DOMAIN_EXPLANATION_PROMPT.format(
            domain=domain,
            reputation_score=reputation_data.get("reputation_score", "unknown"),
            category=reputation_data.get("category", "unknown"),
            entropy=reputation_data.get("entropy_score", "unknown"),
            threat_indicators=json.dumps(reputation_data.get("threat_indicators", {})),
        )

        try:
            response, usage = await self.openai.chat_with_usage(
                messages=[
                    {
                        "role": "system",
                        "content": "You are a DNS security expert. Respond only in valid JSON.",
                    },
                    {"role": "user", "content": prompt},
                ],
                model="gpt-4o-mini",
            )

            # Log usage
            log_llm_usage(
                feature="dns",
                model=usage.model,
                prompt_tokens=usage.prompt_tokens,
                completion_tokens=usage.completion_tokens,
                function_name="explain_domain",
            )

            result = self._parse_json_response(response)

            # Cache the analysis
            await self._cache_analysis(
                analysis_type="domain",
                target_identifier=domain,
                result=result,
            )

            return result

        except Exception as e:
            logger.error("domain_explanation_failed", domain=domain, error=str(e))
            return {
                "domain_type": "unknown",
                "risk_level": "unknown",
                "explanation": f"Unable to analyze domain: {str(e)}",
                "recommendation": "manual_review",
                "confidence": 0.0,
            }

    async def generate_remediation(
        self, alerts: list[DnsSecurityAlert], network_context: str = ""
    ) -> dict:
        """
        Generate consolidated remediation recommendations for multiple alerts.
        """
        # Summarize alerts
        alerts_summary = []
        for alert in alerts[:10]:  # Limit to prevent token overflow
            alerts_summary.append(
                {
                    "type": alert.alert_type,
                    "severity": alert.severity,
                    "domain": alert.domain,
                    "client_ip": alert.client_ip,
                    "title": alert.title,
                }
            )

        prompt = REMEDIATION_PROMPT.format(
            alerts_summary=json.dumps(alerts_summary, indent=2),
            network_context=network_context or "Standard home/office network",
        )

        try:
            response, usage = await self.openai.chat_with_usage(
                messages=[
                    {
                        "role": "system",
                        "content": "You are a DNS security expert. Respond only in valid JSON.",
                    },
                    {"role": "user", "content": prompt},
                ],
                model="gpt-4o-mini",
            )

            # Log usage
            log_llm_usage(
                feature="dns",
                model=usage.model,
                prompt_tokens=usage.prompt_tokens,
                completion_tokens=usage.completion_tokens,
                function_name="generate_remediation",
            )

            return self._parse_json_response(response)

        except Exception as e:
            logger.error("remediation_generation_failed", error=str(e))
            return {
                "priority_actions": [{"action": "Review alerts manually", "urgency": "normal"}],
                "investigation_steps": ["Check affected clients for malware"],
                "preventive_measures": ["Enable DNS filtering"],
                "error": str(e),
            }

    def _format_alert_data(self, alert: DnsSecurityAlert) -> dict:
        """Format alert data for LLM context."""
        return {
            "alert_type": alert.alert_type,
            "severity": alert.severity,
            "domain": alert.domain,
            "client_ip": alert.client_ip,
            "title": alert.title,
            "description": alert.description,
            "raw_data": alert.raw_data,
            "timestamp": alert.timestamp.isoformat() if alert.timestamp else None,
        }

    def _get_client_context(self, client_ip: str) -> str:
        """Get context about the client for LLM analysis."""
        from app.models import DnsClient, DnsClientProfile

        client = self.db.query(DnsClient).filter(DnsClient.client_id == client_ip).first()
        profile = (
            self.db.query(DnsClientProfile).filter(DnsClientProfile.client_id == client_ip).first()
        )

        context_parts = []

        if client:
            context_parts.append(f"Client Name: {client.name or 'Unknown'}")
            context_parts.append(f"Total Queries: {client.queries_count or 0}")
            context_parts.append(f"Blocked Queries: {client.blocked_count or 0}")

        if profile:
            context_parts.append(f"Device Type: {profile.device_type_inference or 'Unknown'}")
            context_parts.append(
                f"Normal Query Rate: {profile.normal_query_rate_per_hour or 0}/hour"
            )
            if profile.baseline_generated_at:
                context_parts.append(
                    f"Baseline Age: {(datetime.utcnow() - profile.baseline_generated_at).days} days"
                )

        return "\n".join(context_parts) if context_parts else "No client context available"

    def _get_historical_context(self, client_ip: str) -> str:
        """Get historical alert context for the client."""
        # Get recent alerts for this client
        cutoff = datetime.utcnow() - timedelta(days=7)
        recent_alerts = (
            self.db.query(DnsSecurityAlert)
            .filter(DnsSecurityAlert.client_ip == client_ip)
            .filter(DnsSecurityAlert.timestamp >= cutoff)
            .order_by(DnsSecurityAlert.timestamp.desc())
            .limit(5)
            .all()
        )

        if not recent_alerts:
            return "No recent alerts for this client"

        context_parts = [f"Recent alerts (last 7 days): {len(recent_alerts)}"]
        for alert in recent_alerts:
            context_parts.append(
                f"- {alert.alert_type}: {alert.title} ({alert.severity}) at {alert.timestamp}"
            )

        return "\n".join(context_parts)

    def _parse_json_response(self, response: str) -> dict:
        """Parse JSON from LLM response, handling markdown code blocks."""
        # Strip markdown code blocks if present
        text = response.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            # Remove first and last lines (code block markers)
            lines = lines[1:-1] if lines[-1].strip() == "```" else lines[1:]
            text = "\n".join(lines)

        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            logger.warning("json_parse_failed", response=text[:200], error=str(e))
            return {"raw_response": text, "parse_error": str(e)}

    async def _cache_analysis(
        self,
        analysis_type: str,
        target_identifier: str,
        result: dict,
        expires_hours: int = 24,
    ):
        """Cache LLM analysis result in database."""
        try:
            analysis = DnsThreatAnalysis(
                analysis_id=uuid.uuid4(),
                analysis_type=analysis_type,
                target_identifier=target_identifier,
                analysis_result=result,
                threat_level=result.get("threat_level"),
                classification=result.get("classification"),
                confidence=result.get("confidence"),
                recommendations=result.get("remediation") or result.get("recommendations"),
                model_used="gpt-4o-mini",
                analyzed_at=datetime.utcnow(),
                expires_at=datetime.utcnow() + timedelta(hours=expires_hours),
            )
            self.db.add(analysis)
            self.db.commit()
        except Exception as e:
            logger.error("cache_analysis_failed", error=str(e))
            self.db.rollback()

    async def get_cached_analysis(
        self, analysis_type: str, target_identifier: str
    ) -> Optional[dict]:
        """Get cached analysis if not expired."""
        analysis = (
            self.db.query(DnsThreatAnalysis)
            .filter(DnsThreatAnalysis.analysis_type == analysis_type)
            .filter(DnsThreatAnalysis.target_identifier == target_identifier)
            .filter(DnsThreatAnalysis.expires_at > datetime.utcnow())
            .order_by(DnsThreatAnalysis.analyzed_at.desc())
            .first()
        )

        if analysis:
            return analysis.analysis_result
        return None


# Singleton instance
_llm_analysis_service: Optional[DnsLlmAnalysisService] = None


def get_llm_analysis_service() -> DnsLlmAnalysisService:
    """Get or create the singleton LLM analysis service."""
    global _llm_analysis_service
    if _llm_analysis_service is None:
        _llm_analysis_service = DnsLlmAnalysisService()
    return _llm_analysis_service
