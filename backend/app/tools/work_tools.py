from datetime import datetime
from typing import Optional

from app.core.logging import get_logger
from app.database import SessionLocal
from app.services.account_intelligence import AccountIntelligenceService
from app.services.work_notes import WorkNotesService
from app.tools.base import Tool, tool_registry

logger = get_logger(__name__)


# =============================================================================
# Tool Handlers
# =============================================================================


async def search_accounts_handler(query: str, limit: int = 5) -> dict:
    """Search for work accounts by name."""
    db = SessionLocal()
    try:
        service = WorkNotesService(db)
        results = service.search_accounts(query, limit=limit)

        if not results:
            return {
                "success": True,
                "message": f"No accounts found matching '{query}'",
                "accounts": [],
                "suggestion": "Would you like me to create a new account?",
            }

        return {
            "success": True,
            "accounts": [
                {
                    "account_id": str(acc.account_id),
                    "name": acc.name,
                    "description": acc.description[:100] if acc.description else None,
                    "status": acc.status,
                    "contact_count": len(acc.contacts or []),
                    "match_score": round(score, 2),
                }
                for acc, score in results
            ],
        }
    except Exception as e:
        logger.exception("search_accounts_failed")
        return {"success": False, "error": str(e)}
    finally:
        db.close()


async def get_account_context_handler(
    account_name: str,
    query: Optional[str] = None,
) -> dict:
    """Get full context for an account including recent notes."""
    db = SessionLocal()
    try:
        service = WorkNotesService(db)

        # Find the account
        matches = service.search_accounts(account_name, limit=1)
        if not matches or matches[0][1] < 0.5:
            return {
                "success": False,
                "message": f"Account '{account_name}' not found",
                "suggestions": [m[0].name for m in matches[:3]] if matches else [],
            }

        account = matches[0][0]
        context = await service.build_account_context(
            account_id=account.id,
            query=query,
        )

        stats = service.get_account_stats(account.id)

        return {
            "success": True,
            "account_name": account.name,
            "account_id": str(account.account_id),
            "context": context,
            "stats": stats,
        }
    except Exception as e:
        logger.exception("get_account_context_failed")
        return {"success": False, "error": str(e)}
    finally:
        db.close()


async def add_work_note_handler(
    account_name: str,
    content: str,
    activity_type: Optional[str] = None,
    create_account_if_missing: bool = False,
) -> dict:
    """Add a note to a work account."""
    db = SessionLocal()
    try:
        service = WorkNotesService(db)

        note, account, was_created, suggestions = await service.append_note(
            account_name=account_name,
            content=content,
            activity_type=activity_type,
            auto_create_account=create_account_if_missing,
        )

        if not note:
            # Account not found and not auto-creating
            return {
                "success": False,
                "message": f"Account '{account_name}' not found.",
                "suggestions": [s[0].name for s in suggestions[:5]],
                "prompt": "Did you mean one of these accounts, or should I create a new one?",
            }

        return {
            "success": True,
            "note_id": str(note.note_id),
            "account_name": account.name,
            "account_id": str(account.account_id),
            "account_created": was_created,
            "message": f"Note added to {account.name}"
            + (" (new account created)" if was_created else ""),
        }
    except Exception as e:
        logger.exception("add_work_note_failed")
        return {"success": False, "error": str(e)}
    finally:
        db.close()


async def create_account_handler(
    name: str,
    description: Optional[str] = None,
) -> dict:
    """Create a new work account."""
    db = SessionLocal()
    try:
        service = WorkNotesService(db)

        # Check if exists
        matches = service.search_accounts(name)
        if matches and matches[0][1] > 0.8:
            return {
                "success": False,
                "message": f"Account similar to '{name}' already exists: {matches[0][0].name}",
                "existing_account": matches[0][0].name,
            }

        account = service.create_account(name=name, description=description)

        return {
            "success": True,
            "account_id": str(account.account_id),
            "name": account.name,
            "message": f"Account '{name}' created successfully",
        }
    except Exception as e:
        logger.exception("create_account_failed")
        return {"success": False, "error": str(e)}
    finally:
        db.close()


