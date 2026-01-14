import json
import re
from datetime import date, datetime, timedelta
from typing import Any, Optional
from uuid import UUID

import psycopg2
import tiktoken
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.logging import get_logger
from app.models import WorkAccount, WorkNote, WorkUserProfile
from app.services.llm_usage import log_llm_usage
from app.services.openai_service import OpenAIService

logger = get_logger(__name__)


class WorkNotesService:
    """Service for managing work accounts and notes with RAG capabilities."""

    def __init__(self, db: Session):
        self.db = db
        self.openai = OpenAIService()
        self.tokenizer = tiktoken.encoding_for_model("gpt-4")
        self.max_context_tokens = 6000  # Larger budget for work context

    # =========================================================================
    # Account Operations
    # =========================================================================

    # Common company suffixes to strip for matching
    COMPANY_SUFFIXES = [
        r"\s*,?\s*inc\.?$",
        r"\s*,?\s*incorporated$",
        r"\s*,?\s*llc\.?$",
        r"\s*,?\s*l\.l\.c\.?$",
        r"\s*,?\s*corp\.?$",
        r"\s*,?\s*corporation$",
        r"\s*,?\s*ltd\.?$",
        r"\s*,?\s*limited$",
        r"\s*,?\s*co\.?$",
        r"\s*,?\s*company$",
        r"\s*,?\s*plc\.?$",
        r"\s*,?\s*gmbh$",
        r"\s*,?\s*ag$",
        r"\s*,?\s*sa$",
        r"\s*,?\s*nv$",
        r"\s*,?\s*bv$",
        r"\s*,?\s*pty\.?$",
        r"\s*,?\s*pvt\.?$",
        r"\s*,?\s*private$",
        r"\s*,?\s*systems$",
        r"\s*,?\s*technologies$",
        r"\s*,?\s*technology$",
        r"\s*,?\s*tech$",
        r"\s*,?\s*solutions$",
        r"\s*,?\s*services$",
        r"\s*,?\s*group$",
        r"\s*,?\s*holdings$",
        r"\s*,?\s*enterprises$",
        r"\s*,?\s*international$",
        r"\s*,?\s*intl\.?$",
        r"\s*,?\s*global$",
        r"\s*,?\s*worldwide$",
    ]

    def normalize_name(self, name: str) -> str:
        """Normalize account name for matching."""
        return re.sub(r"[^a-z0-9]", "", name.lower())

    def normalize_company_name(self, name: str) -> str:
        """
        Normalize company name by stripping common suffixes.
        Returns the core company name for better matching.
        Example: "Cisco Systems, Inc." -> "cisco"
        """
        normalized = name.lower().strip()
        # Strip common suffixes (apply multiple times for compound suffixes)
        for _ in range(3):
            for suffix in self.COMPANY_SUFFIXES:
                normalized = re.sub(suffix, "", normalized, flags=re.IGNORECASE)
        # Remove remaining punctuation and extra spaces
        normalized = re.sub(r"[^a-z0-9\s]", "", normalized)
        normalized = re.sub(r"\s+", "", normalized).strip()
        return normalized

    def search_accounts(
        self,
        query: str,
        limit: int = 10,
    ) -> list[tuple[WorkAccount, float]]:
        """
        Search for accounts by name with fuzzy matching.
        Returns accounts with match confidence scores.
        """
        normalized_query = self.normalize_name(query)
        core_query = self.normalize_company_name(query)

        # Exact match on normalized name
        exact = (
            self.db.query(WorkAccount)
            .filter(WorkAccount.normalized_name == normalized_query)
            .first()
        )
        if exact:
            return [(exact, 1.0)]

        # Get all accounts for comprehensive matching
        all_accounts = self.db.query(WorkAccount).all()
        results = []
        seen_ids = set()

        for account in all_accounts:
            core_account = self.normalize_company_name(account.name)
            score = 0.0

            # Check for core name match (e.g., "cisco" matches "cisco")
            if core_query == core_account:
                score = 0.95  # Very high - core names match exactly
            # Check if query core is contained in account core or vice versa
            elif core_query and core_account:
                if core_query in core_account:
                    # Query is substring of account (e.g., "cisco" in "ciscosystems")
                    score = len(core_query) / len(core_account) * 0.9
                elif core_account in core_query:
                    # Account is substring of query
                    score = len(core_account) / len(core_query) * 0.85

            # Also check traditional normalized name matching
            if score < 0.5:
                if normalized_query in account.normalized_name:
                    score = max(score, len(normalized_query) / len(account.normalized_name) * 0.7)
                elif account.normalized_name in normalized_query:
                    score = max(score, 0.6)

            # Check aliases
            for alias in account.aliases or []:
                core_alias = self.normalize_company_name(alias)
                if core_query == core_alias:
                    score = max(score, 0.9)
                elif core_query in core_alias or core_alias in core_query:
                    score = max(score, 0.75)

            if score > 0.3:
                results.append((account, score))
                seen_ids.add(account.id)

        return sorted(results, key=lambda x: -x[1])[:limit]

    def get_or_create_account(
        self,
        name: str,
        auto_create: bool = False,
    ) -> tuple[Optional[WorkAccount], bool, list[tuple[WorkAccount, float]]]:
        """
        Smart account resolution:
        - Returns (account, was_created, suggestions)
        - If exact match found: returns (account, False, [])
        - If auto_create and no match: creates new account
        - If not auto_create and no match: returns (None, False, suggestions)
        """
        matches = self.search_accounts(name)

        # High confidence match (>0.9)
        if matches and matches[0][1] > 0.9:
            return (matches[0][0], False, [])

        # No good match - create or suggest
        if auto_create:
            account = self.create_account(name)
            return (account, True, [])
        else:
            return (None, False, matches)

    def create_account(
        self,
        name: str,
        description: Optional[str] = None,
        contacts: Optional[list[dict]] = None,
        metadata: Optional[dict] = None,
    ) -> WorkAccount:
        """Create a new work account."""
        account = WorkAccount(
            name=name,
            normalized_name=self.normalize_name(name),
            description=description,
            contacts=contacts or [],
            extra_data=metadata or {},
            aliases=[],
        )
        self.db.add(account)
        self.db.commit()
        self.db.refresh(account)
        logger.info("account_created", name=name, account_id=str(account.account_id))
        return account

    def update_account(
        self,
        account_id: UUID,
        name: Optional[str] = None,
        description: Optional[str] = None,
        contacts: Optional[list[dict]] = None,
        metadata: Optional[dict] = None,
        aliases: Optional[list[str]] = None,
        status: Optional[str] = None,
    ) -> Optional[WorkAccount]:
        """Update an existing account."""
        account = self.db.query(WorkAccount).filter_by(account_id=account_id).first()
        if not account:
            return None

        if name:
            account.name = name
            account.normalized_name = self.normalize_name(name)
        if description is not None:
            account.description = description
        if contacts is not None:
            account.contacts = contacts
        if metadata is not None:
            account.extra_data = metadata
        if aliases is not None:
            account.aliases = aliases
        if status:
            account.status = status

        account.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(account)
        return account

    def get_account(self, account_id: UUID) -> Optional[WorkAccount]:
        """Get account by UUID."""
        return self.db.query(WorkAccount).filter_by(account_id=account_id).first()

    def get_account_by_id(self, id: int) -> Optional[WorkAccount]:
        """Get account by internal ID."""
        return self.db.query(WorkAccount).filter_by(id=id).first()

    def list_accounts(
        self,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[WorkAccount]:
        """List all accounts with optional filters."""
        query = self.db.query(WorkAccount)
        if status:
            query = query.filter(WorkAccount.status == status)
        return query.order_by(WorkAccount.updated_at.desc()).offset(offset).limit(limit).all()

    def delete_account(self, account_id: UUID) -> bool:
        """Delete an account and all its notes."""
        account = self.db.query(WorkAccount).filter_by(account_id=account_id).first()
        if not account:
            return False
        self.db.delete(account)
        self.db.commit()
        return True

    # =========================================================================
    # Note Operations
    # =========================================================================

    async def create_note(
        self,
        account_id: int,
        content: str,
        activity_type: Optional[str] = None,
        activity_date: Optional[datetime] = None,
        source: str = "manual",
        source_session_id: Optional[str] = None,
        extract_entities: bool = True,
    ) -> WorkNote:
        """Create a new work note and generate embedding."""
        note = WorkNote(
            account_id=account_id,
            content=content,
            activity_type=activity_type,
            activity_date=activity_date or datetime.utcnow(),
            source=source,
            source_session_id=source_session_id,
            mentioned_contacts=[],
            action_items=[],
            tags=[],
        )
        self.db.add(note)
        self.db.commit()
        self.db.refresh(note)

        # Generate embedding
        await self._update_embedding(note)

        # Optionally extract entities using LLM
        if extract_entities:
            await self._extract_entities(note)

        logger.info("note_created", note_id=str(note.note_id), account_id=account_id)
        return note

    async def append_note(
        self,
        account_name: str,
        content: str,
        activity_type: Optional[str] = None,
        auto_create_account: bool = False,
    ) -> tuple[Optional[WorkNote], Optional[WorkAccount], bool, list[tuple[WorkAccount, float]]]:
        """
        Append a note to an account.
        Returns: (note, account, was_account_created, account_suggestions)
        """
        account, was_created, suggestions = self.get_or_create_account(
            account_name,
            auto_create=auto_create_account,
        )

        if not account:
            return (None, None, False, suggestions)

        note = await self.create_note(
            account_id=account.id,
            content=content,
            activity_type=activity_type,
        )

        return (note, account, was_created, [])

    async def update_note(
        self,
        note_id: UUID,
        content: Optional[str] = None,
        activity_type: Optional[str] = None,
        activity_date: Optional[datetime] = None,
        tags: Optional[list[str]] = None,
    ) -> Optional[WorkNote]:
        """Update an existing note."""
        note = self.db.query(WorkNote).filter_by(note_id=note_id).first()
        if not note:
            return None

        content_changed = False
        if content is not None and content != note.content:
            note.content = content
            content_changed = True
        if activity_type is not None:
            note.activity_type = activity_type
        if activity_date is not None:
            note.activity_date = activity_date
        if tags is not None:
            note.tags = tags

        note.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(note)

        if content_changed:
            await self._update_embedding(note)
            await self._extract_entities(note)

        return note

    def delete_note(self, note_id: UUID) -> bool:
        """Delete a note."""
        note = self.db.query(WorkNote).filter_by(note_id=note_id).first()
        if not note:
            return False
        self.db.delete(note)
        self.db.commit()
        return True

    def get_note(self, note_id: UUID) -> Optional[WorkNote]:
        """Get a note by UUID."""
        return self.db.query(WorkNote).filter_by(note_id=note_id).first()

    def get_notes_for_account(
        self,
        account_id: int,
        limit: int = 50,
        offset: int = 0,
    ) -> list[WorkNote]:
        """Get notes for a specific account."""
        return (
            self.db.query(WorkNote)
            .filter_by(account_id=account_id)
            .order_by(WorkNote.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

    def get_recent_notes(
        self,
        days: int = 30,
        limit: int = 50,
    ) -> list[WorkNote]:
        """Get recent notes across all accounts."""
        cutoff = datetime.utcnow() - timedelta(days=days)
        return (
            self.db.query(WorkNote)
            .filter(WorkNote.created_at >= cutoff)
            .order_by(WorkNote.created_at.desc())
            .limit(limit)
            .all()
        )

    # =========================================================================
    # Embedding & RAG Operations
    # =========================================================================

    async def _update_embedding(self, note: WorkNote) -> None:
        """Generate and store embedding for a note."""
        try:
            # Include account name for better context
            account = self.db.query(WorkAccount).filter_by(id=note.account_id).first()
            text_to_embed = (
                f"Account: {account.name}\n\n{note.content}" if account else note.content
            )

            embedding, usage = await self.openai.generate_embedding_with_usage(text_to_embed)

            # Log usage
            log_llm_usage(
                feature="work",
                model=usage.model,
                prompt_tokens=usage.prompt_tokens,
                completion_tokens=usage.completion_tokens,
                function_name="note_embedding",
            )

            self.db.execute(
                text("UPDATE work_notes SET embedding = :embedding WHERE id = :id"),
                {"embedding": str(embedding), "id": note.id},
            )
            self.db.commit()
        except Exception as e:
            logger.error("embedding_update_failed", note_id=str(note.note_id), error=str(e))

    async def _extract_entities(self, note: WorkNote) -> None:
        """Use LLM to extract structured data from note content."""
        try:
            prompt = [
                {
                    "role": "system",
                    "content": """Extract structured information from this work note.
Return JSON with:
{
  "activity_type": "meeting|call|email|task|note|follow_up" (best guess if not provided),
  "mentioned_contacts": ["Name1", "Name2"],
  "action_items": [{"task": "...", "due": "YYYY-MM-DD or null"}],
  "tags": ["relevant", "tags"]
}
Only include fields where you found relevant info. Be concise.""",
                },
                {"role": "user", "content": note.content},
            ]

            response, usage = await self.openai.chat_with_usage(prompt, model="gpt-4o-mini")

            # Log usage
            log_llm_usage(
                feature="work",
                model=usage.model,
                prompt_tokens=usage.prompt_tokens,
                completion_tokens=usage.completion_tokens,
                function_name="entity_extraction",
            )

            data = json.loads(response)

            if data.get("activity_type") and not note.activity_type:
                note.activity_type = data["activity_type"]
            if data.get("mentioned_contacts"):
                note.mentioned_contacts = data["mentioned_contacts"]
            if data.get("action_items"):
                note.action_items = data["action_items"]
            if data.get("tags"):
                note.tags = data["tags"]

            self.db.commit()
        except Exception as e:
            logger.warning("entity_extraction_failed", note_id=str(note.note_id), error=str(e))

    async def semantic_search(
        self,
        query: str,
        account_id: Optional[int] = None,
        limit: int = 10,
        min_similarity: float = 0.1,
    ) -> list[tuple[WorkNote, float]]:
        """Search notes using semantic similarity."""
        try:
            query_embedding, usage = await self.openai.generate_embedding_with_usage(query)

            # Log usage
            log_llm_usage(
                feature="work",
                model=usage.model,
                prompt_tokens=usage.prompt_tokens,
                completion_tokens=usage.completion_tokens,
                function_name="semantic_search",
            )

            embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

            settings = get_settings()
            conn = psycopg2.connect(settings.database_url)
            cur = conn.cursor()

            account_filter = f"AND account_id = {account_id}" if account_id else ""

            sql = f"""
                SELECT id, similarity
                FROM (
                    SELECT id, 1 - (embedding <=> '{embedding_str}'::vector) as similarity
                    FROM work_notes
                    WHERE embedding IS NOT NULL {account_filter}
                ) subq
                WHERE similarity >= {min_similarity}
                ORDER BY similarity DESC
                LIMIT {limit}
            """
            cur.execute(sql)
            rows = cur.fetchall()
            cur.close()
            conn.close()

            results = []
            for row in rows:
                note_id, similarity = row
                note = self.db.query(WorkNote).filter_by(id=note_id).first()
                if note:
                    results.append((note, similarity))

            return results
        except Exception as e:
            logger.error("semantic_search_failed", error=str(e))
            return []

    # =========================================================================
    # Context Building for LLM
    # =========================================================================

    def _count_tokens(self, text: str) -> int:
        return len(self.tokenizer.encode(text))

    async def build_account_context(
        self,
        account_id: int,
        query: Optional[str] = None,
        include_recent_days: int = 30,
        max_notes: int = 10,
    ) -> str:
        """Build context for LLM about a specific account."""
        account = self.db.query(WorkAccount).filter_by(id=account_id).first()
        if not account:
            return ""

        context_parts = []
        remaining_tokens = self.max_context_tokens

        # Account header
        header = f"# Account: {account.name}\n\n"
        if account.description:
            header += f"{account.description}\n\n"
        if account.contacts:
            header += "## Contacts\n"
            for contact in account.contacts:
                header += f"- {contact.get('name', 'Unknown')}"
                if contact.get("role"):
                    header += f" ({contact['role']})"
                if contact.get("email"):
                    header += f" - {contact['email']}"
                header += "\n"
            header += "\n"

        context_parts.append(header)
        remaining_tokens -= self._count_tokens(header)

        # Recent notes
        recent_notes = self.get_notes_for_account(account_id, limit=max_notes)
        if recent_notes:
            notes_section = "## Recent Notes\n\n"
            for note in recent_notes[:5]:
                note_text = self._format_note_for_context(note)
                tokens = self._count_tokens(note_text)
                if tokens < remaining_tokens:
                    notes_section += note_text + "\n---\n"
                    remaining_tokens -= tokens
            context_parts.append(notes_section)

        # RAG results if query
        if query and remaining_tokens > 500:
            rag_results = await self.semantic_search(query, account_id=account_id, limit=5)
            if rag_results:
                rag_section = "## Relevant Historical Notes\n\n"
                seen_ids = {n.id for n in recent_notes[:5]}
                for note, score in rag_results:
                    if note.id in seen_ids:
                        continue
                    note_text = self._format_note_for_context(note)
                    tokens = self._count_tokens(note_text)
                    if tokens < remaining_tokens:
                        rag_section += f"(Relevance: {score:.2f})\n{note_text}\n---\n"
                        remaining_tokens -= tokens
                context_parts.append(rag_section)

        return "\n".join(context_parts)

    def _format_note_for_context(self, note: WorkNote) -> str:
        """Format a note for LLM context."""
        date_str = note.created_at.strftime("%Y-%m-%d") if note.created_at else "Unknown"
        parts = [f"**{date_str}**"]
        if note.activity_type:
            parts.append(f" [{note.activity_type}]")
        parts.append(f"\n{note.content[:500]}")
        if len(note.content) > 500:
            parts.append("...")
        if note.action_items:
            parts.append(
                "\nAction Items: "
                + ", ".join(item.get("task", "") for item in note.action_items[:3])
            )
        return "".join(parts)

    # =========================================================================
    # Statistics
    # =========================================================================

    def get_account_stats(self, account_id: int) -> dict[str, Any]:
        """Get statistics for an account."""
        account = self.db.query(WorkAccount).filter_by(id=account_id).first()
        if not account:
            return {}

        note_count = self.db.query(WorkNote).filter_by(account_id=account_id).count()

        # Activity distribution
        activity_query = self.db.execute(
            text(
                """
                SELECT activity_type, COUNT(*) as count
                FROM work_notes
                WHERE account_id = :aid AND activity_type IS NOT NULL
                GROUP BY activity_type
            """
            ),
            {"aid": account_id},
        )
        activity_distribution = {row.activity_type: row.count for row in activity_query}

        # Recent activity
        last_note = (
            self.db.query(WorkNote)
            .filter_by(account_id=account_id)
            .order_by(WorkNote.created_at.desc())
            .first()
        )

        # Pending action items
        pending_actions = []
        notes_with_actions = (
            self.db.query(WorkNote)
            .filter(WorkNote.account_id == account_id, WorkNote.action_items.isnot(None))
            .all()
        )
        for note in notes_with_actions:
            for item in note.action_items or []:
                if item.get("status") != "completed":
                    pending_actions.append(
                        {
                            **item,
                            "note_date": note.created_at.isoformat() if note.created_at else None,
                        }
                    )

        return {
            "account_name": account.name,
            "total_notes": note_count,
            "activity_distribution": activity_distribution,
            "last_activity": last_note.created_at.isoformat() if last_note else None,
            "pending_action_items": pending_actions[:10],
            "contact_count": len(account.contacts or []),
        }

    def get_global_stats(self) -> dict[str, Any]:
        """Get statistics across all accounts."""
        total_accounts = self.db.query(WorkAccount).count()
        total_notes = self.db.query(WorkNote).count()

        # Accounts by status
        status_query = self.db.execute(
            text("SELECT status, COUNT(*) as count FROM work_accounts GROUP BY status")
        )
        status_distribution = {row.status: row.count for row in status_query}

        # Activity distribution
        activity_query = self.db.execute(
            text(
                """
                SELECT activity_type, COUNT(*) as count
                FROM work_notes
                WHERE activity_type IS NOT NULL
                GROUP BY activity_type
            """
            )
        )
        activity_distribution = {row.activity_type: row.count for row in activity_query}

        # Most active accounts
        active_query = self.db.execute(
            text(
                """
                SELECT wa.name, COUNT(wn.id) as note_count
                FROM work_accounts wa
                LEFT JOIN work_notes wn ON wa.id = wn.account_id
                GROUP BY wa.id, wa.name
                ORDER BY note_count DESC
                LIMIT 5
            """
            )
        )
        most_active = [{"name": row.name, "note_count": row.note_count} for row in active_query]

        return {
            "total_accounts": total_accounts,
            "total_notes": total_notes,
            "status_distribution": status_distribution,
            "activity_distribution": activity_distribution,
            "most_active_accounts": most_active,
        }

    # =========================================================================
    # Events & Summary
    # =========================================================================

    def get_account_events(
        self,
        account_id: int,
        days_back: int = 30,
        days_ahead: int = 30,
    ) -> dict[str, list[dict[str, Any]]]:
        """
        Get events for an account including:
        - Action items with due dates (upcoming, overdue)
        - Scheduled activities with activity_date
        """
        today = date.today()
        past_cutoff = today - timedelta(days=days_back)
        future_cutoff = today + timedelta(days=days_ahead)

        upcoming = []
        recent = []
        overdue = []

        # Get all notes for this account
        notes = self.db.query(WorkNote).filter_by(account_id=account_id).all()

        for note in notes:
            # Process action items with due dates
            for item in note.action_items or []:
                if not item.get("due"):
                    continue
                if item.get("status") == "completed":
                    continue

                try:
                    due_date = datetime.strptime(item["due"], "%Y-%m-%d").date()
                except (ValueError, TypeError):
                    continue

                event = {
                    "type": "action_item",
                    "task": item.get("task", ""),
                    "date": item["due"],
                    "note_id": str(note.note_id),
                    "content_preview": note.content[:100] + "..."
                    if len(note.content) > 100
                    else note.content,
                }

                if due_date < today:
                    overdue.append(event)
                elif due_date <= future_cutoff:
                    upcoming.append(event)

            # Process activities with activity_date
            if note.activity_date:
                activity_date = (
                    note.activity_date.date()
                    if isinstance(note.activity_date, datetime)
                    else note.activity_date
                )

                event = {
                    "type": "activity",
                    "activity_type": note.activity_type or "note",
                    "date": activity_date.isoformat(),
                    "note_id": str(note.note_id),
                    "content_preview": note.content[:100] + "..."
                    if len(note.content) > 100
                    else note.content,
                }

                if activity_date >= today and activity_date <= future_cutoff:
                    upcoming.append(event)
                elif activity_date >= past_cutoff and activity_date < today:
                    recent.append(event)

        # Sort by date
        upcoming.sort(key=lambda x: x["date"])
        recent.sort(key=lambda x: x["date"], reverse=True)
        overdue.sort(key=lambda x: x["date"])

        return {
            "upcoming": upcoming,
            "recent": recent,
            "overdue": overdue,
        }

    async def generate_account_summary(
        self,
        account_id: int,
        days: int = 30,
    ) -> dict[str, str]:
        """
        Generate AI summary for an account including:
        - Account overview (relationship, key themes, status)
        - Recent activity summary (last N days)
        """
        account = self.db.query(WorkAccount).filter_by(id=account_id).first()
        if not account:
            return {"account_overview": "", "recent_activity_summary": ""}

        # Build context
        context = await self.build_account_context(
            account_id, include_recent_days=days, max_notes=15
        )

        # Get recent notes count and activity types
        cutoff = datetime.utcnow() - timedelta(days=days)
        recent_notes = (
            self.db.query(WorkNote)
            .filter(WorkNote.account_id == account_id, WorkNote.created_at >= cutoff)
            .all()
        )

        activity_summary = {}
        for note in recent_notes:
            activity_type = note.activity_type or "note"
            activity_summary[activity_type] = activity_summary.get(activity_type, 0) + 1

        # Build prompt
        prompt = [
            {
                "role": "system",
                "content": """You are a helpful assistant summarizing work account information.
Generate two summaries based on the provided context:

1. **Account Overview**: A 2-3 sentence high-level summary of the relationship - who they are, key themes, current status, and important contacts.

2. **Recent Activity Summary**: A 2-3 sentence summary of what's happened in the recent period - key activities, outcomes, and any pending items.

Return JSON format:
{
  "account_overview": "...",
  "recent_activity_summary": "..."
}

Be concise and focus on actionable insights. If there's limited information, acknowledge that briefly.""",
            },
            {
                "role": "user",
                "content": f"""Account: {account.name}
Status: {account.status}

Recent activity ({days} days): {len(recent_notes)} notes
Activity breakdown: {json.dumps(activity_summary)}

Context:
{context}

Generate the summaries.""",
            },
        ]

        try:
            response, usage = await self.openai.chat_with_usage(prompt, model="gpt-4o-mini")

            # Log usage
            log_llm_usage(
                feature="work",
                model=usage.model,
                prompt_tokens=usage.prompt_tokens,
                completion_tokens=usage.completion_tokens,
                function_name="account_summary",
            )

            data = json.loads(response)
            return {
                "account_overview": data.get("account_overview", ""),
                "recent_activity_summary": data.get("recent_activity_summary", ""),
            }
        except Exception as e:
            logger.error("summary_generation_failed", account_id=account_id, error=str(e))
            return {
                "account_overview": f"Unable to generate summary: {str(e)}",
                "recent_activity_summary": "",
            }

    # =========================================================================
    # User Profile Management
    # =========================================================================

    def get_profile(self) -> Optional[WorkUserProfile]:
        """Get the user's work profile (singleton)."""
        return self.db.query(WorkUserProfile).first()

    def get_or_create_profile(self) -> WorkUserProfile:
        """Get existing profile or create a new empty one."""
        profile = self.get_profile()
        if not profile:
            profile = WorkUserProfile(
                learned_facts=[],
                responsibilities=[],
                expertise_areas=[],
                goals=[],
                key_relationships=[],
                current_priorities=[],
            )
            self.db.add(profile)
            self.db.commit()
            self.db.refresh(profile)
        return profile

    def update_profile(
        self,
        name: Optional[str] = None,
        role: Optional[str] = None,
        company: Optional[str] = None,
        department: Optional[str] = None,
        responsibilities: Optional[list[str]] = None,
        expertise_areas: Optional[list[str]] = None,
        goals: Optional[list[str]] = None,
        working_style: Optional[str] = None,
        key_relationships: Optional[list[dict]] = None,
        communication_prefs: Optional[str] = None,
        current_priorities: Optional[list[str]] = None,
    ) -> WorkUserProfile:
        """Update profile fields."""
        profile = self.get_or_create_profile()

        if name is not None:
            profile.name = name
        if role is not None:
            profile.role = role
        if company is not None:
            profile.company = company
        if department is not None:
            profile.department = department
        if responsibilities is not None:
            profile.responsibilities = responsibilities
        if expertise_areas is not None:
            profile.expertise_areas = expertise_areas
        if goals is not None:
            profile.goals = goals
        if working_style is not None:
            profile.working_style = working_style
        if key_relationships is not None:
            profile.key_relationships = key_relationships
        if communication_prefs is not None:
            profile.communication_prefs = communication_prefs
        if current_priorities is not None:
            profile.current_priorities = current_priorities

        self.db.commit()
        self.db.refresh(profile)
        return profile

    def add_learned_fact(
        self,
        fact: str,
        category: str,
        confidence: float = 0.8,
        source_session_id: Optional[str] = None,
    ) -> WorkUserProfile:
        """Add a new learned fact to the profile."""
        import uuid

        profile = self.get_or_create_profile()
        facts = profile.learned_facts or []

        new_fact = {
            "id": str(uuid.uuid4()),
            "fact": fact,
            "category": category,
            "confidence": confidence,
            "source_session_id": source_session_id,
            "learned_at": datetime.utcnow().isoformat(),
            "verified": False,
        }
        facts.append(new_fact)

        profile.learned_facts = facts
        profile.last_learned_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(profile)
        return profile

    def verify_fact(self, fact_id: str, verified: bool = True) -> Optional[WorkUserProfile]:
        """Mark a learned fact as verified or unverified."""
        profile = self.get_profile()
        if not profile:
            return None

        facts = profile.learned_facts or []
        for fact in facts:
            if fact.get("id") == fact_id:
                fact["verified"] = verified
                break

        profile.learned_facts = facts
        self.db.commit()
        self.db.refresh(profile)
        return profile

    def delete_fact(self, fact_id: str) -> bool:
        """Delete a learned fact."""
        profile = self.get_profile()
        if not profile:
            return False

        facts = profile.learned_facts or []
        original_len = len(facts)
        facts = [f for f in facts if f.get("id") != fact_id]

        if len(facts) == original_len:
            return False

        profile.learned_facts = facts
        self.db.commit()
        return True

    async def extract_facts_from_messages(
        self,
        messages: list[dict[str, str]],
        session_id: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """Extract user facts from conversation messages using LLM."""

        if not messages:
            return []

        # Include FULL conversation - both user messages AND assistant responses
        # Assistant responses may contain extracted/summarized info from files the user shared
        conversation_text = "\n".join(
            [f"{m.get('role', 'user').title()}: {m.get('content', '')}" for m in messages]
        )

        prompt = [
            {
                "role": "system",
                "content": """Analyze this conversation and extract ALL facts about the USER themselves.

The user may have:
- Shared their resume, CV, or professional profile
- Mentioned their work history, experience, education
- Discussed their skills, certifications, or expertise
- Talked about their job, role, company, or responsibilities
- Mentioned personal details like name, location, interests

Extract information about:
- Name, contact info
- Current role, title, company, department
- Work history and previous positions
- Education, degrees, certifications
- Technical skills, tools, technologies they know
- Expertise areas and specializations
- Responsibilities and what they do
- Goals, priorities, and career objectives
- Key relationships (colleagues, managers, team members)
- Achievements and accomplishments
- Territory, region, or focus areas
- Working style and preferences

IMPORTANT: Look at BOTH user messages AND assistant responses. If the assistant summarized a resume or document the user shared, extract facts from that summary too.

Return a JSON array of facts. Each fact should have:
- "fact": The specific fact (concise statement)
- "category": One of: "identity", "role", "responsibilities", "expertise", "goals", "relationships", "priorities", "preferences", "education", "skills", "experience", "achievements"
- "confidence": How confident you are (0.0 to 1.0)

Extract ALL relevant facts - be thorough!
If no user facts are found, return an empty array [].

Example output:
[
  {"fact": "Name is John Smith", "category": "identity", "confidence": 0.95},
  {"fact": "Works as Solutions Architect at Cisco", "category": "role", "confidence": 0.95},
  {"fact": "Has 10 years experience in networking", "category": "experience", "confidence": 0.9},
  {"fact": "CCIE certified", "category": "skills", "confidence": 0.95},
  {"fact": "Bachelor's degree in Computer Science from MIT", "category": "education", "confidence": 0.9}
]""",
            },
            {
                "role": "user",
                "content": f"Extract ALL facts about the user from this conversation:\n\n{conversation_text}",
            },
        ]

        try:
            response, usage = await self.openai.chat_with_usage(prompt, model="gpt-4o-mini")

            # Log usage
            log_llm_usage(
                feature="work",
                model=usage.model,
                prompt_tokens=usage.prompt_tokens,
                completion_tokens=usage.completion_tokens,
                function_name="fact_extraction",
                session_id=session_id,
            )

            facts = json.loads(response)
            if not isinstance(facts, list):
                return []

            # Add session tracking
            for fact in facts:
                fact["source_session_id"] = session_id

            return facts
        except Exception as e:
            logger.error("fact_extraction_failed", error=str(e))
            return []

    async def learn_from_messages(
        self,
        messages: list[dict[str, str]],
        session_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """Extract and store facts from conversation messages."""
        extracted = await self.extract_facts_from_messages(messages, session_id)

        added_facts = []
        for fact_data in extracted:
            # Skip low-confidence facts
            if fact_data.get("confidence", 0) < 0.6:
                continue

            # Check for duplicate facts (simple substring match)
            profile = self.get_profile()
            existing_facts = profile.learned_facts if profile else []
            is_duplicate = any(
                fact_data["fact"].lower() in f.get("fact", "").lower()
                or f.get("fact", "").lower() in fact_data["fact"].lower()
                for f in existing_facts
            )

            if not is_duplicate:
                self.add_learned_fact(
                    fact=fact_data["fact"],
                    category=fact_data.get("category", "general"),
                    confidence=fact_data.get("confidence", 0.8),
                    source_session_id=session_id,
                )
                added_facts.append(fact_data)

        return {
            "extracted": len(extracted),
            "added": len(added_facts),
            "facts": added_facts,
        }

    def build_profile_context(self) -> str:
        """Build profile context for injection into system prompt."""
        profile = self.get_profile()
        if not profile:
            return ""

        parts = ["## About You (Learned from our conversations)\n"]

        # Identity
        identity_parts = []
        if profile.name:
            identity_parts.append(profile.name)
        if profile.role:
            identity_parts.append(profile.role)
        if profile.company:
            identity_parts.append(f"at {profile.company}")
        if identity_parts:
            parts.append(f"**Identity:** {', '.join(identity_parts)}")

        if profile.department:
            parts.append(f"**Department:** {profile.department}")

        # Responsibilities
        if profile.responsibilities:
            parts.append("\n**Your Responsibilities:**")
            for r in profile.responsibilities[:5]:
                parts.append(f"- {r}")

        # Expertise
        if profile.expertise_areas:
            areas = ", ".join(profile.expertise_areas[:8])
            parts.append(f"\n**Your Expertise:** {areas}")

        # Current priorities
        if profile.current_priorities:
            parts.append("\n**Current Priorities:**")
            for i, p in enumerate(profile.current_priorities[:5], 1):
                parts.append(f"{i}. {p}")

        # Working style
        if profile.working_style:
            parts.append(f"\n**Working Style:** {profile.working_style}")

        # Key relationships
        if profile.key_relationships:
            parts.append("\n**Key Relationships:**")
            for rel in profile.key_relationships[:5]:
                name = rel.get("name", "")
                role = rel.get("role", "")
                parts.append(f"- {name}" + (f" ({role})" if role else ""))

        # Only include if we have meaningful content
        if len(parts) <= 1:
            return ""

        parts.append("\nUse this context to provide personalized assistance.")
        return "\n".join(parts)
