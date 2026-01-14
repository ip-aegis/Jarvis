from datetime import date, datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.database import get_db
from app.services.journal import JournalService

logger = get_logger(__name__)

router = APIRouter()


# =========================================================================
# Request/Response Models
# =========================================================================


class JournalEntryCreate(BaseModel):
    content: str
    date: Optional[str] = None  # Accept string, convert to date
    title: Optional[str] = None
    mood: Optional[str] = None
    energy_level: Optional[int] = None
    tags: Optional[list[str]] = None

    @field_validator("date", mode="before")
    @classmethod
    def parse_date(cls, v):
        if v is None:
            return None
        if isinstance(v, date):
            return v.isoformat()
        return v


class JournalEntryUpdate(BaseModel):
    content: Optional[str] = None
    title: Optional[str] = None
    mood: Optional[str] = None
    energy_level: Optional[int] = None
    tags: Optional[list[str]] = None
    date: Optional[str] = None  # Accept string, convert to date

    @field_validator("date", mode="before")
    @classmethod
    def parse_date(cls, v):
        if v is None:
            return None
        if isinstance(v, date):
            return v.isoformat()
        return v


class JournalEntryResponse(BaseModel):
    entry_id: str
    date: str
    title: Optional[str]
    content: str
    mood: Optional[str]
    energy_level: Optional[int]
    tags: list[str]
    source: str
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class SummaryApprovalRequest(BaseModel):
    title: Optional[str] = None
    mood: Optional[str] = None
    energy_level: Optional[int] = None
    tags: Optional[list[str]] = None


class SearchRequest(BaseModel):
    query: str
    limit: Optional[int] = 5


# =========================================================================
# Helper Functions
# =========================================================================


def entry_to_response(entry) -> dict:
    """Convert JournalEntry model to response dict."""
    return {
        "entry_id": str(entry.entry_id),
        "date": entry.date.isoformat() if hasattr(entry.date, "isoformat") else str(entry.date),
        "title": entry.title,
        "content": entry.content,
        "mood": entry.mood,
        "energy_level": entry.energy_level,
        "tags": entry.tags or [],
        "source": entry.source,
        "created_at": entry.created_at.isoformat() if entry.created_at else None,
        "updated_at": entry.updated_at.isoformat() if entry.updated_at else None,
    }


def summary_to_response(summary) -> dict:
    """Convert JournalChatSummary model to response dict."""
    return {
        "summary_id": str(summary.summary_id),
        "chat_session_id": summary.chat_session_id,
        "summary_text": summary.summary_text,
        "key_topics": summary.key_topics or [],
        "sentiment": summary.sentiment,
        "status": summary.status,
        "model_used": summary.model_used,
        "tokens_used": summary.tokens_used,
        "created_at": summary.created_at.isoformat() if summary.created_at else None,
        "journal_entry_id": str(summary.journal_entry.entry_id) if summary.journal_entry else None,
    }


# =========================================================================
# Journal Entry Endpoints
# =========================================================================


@router.get("/entries")
async def list_entries(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    mood: Optional[str] = Query(None),
    tags: Optional[str] = Query(None),  # Comma-separated
    limit: int = Query(50, le=100),
    offset: int = Query(0),
    db: Session = Depends(get_db),
):
    """List journal entries with optional filters."""
    service = JournalService(db)

    tag_list = tags.split(",") if tags else None
    entries = service.get_entries(
        start_date=start_date,
        end_date=end_date,
        mood=mood,
        tags=tag_list,
        limit=limit,
        offset=offset,
    )

    return {
        "entries": [entry_to_response(e) for e in entries],
        "count": len(entries),
    }


@router.get("/entries/{entry_id}")
async def get_entry(entry_id: UUID, db: Session = Depends(get_db)):
    """Get a single journal entry."""
    service = JournalService(db)
    entry = service.get_entry(entry_id)

    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")

    return entry_to_response(entry)


