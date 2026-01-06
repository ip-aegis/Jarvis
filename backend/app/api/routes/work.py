from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.database import SessionLocal, get_db
from app.models import WorkAccount
from app.services.account_intelligence import AccountIntelligenceService
from app.services.work_notes import WorkNotesService

logger = get_logger(__name__)
router = APIRouter()


# =============================================================================
# Request/Response Models
# =============================================================================


class ContactCreate(BaseModel):
    name: str
    role: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None


class AccountCreate(BaseModel):
    name: str
    description: Optional[str] = None
    contacts: Optional[list[dict]] = None
    metadata: Optional[dict] = None


class AccountUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    contacts: Optional[list[dict]] = None
    metadata: Optional[dict] = None
    aliases: Optional[list[str]] = None
    status: Optional[str] = None


class NoteCreate(BaseModel):
    content: str
    activity_type: Optional[str] = None
    activity_date: Optional[datetime] = None


class NoteUpdate(BaseModel):
    content: Optional[str] = None
    activity_type: Optional[str] = None
    activity_date: Optional[datetime] = None
    tags: Optional[list[str]] = None


# =============================================================================
# Helper Functions
# =============================================================================


def account_to_response(account: WorkAccount) -> dict:
    """Convert WorkAccount model to response dict."""
    return {
        "account_id": str(account.account_id),
        "name": account.name,
        "description": account.description,
        "contacts": account.contacts or [],
        "extra_data": account.extra_data or {},
        "status": account.status,
        "aliases": account.aliases or [],
        "created_at": account.created_at.isoformat() if account.created_at else None,
        "updated_at": account.updated_at.isoformat() if account.updated_at else None,
    }


def note_to_response(note) -> dict:
    """Convert WorkNote model to response dict."""
    return {
        "note_id": str(note.note_id),
        "account_id": note.account_id,
        "content": note.content,
        "activity_type": note.activity_type,
        "activity_date": note.activity_date.isoformat() if note.activity_date else None,
        "mentioned_contacts": note.mentioned_contacts or [],
        "action_items": note.action_items or [],
        "tags": note.tags or [],
        "source": note.source,
        "created_at": note.created_at.isoformat() if note.created_at else None,
        "updated_at": note.updated_at.isoformat() if note.updated_at else None,
    }


# =============================================================================
# Account Endpoints
# =============================================================================


@router.get("/accounts")
async def list_accounts(
    status: Optional[str] = Query(None),
    limit: int = Query(50, le=100),
    offset: int = Query(0),
    db: Session = Depends(get_db),
):
    """List all work accounts."""
    service = WorkNotesService(db)
    accounts = service.list_accounts(status=status, limit=limit, offset=offset)
    return {
        "accounts": [account_to_response(a) for a in accounts],
        "count": len(accounts),
    }


@router.get("/accounts/search")
async def search_accounts(
    q: str = Query(..., min_length=1),
    limit: int = Query(10, le=50),
    db: Session = Depends(get_db),
):
    """Search accounts by name."""
    service = WorkNotesService(db)
    results = service.search_accounts(q, limit=limit)
    return {
        "query": q,
        "results": [
            {
                **account_to_response(acc),
                "match_score": round(score, 2),
            }
            for acc, score in results
        ],
    }


async def _enrich_account_background(account_id: UUID):
    """Background task to enrich account with intelligence."""
    db = SessionLocal()
    try:
        service = AccountIntelligenceService(db)
        await service.enrich_account(account_id)
    except Exception as e:
        logger.error("background_enrichment_failed", account_id=str(account_id), error=str(e))
    finally:
        db.close()


@router.post("/accounts")
async def create_account(
    request: AccountCreate,
    background_tasks: BackgroundTasks,
    auto_enrich: bool = Query(True, description="Automatically gather company intelligence"),
    db: Session = Depends(get_db),
):
    """Create a new work account."""
    service = WorkNotesService(db)

    # Check for duplicates
    matches = service.search_accounts(request.name)
    if matches and matches[0][1] > 0.9:
        raise HTTPException(
            status_code=409,
            detail=f"Account similar to '{request.name}' already exists: {matches[0][0].name}",
        )

    account = service.create_account(
        name=request.name,
        description=request.description,
        contacts=request.contacts,
        metadata=request.metadata,
    )

    # Queue background intelligence gathering
    if auto_enrich:
        background_tasks.add_task(_enrich_account_background, account.account_id)

    return account_to_response(account)