async def search_work_notes_handler(
    query: str,
    account_name: Optional[str] = None,
    limit: int = 10,
) -> dict:
    """Search through work notes using semantic search."""
    db = SessionLocal()
    try:
        service = WorkNotesService(db)

        account_id = None
        account_name_resolved = None
        if account_name:
            matches = service.search_accounts(account_name, limit=1)
            if matches and matches[0][1] > 0.5:
                account_id = matches[0][0].id
                account_name_resolved = matches[0][0].name

        results = await service.semantic_search(
            query=query,
            account_id=account_id,
            limit=limit,
        )

        if not results:
            return {
                "success": True,
                "message": "No matching notes found",
                "results": [],
            }

        formatted = []
        for note, score in results:
            account = service.get_account_by_id(note.account_id)
            formatted.append(
                {
                    "account_name": account.name if account else "Unknown",
                    "date": note.created_at.strftime("%Y-%m-%d") if note.created_at else None,
                    "activity_type": note.activity_type,
                    "content": note.content[:300] + "..."
                    if len(note.content) > 300
                    else note.content,
                    "similarity": round(score, 3),
                }
            )

        return {
            "success": True,
            "query": query,
            "account_filter": account_name_resolved,
            "results": formatted,
            "count": len(formatted),
        }
    except Exception as e:
        logger.exception("search_work_notes_failed")
        return {"success": False, "error": str(e)}
    finally:
        db.close()


async def list_accounts_handler(
    status: Optional[str] = None,
    limit: int = 20,
) -> dict:
    """List all work accounts."""
    db = SessionLocal()
    try:
        service = WorkNotesService(db)
        accounts = service.list_accounts(status=status, limit=limit)

        return {
            "success": True,
            "accounts": [
                {
                    "account_id": str(acc.account_id),
                    "name": acc.name,
                    "description": acc.description[:100] if acc.description else None,
                    "status": acc.status,
                    "contact_count": len(acc.contacts or []),
                }
                for acc in accounts
            ],
            "count": len(accounts),
        }
    except Exception as e:
        logger.exception("list_accounts_failed")
        return {"success": False, "error": str(e)}
    finally:
        db.close()


async def update_account_handler(
    account_name: str,
    description: Optional[str] = None,
    add_contact: Optional[dict] = None,
    add_alias: Optional[str] = None,
    status: Optional[str] = None,
) -> dict:
    """Update account information."""
    db = SessionLocal()
    try:
        service = WorkNotesService(db)

        matches = service.search_accounts(account_name, limit=1)
        if not matches or matches[0][1] < 0.5:
            return {"success": False, "message": f"Account '{account_name}' not found"}

        account = matches[0][0]

        # Build updates
        contacts = None
        aliases = None

        if add_contact:
            contacts = account.contacts or []
            # Ensure contacts is a flat list (fix any nested arrays)
            if contacts and isinstance(contacts[0], list):
                contacts = contacts[0]
            # Handle case where LLM passes array instead of single contact
            if isinstance(add_contact, list):
                contacts.extend(add_contact)
            else:
                contacts.append(add_contact)

        if add_alias:
            aliases = account.aliases or []
            aliases.append(add_alias)

        service.update_account(
            account.account_id,
            description=description,
            contacts=contacts,
            aliases=aliases,
            status=status,
        )

        return {
            "success": True,
            "message": f"Account '{account.name}' updated",
        }
    except Exception as e:
        logger.exception("update_account_failed")
        return {"success": False, "error": str(e)}
    finally:
        db.close()


async def get_recent_activity_handler(days: int = 30, limit: int = 20) -> dict:
    """Get recent notes across all accounts."""
    db = SessionLocal()
    try:
        service = WorkNotesService(db)
        notes = service.get_recent_notes(days=days, limit=limit)

        formatted = []
        for note in notes:
            account = service.get_account_by_id(note.account_id)
            formatted.append(
                {
                    "account_name": account.name if account else "Unknown",
                    "date": note.created_at.strftime("%Y-%m-%d") if note.created_at else None,
                    "activity_type": note.activity_type,
                    "content": note.content[:200] + "..."
                    if len(note.content) > 200
                    else note.content,
                }
            )

        return {
            "success": True,
            "days": days,
            "notes": formatted,
            "count": len(formatted),
        }
    except Exception as e:
        logger.exception("get_recent_activity_failed")
        return {"success": False, "error": str(e)}
    finally:
        db.close()


