"""Service for gathering company intelligence from web search."""

import json
from datetime import UTC, datetime
from typing import Any, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models import WorkAccount
from app.services.openai_service import OpenAIService
from app.services.search import SearchService

logger = get_logger(__name__)

# LLM prompt for extracting company intelligence
EXTRACTION_PROMPT = """You are extracting company information from search results.

Given the search results below for "{company_name}", extract the following information.
Only include information you are confident about based on the search results.
Return null for any field you cannot determine with confidence.

Return a JSON object with these fields:
- headquarters: string - City, State/Province, Country (e.g., "San Jose, CA, USA")
- industry: string - Primary industry sector (e.g., "Enterprise Networking", "Cloud Computing")
- summary: string - 2-3 sentence description of what the company does
- employee_count: number - Approximate number of employees (null if unknown)
- employee_count_range: string - Range like "1-50", "51-200", "201-500", "501-1000", "1001-5000", "5001-10000", "10001-50000", "50001-100000", "100000+"
- founded_year: number - Year company was founded (null if unknown)
- website_url: string - Official company website URL
- stock_ticker: string - Stock ticker symbol if publicly traded (null if private)
- stock_exchange: string - Exchange name like "NYSE", "NASDAQ", "LSE" (null if private)

SEARCH RESULTS:
{search_results}

Respond with only valid JSON, no markdown formatting or explanation."""


class AccountIntelligenceService:
    """Service for gathering and enriching account intelligence data."""

    def __init__(self, db: Session):
        self.db = db
        self.search_service = SearchService()
        self.openai_service = OpenAIService()

    async def gather_intelligence(self, company_name: str) -> Optional[dict[str, Any]]:
        """
        Gather company intelligence using web search and LLM extraction.

        Args:
            company_name: Name of the company to research

        Returns:
            Dictionary with intelligence fields or None if not found
        """
        logger.info("gathering_intelligence", company_name=company_name)

        # Search for company information
        search_query = f"{company_name} company headquarters industry employees founded"

        try:
            search_results = await self.search_service.search(
                query=search_query,
                categories=["general"],
                limit=8,
            )
        except Exception as e:
            logger.error("search_failed", company_name=company_name, error=str(e))
            return None

        if not search_results:
            logger.warning("no_search_results", company_name=company_name)
            return None

        # Format search results for LLM
        formatted_results = "\n\n".join(
            [
                f"Title: {r['title']}\nURL: {r['url']}\nContent: {r['content']}"
                for r in search_results
            ]
        )

        # Use LLM to extract structured data
        prompt = EXTRACTION_PROMPT.format(
            company_name=company_name,
            search_results=formatted_results,
        )

        try:
            response = await self.openai_service.chat(
                messages=[{"role": "user", "content": prompt}],
                model="gpt-4o-mini",
            )

            # Parse JSON response
            # Strip markdown code blocks if present
            response_text = response.strip()
            if response_text.startswith("```"):
                lines = response_text.split("\n")
                response_text = "\n".join(lines[1:-1])

            intelligence = json.loads(response_text)

            # Add metadata
            intelligence["enriched_at"] = datetime.now(UTC).isoformat()
            intelligence["enrichment_source"] = "searxng"

            # Calculate confidence based on how many fields were found
            filled_fields = sum(1 for v in intelligence.values() if v is not None)
            total_fields = 9  # Main intelligence fields
            intelligence["enrichment_confidence"] = round(filled_fields / total_fields, 2)

            logger.info(
                "intelligence_gathered",
                company_name=company_name,
                confidence=intelligence["enrichment_confidence"],
            )

            return intelligence

        except json.JSONDecodeError as e:
            logger.error(
                "json_parse_failed",
                company_name=company_name,
                error=str(e),
                response=response[:200] if response else None,
            )
            return None
        except Exception as e:
            logger.error("llm_extraction_failed", company_name=company_name, error=str(e))
            return None

    async def enrich_account(
        self,
        account_id: UUID,
        force: bool = False,
    ) -> Optional[WorkAccount]:
        """
        Enrich an account with company intelligence.

        Args:
            account_id: UUID of the account to enrich
            force: If True, refresh even if already enriched

        Returns:
            Updated WorkAccount or None if not found
        """
        # Get account
        account = self.db.query(WorkAccount).filter_by(account_id=account_id).first()
        if not account:
            logger.warning("account_not_found", account_id=str(account_id))
            return None

        # Check if already enriched
        extra_data = account.extra_data or {}
        existing_intelligence = extra_data.get("intelligence")

        if existing_intelligence and not force:
            logger.info(
                "already_enriched",
                account_id=str(account_id),
                enriched_at=existing_intelligence.get("enriched_at"),
            )
            return account

        # Gather intelligence
        intelligence = await self.gather_intelligence(account.name)

        if intelligence:
            # Update account
            extra_data["intelligence"] = intelligence
            account.extra_data = extra_data
            account.updated_at = datetime.now(UTC)
            self.db.commit()
            self.db.refresh(account)

            logger.info(
                "account_enriched",
                account_id=str(account_id),
                account_name=account.name,
            )
        else:
            logger.warning(
                "enrichment_failed",
                account_id=str(account_id),
                account_name=account.name,
            )

        return account

    def get_intelligence(self, account_id: UUID) -> Optional[dict[str, Any]]:
        """
        Get intelligence data for an account.

        Args:
            account_id: UUID of the account

        Returns:
            Intelligence dictionary or None
        """
        account = self.db.query(WorkAccount).filter_by(account_id=account_id).first()
        if not account:
            return None

        extra_data = account.extra_data or {}
        return extra_data.get("intelligence")