@router.get("/accounts/{account_id}")
async def get_account(account_id: UUID, db: Session = Depends(get_db)):
    """Get a specific account."""
    service = WorkNotesService(db)
    account = service.get_account(account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    return account_to_response(account)


@router.put("/accounts/{account_id}")
async def update_account(
    account_id: UUID,
    request: AccountUpdate,
    db: Session = Depends(get_db),
):
    """Update an account."""
    service = WorkNotesService(db)
    account = service.update_account(
        account_id=account_id,
        name=request.name,
        description=request.description,
        contacts=request.contacts,
        metadata=request.metadata,
        aliases=request.aliases,
        status=request.status,
    )
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    return account_to_response(account)


@router.delete("/accounts/{account_id}")
async def delete_account(account_id: UUID, db: Session = Depends(get_db)):
    """Delete an account and all its notes."""
    service = WorkNotesService(db)
    if not service.delete_account(account_id):
        raise HTTPException(status_code=404, detail="Account not found")
    return {"status": "deleted", "account_id": str(account_id)}


@router.get("/accounts/{account_id}/stats")
async def get_account_stats(account_id: UUID, db: Session = Depends(get_db)):
    """Get statistics for an account."""
    service = WorkNotesService(db)
    account = service.get_account(account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    return service.get_account_stats(account.id)


@router.post("/accounts/{account_id}/contacts")
async def add_contact(
    account_id: UUID,
    contact: ContactCreate,
    db: Session = Depends(get_db),
):
    """Add a contact to an account."""
    service = WorkNotesService(db)
    account = service.get_account(account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    contacts = account.contacts or []
    contacts.append(contact.model_dump())

    updated = service.update_account(account_id, contacts=contacts)
    return account_to_response(updated)


# =============================================================================
# Intelligence Endpoints
# =============================================================================


@router.post("/accounts/{account_id}/enrich")
async def enrich_account(
    account_id: UUID,
    force: bool = Query(False, description="Force refresh even if already enriched"),
    db: Session = Depends(get_db),
):
    """Manually trigger intelligence enrichment for an account."""
    service = AccountIntelligenceService(db)
    account = await service.enrich_account(account_id, force=force)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    return account_to_response(account)


@router.get("/accounts/{account_id}/intelligence")
async def get_account_intelligence(
    account_id: UUID,
    db: Session = Depends(get_db),
):
    """Get intelligence data for an account."""
    service = AccountIntelligenceService(db)
    intelligence = service.get_intelligence(account_id)

    # Get account for name
    work_service = WorkNotesService(db)
    account = work_service.get_account(account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    return {
        "account_id": str(account_id),
        "account_name": account.name,
        "has_intelligence": intelligence is not None,
        "intelligence": intelligence,
    }


# =============================================================================
# Note Endpoints
# =============================================================================


@router.get("/accounts/{account_id}/notes")
async def list_notes(
    account_id: UUID,
    limit: int = Query(50, le=100),
    offset: int = Query(0),
    db: Session = Depends(get_db),
):
    """List notes for an account."""
    service = WorkNotesService(db)
    account = service.get_account(account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    notes = service.get_notes_for_account(account.id, limit=limit, offset=offset)
    return {
        "account_name": account.name,
        "notes": [note_to_response(n) for n in notes],
        "count": len(notes),
    }


@router.post("/accounts/{account_id}/notes")
async def create_note(
    account_id: UUID,
    request: NoteCreate,
    db: Session = Depends(get_db),
):
    """Add a note to an account."""
    service = WorkNotesService(db)
    account = service.get_account(account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    try:
        note = await service.create_note(
            account_id=account.id,
            content=request.content,
            activity_type=request.activity_type,
            activity_date=request.activity_date,
        )
        return note_to_response(note)
    except Exception as e:
        logger.exception("create_note_failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/notes/{note_id}")
async def get_note(note_id: UUID, db: Session = Depends(get_db)):
    """Get a specific note."""
    service = WorkNotesService(db)
    note = service.get_note(note_id)
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    return note_to_response(note)


@router.put("/notes/{note_id}")
async def update_note(
    note_id: UUID,
    request: NoteUpdate,
    db: Session = Depends(get_db),
):
    """Update a note."""
    service = WorkNotesService(db)
    try:
        note = await service.update_note(
            note_id=note_id,
            content=request.content,
            activity_type=request.activity_type,
            activity_date=request.activity_date,
            tags=request.tags,
        )
        if not note:
            raise HTTPException(status_code=404, detail="Note not found")
        return note_to_response(note)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("update_note_failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/notes/{note_id}")
async def delete_note(note_id: UUID, db: Session = Depends(get_db)):
    """Delete a note."""
    service = WorkNotesService(db)
    if not service.delete_note(note_id):
        raise HTTPException(status_code=404, detail="Note not found")
    return {"status": "deleted", "note_id": str(note_id)}


# =============================================================================
# Search Endpoints
# =============================================================================


@router.get("/notes/search")
async def search_notes(
    q: str = Query(..., min_length=1),
    account_id: Optional[UUID] = Query(None),
    limit: int = Query(20, le=100),
    db: Session = Depends(get_db),
):
    """Search notes using semantic similarity."""
    service = WorkNotesService(db)

    account_db_id = None
    if account_id:
        account = service.get_account(account_id)
        if account:
            account_db_id = account.id

    try:
        results = await service.semantic_search(q, account_id=account_db_id, limit=limit)

        return {
            "query": q,
            "results": [
                {
                    **note_to_response(note),
                    "account_name": service.get_account_by_id(note.account_id).name
                    if service.get_account_by_id(note.account_id)
                    else "Unknown",
                    "similarity": round(score, 3),
                }
                for note, score in results
            ],
        }
    except Exception as e:
        logger.exception("search_notes_failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/notes/recent")
async def get_recent_notes(
    days: int = Query(30, le=90),
    limit: int = Query(50, le=100),
    db: Session = Depends(get_db),
):
    """Get recent notes across all accounts."""
    service = WorkNotesService(db)
    notes = service.get_recent_notes(days=days, limit=limit)

    return {
        "days": days,
        "notes": [
            {
                **note_to_response(note),
                "account_name": service.get_account_by_id(note.account_id).name
                if service.get_account_by_id(note.account_id)
                else "Unknown",
            }
            for note in notes
        ],
        "count": len(notes),
    }


# =============================================================================
# Context Endpoints
# =============================================================================


@router.get("/accounts/{account_id}/context")
async def get_account_context(
    account_id: UUID,
    query: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Get LLM context for an account."""
    service = WorkNotesService(db)
    account = service.get_account(account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    try:
        context = await service.build_account_context(
            account_id=account.id,
            query=query,
        )
        return {"context": context}
    except Exception as e:
        logger.exception("context_build_failed")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Stats Endpoints
# =============================================================================


@router.get("/stats")
async def get_global_stats(db: Session = Depends(get_db)):
    """Get statistics across all accounts."""
    service = WorkNotesService(db)
    return service.get_global_stats()


# =============================================================================
# Events & Summary Endpoints
# =============================================================================


@router.get("/accounts/{account_id}/events")
async def get_account_events(
    account_id: UUID,
    days_back: int = Query(30, le=90),
    days_ahead: int = Query(30, le=90),
    db: Session = Depends(get_db),
):
    """Get events timeline for an account (action items and scheduled activities)."""
    service = WorkNotesService(db)
    account = service.get_account(account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    events = service.get_account_events(
        account_id=account.id,
        days_back=days_back,
        days_ahead=days_ahead,
    )
    return events


@router.get("/accounts/{account_id}/summary")
async def get_account_summary(
    account_id: UUID,
    days: int = Query(30, le=90),
    db: Session = Depends(get_db),
):
    """Generate AI summary for an account."""
    service = WorkNotesService(db)
    account = service.get_account(account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    try:
        summary = await service.generate_account_summary(
            account_id=account.id,
            days=days,
        )
        return {
            **summary,
            "model_used": "gpt-4o-mini",
        }
    except Exception as e:
        logger.exception("summary_generation_failed")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Action Item Management Endpoints
# =============================================================================


class ActionItemUpdate(BaseModel):
    task: str  # Identifies the action item
    status: Optional[str] = None  # pending, completed
    due: Optional[str] = None


class ActionItemDelete(BaseModel):
    task: str  # Identifies the action item to delete


@router.patch("/notes/{note_id}/action-items")
async def update_action_item(
    note_id: UUID,
    request: ActionItemUpdate,
    db: Session = Depends(get_db),
):
    """Update an action item on a note (e.g., mark as completed)."""
    service = WorkNotesService(db)
    note = service.get_note(note_id)
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")

    action_items = note.action_items or []
    updated = False

    for item in action_items:
        if item.get("task") == request.task:
            if request.status is not None:
                item["status"] = request.status
            if request.due is not None:
                item["due"] = request.due
            updated = True
            break

    if not updated:
        raise HTTPException(status_code=404, detail="Action item not found")

    # Update the note
    note.action_items = action_items
    db.commit()
    db.refresh(note)

    return note_to_response(note)


@router.delete("/notes/{note_id}/action-items")
async def delete_action_item(
    note_id: UUID,
    task: str = Query(..., description="The task text to identify the action item"),
    db: Session = Depends(get_db),
):
    """Delete an action item from a note."""
    service = WorkNotesService(db)
    note = service.get_note(note_id)
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")

    action_items = note.action_items or []
    original_count = len(action_items)

    # Filter out the matching action item
    action_items = [item for item in action_items if item.get("task") != task]

    if len(action_items) == original_count:
        raise HTTPException(status_code=404, detail="Action item not found")

    # Update the note
    note.action_items = action_items
    db.commit()
    db.refresh(note)

    return {"status": "deleted", "remaining_items": len(action_items)}


# =============================================================================
# Profile Endpoints
# =============================================================================


class ProfileUpdate(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    company: Optional[str] = None
    department: Optional[str] = None
    responsibilities: Optional[list[str]] = None
    expertise_areas: Optional[list[str]] = None
    goals: Optional[list[str]] = None
    working_style: Optional[str] = None
    key_relationships: Optional[list[dict]] = None
    communication_prefs: Optional[str] = None
    current_priorities: Optional[list[str]] = None


class LearnRequest(BaseModel):
    messages: list[dict[str, str]]
    session_id: Optional[str] = None


class FactVerify(BaseModel):
    verified: bool = True


def profile_to_response(profile) -> dict:
    """Convert WorkUserProfile model to response dict."""
    if not profile:
        return {
            "id": None,
            "name": None,
            "role": None,
            "company": None,
            "department": None,
            "responsibilities": [],
            "expertise_areas": [],
            "goals": [],
            "working_style": None,
            "key_relationships": [],
            "communication_prefs": None,
            "current_priorities": [],
            "learned_facts": [],
            "last_learned_at": None,
            "created_at": None,
            "updated_at": None,
        }
    return {
        "id": profile.id,
        "name": profile.name,
        "role": profile.role,
        "company": profile.company,
        "department": profile.department,
        "responsibilities": profile.responsibilities or [],
        "expertise_areas": profile.expertise_areas or [],
        "goals": profile.goals or [],
        "working_style": profile.working_style,
        "key_relationships": profile.key_relationships or [],
        "communication_prefs": profile.communication_prefs,
        "current_priorities": profile.current_priorities or [],
        "learned_facts": profile.learned_facts or [],
        "last_learned_at": profile.last_learned_at.isoformat() if profile.last_learned_at else None,
        "created_at": profile.created_at.isoformat() if profile.created_at else None,
        "updated_at": profile.updated_at.isoformat() if profile.updated_at else None,
    }


@router.get("/profile")
async def get_profile(db: Session = Depends(get_db)):
    """Get the user's work profile."""
    service = WorkNotesService(db)
    profile = service.get_or_create_profile()
    return profile_to_response(profile)


@router.put("/profile")
async def update_profile(request: ProfileUpdate, db: Session = Depends(get_db)):
    """Update the user's work profile."""
    service = WorkNotesService(db)
    profile = service.update_profile(
        name=request.name,
        role=request.role,
        company=request.company,
        department=request.department,
        responsibilities=request.responsibilities,
        expertise_areas=request.expertise_areas,
        goals=request.goals,
        working_style=request.working_style,
        key_relationships=request.key_relationships,
        communication_prefs=request.communication_prefs,
        current_priorities=request.current_priorities,
    )
    return profile_to_response(profile)


@router.post("/profile/learn")
async def learn_from_chats(request: LearnRequest, db: Session = Depends(get_db)):
    """Extract and learn facts from chat messages."""
    logger.info(
        "learn_from_chats_called",
        message_count=len(request.messages),
        session_id=request.session_id,
    )
    service = WorkNotesService(db)
    try:
        result = await service.learn_from_messages(
            messages=request.messages,
            session_id=request.session_id,
        )
        logger.info(
            "learn_from_chats_result",
            extracted=result.get("extracted", 0),
            added=result.get("added", 0),
        )
        return result
    except Exception as e:
        logger.exception("learn_from_chats_failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/profile/facts/{fact_id}")
async def verify_fact(fact_id: str, request: FactVerify, db: Session = Depends(get_db)):
    """Verify or unverify a learned fact."""
    service = WorkNotesService(db)
    profile = service.verify_fact(fact_id, request.verified)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile or fact not found")
    return profile_to_response(profile)


@router.delete("/profile/facts/{fact_id}")
async def delete_fact(fact_id: str, db: Session = Depends(get_db)):
    """Delete a learned fact."""
    service = WorkNotesService(db)
    if not service.delete_fact(fact_id):
        raise HTTPException(status_code=404, detail="Fact not found")
    return {"status": "deleted", "fact_id": fact_id}