async def update_user_profile_handler(
    name: Optional[str] = None,
    role: Optional[str] = None,
    company: Optional[str] = None,
    department: Optional[str] = None,
    responsibilities: Optional[list[str]] = None,
    expertise_areas: Optional[list[str]] = None,
    goals: Optional[list[str]] = None,
    working_style: Optional[str] = None,
    current_priorities: Optional[list[str]] = None,
    add_responsibility: Optional[str] = None,
    add_expertise: Optional[str] = None,
    add_priority: Optional[str] = None,
    add_goal: Optional[str] = None,
) -> dict:
    """Update the user's work profile with information about them."""
    db = SessionLocal()
    try:
        service = WorkNotesService(db)
        profile = service.get_or_create_profile()

        updates_made = []

        # Direct field updates
        if name is not None:
            profile.name = name
            updates_made.append(f"name: {name}")
        if role is not None:
            profile.role = role
            updates_made.append(f"role: {role}")
        if company is not None:
            profile.company = company
            updates_made.append(f"company: {company}")
        if department is not None:
            profile.department = department
            updates_made.append(f"department: {department}")
        if working_style is not None:
            profile.working_style = working_style
            updates_made.append("working_style")

        # List replacements
        if responsibilities is not None:
            profile.responsibilities = responsibilities
            updates_made.append(f"responsibilities: {len(responsibilities)} items")
        if expertise_areas is not None:
            profile.expertise_areas = expertise_areas
            updates_made.append(f"expertise_areas: {len(expertise_areas)} items")
        if goals is not None:
            profile.goals = goals
            updates_made.append(f"goals: {len(goals)} items")
        if current_priorities is not None:
            profile.current_priorities = current_priorities
            updates_made.append(f"current_priorities: {len(current_priorities)} items")

        # Append to lists
        if add_responsibility:
            current = profile.responsibilities or []
            if add_responsibility not in current:
                current.append(add_responsibility)
                profile.responsibilities = current
                updates_made.append(f"added responsibility: {add_responsibility}")

        if add_expertise:
            current = profile.expertise_areas or []
            if add_expertise not in current:
                current.append(add_expertise)
                profile.expertise_areas = current
                updates_made.append(f"added expertise: {add_expertise}")

        if add_priority:
            current = profile.current_priorities or []
            if add_priority not in current:
                current.append(add_priority)
                profile.current_priorities = current
                updates_made.append(f"added priority: {add_priority}")

        if add_goal:
            current = profile.goals or []
            if add_goal not in current:
                current.append(add_goal)
                profile.goals = current
                updates_made.append(f"added goal: {add_goal}")

        profile.updated_at = datetime.utcnow()
        db.commit()

        if not updates_made:
            return {
                "success": False,
                "message": "No updates provided. Specify at least one field to update.",
            }

        return {
            "success": True,
            "message": "Profile updated successfully",
            "updates": updates_made,
            "profile_summary": {
                "name": profile.name,
                "role": profile.role,
                "company": profile.company,
                "department": profile.department,
                "responsibilities_count": len(profile.responsibilities or []),
                "expertise_count": len(profile.expertise_areas or []),
                "priorities_count": len(profile.current_priorities or []),
            },
        }
    except Exception as e:
        logger.exception("update_user_profile_failed")
        return {"success": False, "error": str(e)}
    finally:
        db.close()


async def get_user_profile_handler() -> dict:
    """Get the current user's work profile."""
    db = SessionLocal()
    try:
        service = WorkNotesService(db)
        profile = service.get_profile()

        if not profile:
            return {
                "success": True,
                "message": "No profile exists yet. Would you like me to create one with the information you've shared?",
                "profile": None,
            }

        return {
            "success": True,
            "profile": {
                "name": profile.name,
                "role": profile.role,
                "company": profile.company,
                "department": profile.department,
                "responsibilities": profile.responsibilities or [],
                "expertise_areas": profile.expertise_areas or [],
                "goals": profile.goals or [],
                "working_style": profile.working_style,
                "current_priorities": profile.current_priorities or [],
                "learned_facts_count": len(profile.learned_facts or []),
            },
        }
    except Exception as e:
        logger.exception("get_user_profile_failed")
        return {"success": False, "error": str(e)}
    finally:
        db.close()