@router.post("/entries")
async def create_entry(request: JournalEntryCreate, db: Session = Depends(get_db)):
    """Create a new journal entry."""
    service = JournalService(db)

    # Parse date string to date object
    entry_date = None
    if request.date:
        try:
            entry_date = datetime.strptime(request.date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

    try:
        entry = await service.create_entry(
            content=request.content,
            entry_date=entry_date,
            title=request.title,
            mood=request.mood,
            energy_level=request.energy_level,
            tags=request.tags,
        )
        return entry_to_response(entry)
    except Exception as e:
        logger.exception("create_entry_failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/entries/{entry_id}")
async def update_entry(
    entry_id: UUID,
    request: JournalEntryUpdate,
    db: Session = Depends(get_db),
):
    """Update an existing journal entry."""
    service = JournalService(db)

    # Parse date string to date object
    entry_date = None
    if request.date:
        try:
            entry_date = datetime.strptime(request.date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

    try:
        entry = await service.update_entry(
            entry_id=entry_id,
            content=request.content,
            title=request.title,
            mood=request.mood,
            energy_level=request.energy_level,
            tags=request.tags,
            entry_date=entry_date,
        )

        if not entry:
            raise HTTPException(status_code=404, detail="Entry not found")

        return entry_to_response(entry)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("update_entry_failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/entries/{entry_id}")
async def delete_entry(entry_id: UUID, db: Session = Depends(get_db)):
    """Delete a journal entry."""
    service = JournalService(db)

    if not service.delete_entry(entry_id):
        raise HTTPException(status_code=404, detail="Entry not found")

    return {"status": "deleted", "entry_id": str(entry_id)}


# =========================================================================
# Search Endpoints
# =========================================================================


@router.post("/search")
async def search_entries(request: SearchRequest, db: Session = Depends(get_db)):
    """Search journal entries using semantic similarity."""
    service = JournalService(db)

    try:
        results = await service.semantic_search(
            query=request.query,
            limit=request.limit or 5,
        )

        return {
            "query": request.query,
            "results": [
                {
                    **entry_to_response(entry),
                    "similarity": round(score, 3),
                }
                for entry, score in results
            ],
        }
    except Exception as e:
        logger.exception("search_failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/search")
async def search_entries_get(
    q: str = Query(..., min_length=1),
    limit: int = Query(5, le=20),
    db: Session = Depends(get_db),
):
    """Search journal entries using semantic similarity (GET version)."""
    service = JournalService(db)

    try:
        results = await service.semantic_search(query=q, limit=limit)

        return {
            "query": q,
            "results": [
                {
                    **entry_to_response(entry),
                    "similarity": round(score, 3),
                }
                for entry, score in results
            ],
        }
    except Exception as e:
        logger.exception("search_failed")
        raise HTTPException(status_code=500, detail=str(e))


# =========================================================================
# Chat Summary Endpoints
# =========================================================================


@router.post("/sessions/{session_id}/summarize")
async def generate_summary(session_id: str, db: Session = Depends(get_db)):
    """Generate a journal summary from a chat session."""
    service = JournalService(db)

    try:
        summary = await service.generate_chat_summary(session_id)

        if not summary:
            raise HTTPException(status_code=404, detail="Session not found or has no messages")

        return summary_to_response(summary)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("summary_generation_failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/summaries")
async def list_pending_summaries(db: Session = Depends(get_db)):
    """List all pending summaries awaiting approval."""
    service = JournalService(db)
    summaries = service.get_pending_summaries()

    return {
        "summaries": [summary_to_response(s) for s in summaries],
        "count": len(summaries),
    }


@router.post("/summaries/{summary_id}/approve")
async def approve_summary(
    summary_id: UUID,
    request: SummaryApprovalRequest,
    db: Session = Depends(get_db),
):
    """Approve a summary and create a journal entry from it."""
    service = JournalService(db)

    try:
        entry = await service.approve_summary(
            summary_id=summary_id,
            title=request.title,
            mood=request.mood,
            energy_level=request.energy_level,
            tags=request.tags,
        )

        if not entry:
            raise HTTPException(status_code=404, detail="Summary not found or already processed")

        return {
            "status": "approved",
            "entry": entry_to_response(entry),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("summary_approval_failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/summaries/{summary_id}")
async def reject_summary(summary_id: UUID, db: Session = Depends(get_db)):
    """Reject a summary."""
    service = JournalService(db)

    if not service.reject_summary(summary_id):
        raise HTTPException(status_code=404, detail="Summary not found")

    return {"status": "rejected", "summary_id": str(summary_id)}


# =========================================================================
# Calendar & Stats Endpoints
# =========================================================================


@router.get("/calendar/{year}/{month}")
async def get_calendar(year: int, month: int, db: Session = Depends(get_db)):
    """Get calendar data for a specific month."""
    if month < 1 or month > 12:
        raise HTTPException(status_code=400, detail="Invalid month")

    service = JournalService(db)
    return service.get_calendar_data(year, month)


@router.get("/stats")
async def get_stats(db: Session = Depends(get_db)):
    """Get journal statistics."""
    service = JournalService(db)
    return service.get_stats()


# =========================================================================
# Context Endpoint (for LLM integration)
# =========================================================================


@router.get("/context")
async def get_journal_context(
    query: Optional[str] = Query(None),
    days: int = Query(7, le=30),
    db: Session = Depends(get_db),
):
    """Get journal context for LLM consumption."""
    service = JournalService(db)

    try:
        context = await service.build_journal_context(
            query=query,
            include_recent_days=days,
        )
        return {"context": context}
    except Exception as e:
        logger.exception("context_build_failed")
        raise HTTPException(status_code=500, detail=str(e))


# =========================================================================
# User Profile Endpoints
# =========================================================================


class ProfileUpdateRequest(BaseModel):
    name: Optional[str] = None
    nickname: Optional[str] = None
    life_context: Optional[dict] = None
    interests: Optional[list[str]] = None
    goals: Optional[list[str]] = None
    challenges: Optional[list[str]] = None
    values: Optional[list[str]] = None
    communication_style: Optional[str] = None


def profile_to_response(profile) -> dict:
    """Convert JournalUserProfile model to response dict."""
    if not profile:
        return None
    return {
        "id": profile.id,
        "name": profile.name,
        "nickname": profile.nickname,
        "life_context": profile.life_context or {},
        "interests": profile.interests or [],
        "goals": profile.goals or [],
        "challenges": profile.challenges or [],
        "values": profile.values or [],
        "communication_style": profile.communication_style,
        "learned_facts": profile.learned_facts or [],
        "learned_facts_count": len(profile.learned_facts or []),
        "last_learned_at": profile.last_learned_at.isoformat() if profile.last_learned_at else None,
        "created_at": profile.created_at.isoformat() if profile.created_at else None,
        "updated_at": profile.updated_at.isoformat() if profile.updated_at else None,
    }


@router.get("/profile")
async def get_profile(db: Session = Depends(get_db)):
    """Get the user's journal profile."""
    service = JournalService(db)
    profile = service.get_profile()

    if not profile:
        return {"profile": None, "message": "No profile yet. It will be created as you chat."}

    return {"profile": profile_to_response(profile)}


@router.put("/profile")
async def update_profile(request: ProfileUpdateRequest, db: Session = Depends(get_db)):
    """Update the user's journal profile."""
    service = JournalService(db)

    try:
        profile = service.update_profile(
            name=request.name,
            nickname=request.nickname,
            life_context=request.life_context,
            interests=request.interests,
            goals=request.goals,
            challenges=request.challenges,
            values=request.values,
            communication_style=request.communication_style,
        )
        return {"profile": profile_to_response(profile)}
    except Exception as e:
        logger.exception("profile_update_failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/profile/facts/{fact_id}")
async def delete_fact(fact_id: str, db: Session = Depends(get_db)):
    """Delete a learned fact from the profile."""
    service = JournalService(db)

    if not service.delete_fact(fact_id):
        raise HTTPException(status_code=404, detail="Fact not found")

    return {"status": "deleted", "fact_id": fact_id}


@router.post("/profile/facts/{fact_id}/verify")
async def verify_fact(fact_id: str, verified: bool = True, db: Session = Depends(get_db)):
    """Mark a learned fact as verified or unverified."""
    service = JournalService(db)

    profile = service.verify_fact(fact_id, verified)
    if not profile:
        raise HTTPException(status_code=404, detail="Fact not found")

    return {"status": "verified" if verified else "unverified", "fact_id": fact_id}


# =========================================================================
# Retroactive Processing Endpoints
# =========================================================================


@router.post("/retroactive/process")
async def process_retroactive(
    limit: int = Query(100, le=500),
    db: Session = Depends(get_db),
):
    """Process existing journal chat sessions retroactively.

    This will:
    1. Find all journal chat sessions that haven't been summarized
    2. Extract facts from each session and add to user profile
    3. Generate summaries and auto-approve them as journal entries
    """
    from app.services.journal_tasks import journal_processor

    try:
        results = await journal_processor.process_retroactive(limit=limit)
        return {
            "status": "completed",
            "results": results,
        }
    except Exception as e:
        logger.exception("retroactive_processing_failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/retroactive/status")
async def get_retroactive_status(db: Session = Depends(get_db)):
    """Get status of journal sessions that could be processed retroactively."""
    from app.models import ChatSession, JournalChatSummary

    # Count total journal sessions
    total_sessions = db.query(ChatSession).filter(ChatSession.context == "journal").count()

    # Count sessions with summaries
    summarized_session_ids = (
        db.query(JournalChatSummary.chat_session_id)
        .filter(JournalChatSummary.chat_session_id.isnot(None))
        .distinct()
        .all()
    )
    summarized_count = len(summarized_session_ids)

    # Get profile stats
    service = JournalService(db)
    profile = service.get_profile()

    return {
        "total_journal_sessions": total_sessions,
        "summarized_sessions": summarized_count,
        "pending_sessions": total_sessions - summarized_count,
        "profile_exists": profile is not None,
        "learned_facts_count": len(profile.learned_facts) if profile else 0,
    }


# =============================================================================
# Fact Extraction Visibility
# =============================================================================


@router.get("/extractions/recent")
async def get_recent_extractions(
    limit: int = Query(50, le=200),
    status: Optional[str] = Query(
        None, description="Filter by status: added, duplicate, low_confidence"
    ),
    db: Session = Depends(get_db),
):
    """Get recent fact extractions for visibility into what was learned/filtered."""
    from app.models import JournalFactExtraction

    query = db.query(JournalFactExtraction).order_by(JournalFactExtraction.extracted_at.desc())

    if status:
        query = query.filter(JournalFactExtraction.status == status)

    extractions = query.limit(limit).all()

    return {
        "extractions": [
            {
                "id": e.id,
                "session_id": e.session_id,
                "extracted_at": e.extracted_at.isoformat() if e.extracted_at else None,
                "fact_text": e.fact_text,
                "category": e.category,
                "confidence": e.confidence,
                "status": e.status,
                "duplicate_of": e.duplicate_of,
            }
            for e in extractions
        ],
        "total": len(extractions),
    }


@router.post("/extractions/{extraction_id}/add")
async def add_filtered_extraction(
    extraction_id: int,
    db: Session = Depends(get_db),
):
    """Manually add a filtered extraction as a learned fact."""
    from app.models import JournalFactExtraction

    extraction = db.query(JournalFactExtraction).filter_by(id=extraction_id).first()
    if not extraction:
        raise HTTPException(status_code=404, detail="Extraction not found")

    if extraction.status == "added":
        raise HTTPException(status_code=400, detail="This fact was already added")

    service = JournalService(db)
    service.add_learned_fact(
        fact=extraction.fact_text,
        category=extraction.category or "general",
        confidence=extraction.confidence or 0.5,
        source_session_id=extraction.session_id,
    )

    # Update extraction status
    extraction.status = "added"
    db.commit()

    return {"status": "ok", "message": "Fact added to profile"}
