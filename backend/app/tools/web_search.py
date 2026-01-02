from app.tools.base import Tool, tool_registry
from app.services.search import SearchService


async def web_search_handler(query: str) -> dict:
    """Execute a web search."""
    search = SearchService()
    results = await search.search(query, limit=5)

    if not results:
        return {"results": [], "message": "No results found"}

    return {
        "results": results,
        "message": f"Found {len(results)} results",
    }


# Register the tool
web_search_tool = Tool(
    name="web_search",
    description="Search the web for information. Use this when you need current information or to research a topic.",
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query",
            }
        },
        "required": ["query"],
    },
    handler=web_search_handler,
)

tool_registry.register(web_search_tool)
