import httpx
from typing import List, Dict, Any

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from app.config import get_settings
from app.core.logging import get_logger

settings = get_settings()
logger = get_logger(__name__)


class SearchService:
    """Service for web search via SearXNG."""

    def __init__(self):
        self.base_url = settings.searxng_url
        self.timeout = httpx.Timeout(30.0)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError)),
        before_sleep=lambda retry_state: logger.warning(
            "searxng_retry",
            attempt=retry_state.attempt_number,
            wait=retry_state.next_action.sleep,
        ),
    )
    async def search(
        self,
        query: str,
        categories: List[str] = None,
        engines: List[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Perform a web search using SearXNG.

        Args:
            query: Search query
            categories: Categories to search (general, images, news, etc.)
            engines: Specific engines to use (google, bing, duckduckgo, etc.)
            limit: Maximum number of results

        Returns:
            List of search results with title, url, and content
        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            params = {
                "q": query,
                "format": "json",
            }

            if categories:
                params["categories"] = ",".join(categories)

            if engines:
                params["engines"] = ",".join(engines)

            try:
                response = await client.get(
                    f"{self.base_url}/search",
                    params=params,
                )
                response.raise_for_status()
                data = response.json()

                results = []
                for result in data.get("results", [])[:limit]:
                    results.append({
                        "title": result.get("title", ""),
                        "url": result.get("url", ""),
                        "content": result.get("content", ""),
                        "engine": result.get("engine", ""),
                    })

                return results

            except Exception as e:
                logger.error("search_error", error=str(e), query=query)
                return []

    async def health_check(self) -> bool:
        """Check if SearXNG is accessible."""
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
                response = await client.get(f"{self.base_url}/healthz")
                return response.status_code == 200
        except:
            return False
