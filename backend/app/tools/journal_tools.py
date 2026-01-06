from app.core.logging import get_logger
from app.database import SessionLocal
from app.services.journal import JournalService
from app.tools.base import Tool, tool_registry

logger = get_logger(__name__)


# =========================================================================
# Journal Tool Handlers
# =========================================================================


async def search_journal_handler(query: str, limit: int = 5) -> dict:
    """Search through journal entries using semantic similarity."""
    db = SessionLocal()
    try:
        service = JournalService(db)
        results = await service.semantic_search(query=query, limit=limit)

        if not results:
            return {
                "success": True,
                "message": "No matching journal entries found.",
                "results": [],
            }

        formatted_results = []
        for entry, score in results:
            formatted_results.append(
                {
                    "date": entry.date.isoformat()
                    if hasattr(entry.date, "isoformat")
                    else str(entry.date),
                    "title": entry.title,
                    "content": entry.content[:300] + "..."
                    if len(entry.content) > 300
                    else entry.content,
                    "mood": entry.mood,
                    "tags": entry.tags or [],
                    "similarity": round(score, 3),
                }
            )

        return {
            "success": True,
            "query": query,
            "results": formatted_results,
            "count": len(formatted_results),
        }
    except Exception as e:
        logger.exception("search_journal_failed")
        return {"success": False, "error": str(e)}
    finally:
        db.close()


async def get_recent_entries_handler(days: int = 7) -> dict:
    """Get journal entries from the last N days."""
    db = SessionLocal()
    try:
        service = JournalService(db)
        entries = service.get_recent_entries(days=days)

        if not entries:
            return {
                "success": True,
                "message": f"No journal entries in the last {days} days.",
                "entries": [],
            }

        formatted_entries = []
        for entry in entries:
            formatted_entries.append(
                {
                    "date": entry.date.isoformat()
                    if hasattr(entry.date, "isoformat")
                    else str(entry.date),
                    "title": entry.title,
                    "content": entry.content[:300] + "..."
                    if len(entry.content) > 300
                    else entry.content,
                    "mood": entry.mood,
                    "energy_level": entry.energy_level,
                    "tags": entry.tags or [],
                }
            )

        return {
            "success": True,
            "days": days,
            "entries": formatted_entries,
            "count": len(formatted_entries),
        }
    except Exception as e:
        logger.exception("get_recent_entries_failed")
        return {"success": False, "error": str(e)}
    finally:
        db.close()


async def get_journal_stats_handler() -> dict:
    """Get journal statistics including streaks, mood trends, and totals."""
    db = SessionLocal()
    try:
        service = JournalService(db)
        stats = service.get_stats()

        return {
            "success": True,
            **stats,
        }
    except Exception as e:
        logger.exception("get_journal_stats_failed")
        return {"success": False, "error": str(e)}
    finally:
        db.close()


async def get_entries_by_mood_handler(mood: str, limit: int = 10) -> dict:
    """Get journal entries filtered by mood."""
    db = SessionLocal()
    try:
        service = JournalService(db)
        entries = service.get_entries(mood=mood, limit=limit)

        if not entries:
            return {
                "success": True,
                "message": f"No journal entries with mood '{mood}' found.",
                "entries": [],
            }

        formatted_entries = []
        for entry in entries:
            formatted_entries.append(
                {
                    "date": entry.date.isoformat()
                    if hasattr(entry.date, "isoformat")
                    else str(entry.date),
                    "title": entry.title,
                    "content": entry.content[:200] + "..."
                    if len(entry.content) > 200
                    else entry.content,
                    "mood": entry.mood,
                    "tags": entry.tags or [],
                }
            )

        return {
            "success": True,
            "mood": mood,
            "entries": formatted_entries,
            "count": len(formatted_entries),
        }
    except Exception as e:
        logger.exception("get_entries_by_mood_failed")
        return {"success": False, "error": str(e)}
    finally:
        db.close()


# =========================================================================
# Tool Definitions
# =========================================================================

search_journal_tool = Tool(
    name="search_journal",
    description="Search through the user's journal entries using semantic similarity. Use this to find relevant past entries based on topics, experiences, or themes the user is discussing.",
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query - can be topics, feelings, experiences, or keywords to find related journal entries",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of results to return (default: 5)",
                "default": 5,
            },
        },
        "required": ["query"],
    },
    handler=search_journal_handler,
)

get_recent_entries_tool = Tool(
    name="get_recent_entries",
    description="Get the user's journal entries from the last N days. Use this to understand their recent experiences, moods, and context.",
    parameters={
        "type": "object",
        "properties": {
            "days": {
                "type": "integer",
                "description": "Number of days to look back (default: 7)",
                "default": 7,
            },
        },
        "required": [],
    },
    handler=get_recent_entries_handler,
)

get_journal_stats_tool = Tool(
    name="get_journal_stats",
    description="Get statistics about the user's journaling habit including current streak, mood distribution, and entry counts.",
    parameters={
        "type": "object",
        "properties": {},
        "required": [],
    },
    handler=get_journal_stats_handler,
)

get_entries_by_mood_tool = Tool(
    name="get_entries_by_mood",
    description="Get journal entries filtered by a specific mood. Use this to explore patterns or discuss entries from times when the user felt a particular way.",
    parameters={
        "type": "object",
        "properties": {
            "mood": {
                "type": "string",
                "description": "The mood to filter by (e.g., 'happy', 'sad', 'anxious', 'excited', 'neutral')",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of results to return (default: 10)",
                "default": 10,
            },
        },
        "required": ["mood"],
    },
    handler=get_entries_by_mood_handler,
)


# =========================================================================
# Register Tools
# =========================================================================


def register_journal_tools():
    """Register all journal tools with the global registry."""
    tool_registry.register(search_journal_tool)
    tool_registry.register(get_recent_entries_tool)
    tool_registry.register(get_journal_stats_tool)
    tool_registry.register(get_entries_by_mood_tool)