async def enrich_account_handler(account_name: str, force: bool = False) -> dict:
    """Enrich an account with company intelligence using web search."""
    db = SessionLocal()
    try:
        work_service = WorkNotesService(db)
        intel_service = AccountIntelligenceService(db)

        # Find the account
        matches = work_service.search_accounts(account_name, limit=1)
        if not matches or matches[0][1] < 0.5:
            return {
                "success": False,
                "message": f"Account '{account_name}' not found",
                "suggestions": [m[0].name for m in matches[:3]] if matches else [],
            }

        account = matches[0][0]

        # Check if already enriched and not forcing
        existing = (account.extra_data or {}).get("intelligence")
        if existing and not force:
            return {
                "success": True,
                "message": f"Account '{account.name}' already has intelligence data",
                "account_name": account.name,
                "intelligence": existing,
                "note": "Use force=true to refresh the intelligence data",
            }

        # Enrich the account
        enriched = await intel_service.enrich_account(account.account_id, force=force)

        if enriched:
            intelligence = (enriched.extra_data or {}).get("intelligence", {})
            return {
                "success": True,
                "message": f"Successfully gathered intelligence for {enriched.name}",
                "account_name": enriched.name,
                "intelligence": intelligence,
            }
        else:
            return {
                "success": False,
                "message": f"Could not gather intelligence for '{account.name}'. The company may not have enough public information available.",
            }
    except Exception as e:
        logger.exception("enrich_account_failed")
        return {"success": False, "error": str(e)}
    finally:
        db.close()


# =============================================================================
# Tool Definitions
# =============================================================================

search_accounts_tool = Tool(
    name="search_accounts",
    description="Search for work/customer accounts by name. Use this to find existing accounts before adding notes or to check if an account exists.",
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Account name or partial name to search for",
            },
            "limit": {
                "type": "integer",
                "description": "Max results (default: 5)",
                "default": 5,
            },
        },
        "required": ["query"],
    },
    handler=search_accounts_handler,
)

get_account_context_tool = Tool(
    name="get_account_context",
    description="Get full context for a work account including recent notes, contacts, and relevant history. Use this before discussing an account to understand the relationship.",
    parameters={
        "type": "object",
        "properties": {
            "account_name": {
                "type": "string",
                "description": "The account name to get context for",
            },
            "query": {
                "type": "string",
                "description": "Optional search query to find relevant historical notes",
            },
        },
        "required": ["account_name"],
    },
    handler=get_account_context_handler,
)

add_work_note_tool = Tool(
    name="add_work_note",
    description="Add a note to a work account. Use this to capture meetings, calls, emails, tasks, or any other work-related information about a customer/client.",
    parameters={
        "type": "object",
        "properties": {
            "account_name": {
                "type": "string",
                "description": "The account to add the note to",
            },
            "content": {
                "type": "string",
                "description": "The note content - describe the interaction or information",
            },
            "activity_type": {
                "type": "string",
                "enum": ["meeting", "call", "email", "task", "note", "follow_up"],
                "description": "Type of activity (optional, can be auto-detected)",
            },
            "create_account_if_missing": {
                "type": "boolean",
                "description": "Create the account if it doesn't exist (default: false)",
                "default": False,
            },
        },
        "required": ["account_name", "content"],
    },
    handler=add_work_note_handler,
)

create_account_tool = Tool(
    name="create_account",
    description="Create a new work/customer account. Use this when a user confirms they want to create a new account.",
    parameters={
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Account name (company/customer name)",
            },
            "description": {
                "type": "string",
                "description": "Brief description of the account",
            },
        },
        "required": ["name"],
    },
    handler=create_account_handler,
)

search_work_notes_tool = Tool(
    name="search_work_notes",
    description="Search through work notes using semantic similarity. Find relevant past interactions, discussions, and information about accounts.",
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "What to search for",
            },
            "account_name": {
                "type": "string",
                "description": "Optionally limit search to a specific account",
            },
            "limit": {
                "type": "integer",
                "description": "Max results (default: 10)",
                "default": 10,
            },
        },
        "required": ["query"],
    },
    handler=search_work_notes_handler,
)

list_accounts_tool = Tool(
    name="list_accounts",
    description="List all work accounts. See all customers/clients in the system.",
    parameters={
        "type": "object",
        "properties": {
            "status": {
                "type": "string",
                "enum": ["active", "inactive", "prospect", "closed"],
                "description": "Filter by status",
            },
            "limit": {
                "type": "integer",
                "description": "Max results (default: 20)",
                "default": 20,
            },
        },
        "required": [],
    },
    handler=list_accounts_handler,
)

update_account_tool = Tool(
    name="update_account",
    description="Update account information - add contacts, aliases, change status, or update description.",
    parameters={
        "type": "object",
        "properties": {
            "account_name": {
                "type": "string",
                "description": "Account to update",
            },
            "description": {
                "type": "string",
                "description": "New description for the account",
            },
            "add_contact": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "role": {"type": "string"},
                    "email": {"type": "string"},
                    "phone": {"type": "string"},
                },
                "description": "Contact to add to the account",
            },
            "add_alias": {
                "type": "string",
                "description": "Alternative name for the account (helps with matching)",
            },
            "status": {
                "type": "string",
                "enum": ["active", "inactive", "prospect", "closed"],
                "description": "New status for the account",
            },
        },
        "required": ["account_name"],
    },
    handler=update_account_handler,
)

get_recent_activity_tool = Tool(
    name="get_recent_activity",
    description="Get recent work notes across all accounts. See what's been happening lately.",
    parameters={
        "type": "object",
        "properties": {
            "days": {
                "type": "integer",
                "description": "Number of days to look back (default: 30)",
                "default": 30,
            },
            "limit": {
                "type": "integer",
                "description": "Max results (default: 20)",
                "default": 20,
            },
        },
        "required": [],
    },
    handler=get_recent_activity_handler,
)

update_user_profile_tool = Tool(
    name="update_user_profile",
    description="Update the user's work profile with information about them. Use this when the user shares information about themselves (name, role, company, skills, responsibilities, goals, etc.) and wants it saved to their profile. Call this tool to store information from resumes, bios, or when the user directly tells you about themselves.",
    parameters={
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "User's name",
            },
            "role": {
                "type": "string",
                "description": "User's job title/role (e.g., 'Solutions Architect', 'Sales Engineer')",
            },
            "company": {
                "type": "string",
                "description": "User's company/employer",
            },
            "department": {
                "type": "string",
                "description": "User's department",
            },
            "responsibilities": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of user's job responsibilities",
            },
            "expertise_areas": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of user's expertise/skill areas",
            },
            "goals": {
                "type": "array",
                "items": {"type": "string"},
                "description": "User's professional goals",
            },
            "working_style": {
                "type": "string",
                "description": "Description of user's working style or preferences",
            },
            "current_priorities": {
                "type": "array",
                "items": {"type": "string"},
                "description": "User's current work priorities",
            },
            "add_responsibility": {
                "type": "string",
                "description": "Add a single responsibility to existing list",
            },
            "add_expertise": {
                "type": "string",
                "description": "Add a single expertise area to existing list",
            },
            "add_priority": {
                "type": "string",
                "description": "Add a single priority to existing list",
            },
            "add_goal": {
                "type": "string",
                "description": "Add a single goal to existing list",
            },
        },
        "required": [],
    },
    handler=update_user_profile_handler,
)

get_user_profile_tool = Tool(
    name="get_user_profile",
    description="Get the current user's work profile. Use this to see what information is already stored about the user.",
    parameters={
        "type": "object",
        "properties": {},
        "required": [],
    },
    handler=get_user_profile_handler,
)

enrich_account_tool = Tool(
    name="enrich_account",
    description="Gather company intelligence for a work account using web search. Retrieves headquarters location, industry, company summary, employee count, founded year, website, and stock ticker (if public). Use this to enrich accounts with company information.",
    parameters={
        "type": "object",
        "properties": {
            "account_name": {
                "type": "string",
                "description": "The account name to enrich with intelligence",
            },
            "force": {
                "type": "boolean",
                "description": "Force refresh even if intelligence already exists (default: false)",
                "default": False,
            },
        },
        "required": ["account_name"],
    },
    handler=enrich_account_handler,
)


# =============================================================================
# Registration
# =============================================================================


def register_work_tools():
    """Register all work tools with the global registry."""
    tool_registry.register(search_accounts_tool)
    tool_registry.register(get_account_context_tool)
    tool_registry.register(add_work_note_tool)
    tool_registry.register(create_account_tool)
    tool_registry.register(search_work_notes_tool)
    tool_registry.register(list_accounts_tool)
    tool_registry.register(update_account_tool)
    tool_registry.register(get_recent_activity_tool)
    tool_registry.register(update_user_profile_tool)
    tool_registry.register(get_user_profile_tool)
    tool_registry.register(enrich_account_tool)
