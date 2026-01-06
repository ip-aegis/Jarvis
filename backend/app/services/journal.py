import json
from datetime import date, datetime, timedelta
from typing import Any, Optional
from uuid import UUID

import psycopg2
import tiktoken
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.logging import get_logger
from app.models import ChatMessage, ChatSession, JournalChatSummary, JournalEntry
from app.services.openai_service import OpenAIService

logger = get_logger(__name__)


class JournalService:
    """Service for managing journal entries with RAG capabilities."""

    def __init__(self, db: Session):
        self.db = db
        self.openai = OpenAIService()
        self.tokenizer = tiktoken.encoding_for_model("gpt-4")
        self.max_context_tokens = 4000  # Token budget for context

    # =========================================================================
    # CRUD Operations
    # =========================================================================

    async def create_entry(
        self,
        content: str,
        entry_date: Optional[date] = None,
        title: Optional[str] = None,
        mood: Optional[str] = None,
        energy_level: Optional[int] = None,
        tags: Optional[list[str]] = None,
        source: str = "manual",
        source_session_id: Optional[str] = None,
    ) -> JournalEntry:
        """Create a new journal entry and generate its embedding."""
        entry = JournalEntry(
            date=entry_date or date.today(),
            title=title,
            content=content,
            mood=mood,
            energy_level=energy_level,
            tags=tags or [],
            source=source,
            source_session_id=source_session_id,
        )
        self.db.add(entry)
        self.db.commit()
        self.db.refresh(entry)

        # Generate and store embedding
        await self._update_embedding(entry)

        return entry

    async def update_entry(
        self,
        entry_id: UUID,
        content: Optional[str] = None,
        title: Optional[str] = None,
        mood: Optional[str] = None,
        energy_level: Optional[int] = None,
        tags: Optional[list[str]] = None,
        entry_date: Optional[date] = None,
    ) -> Optional[JournalEntry]:
        """Update an existing journal entry."""
        entry = self.db.query(JournalEntry).filter_by(entry_id=entry_id).first()
        if not entry:
            return None

        content_changed = False
        if content is not None and content != entry.content:
            entry.content = content
            content_changed = True
        if title is not None:
            entry.title = title
        if mood is not None:
            entry.mood = mood
        if energy_level is not None:
            entry.energy_level = energy_level
        if tags is not None:
            entry.tags = tags
        if entry_date is not None:
            entry.date = entry_date

        entry.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(entry)

        # Re-generate embedding if content changed
        if content_changed:
            await self._update_embedding(entry)

        return entry

    def delete_entry(self, entry_id: UUID) -> bool:
        """Delete a journal entry."""
        entry = self.db.query(JournalEntry).filter_by(entry_id=entry_id).first()
        if not entry:
            return False

        self.db.delete(entry)
        self.db.commit()
        return True

    def get_entry(self, entry_id: UUID) -> Optional[JournalEntry]:
        """Get a single journal entry by ID."""
        return self.db.query(JournalEntry).filter_by(entry_id=entry_id).first()

    def get_entries(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        mood: Optional[str] = None,
        tags: Optional[list[str]] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[JournalEntry]:
        """Get journal entries with optional filters."""
        query = self.db.query(JournalEntry)

        if start_date:
            query = query.filter(JournalEntry.date >= start_date)
        if end_date:
            query = query.filter(JournalEntry.date <= end_date)
        if mood:
            query = query.filter(JournalEntry.mood == mood)
        if tags:
            # Filter entries that have any of the specified tags
            for tag in tags:
                query = query.filter(JournalEntry.tags.contains([tag]))

        return query.order_by(JournalEntry.date.desc()).offset(offset).limit(limit).all()

    def get_recent_entries(self, days: int = 7) -> list[JournalEntry]:
        """Get entries from the last N days."""
        start_date = date.today() - timedelta(days=days)
        return self.get_entries(start_date=start_date)

    def get_calendar_data(self, year: int, month: int) -> dict[str, Any]:
        """Get calendar data for a specific month."""
        # Get first and last day of month
        first_day = date(year, month, 1)
        if month == 12:
            last_day = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            last_day = date(year, month + 1, 1) - timedelta(days=1)

        entries = self.get_entries(start_date=first_day, end_date=last_day, limit=100)

        # Build calendar map
        calendar = {}
        for entry in entries:
            day_str = (
                entry.date.isoformat()
                if isinstance(entry.date, date)
                else entry.date.date().isoformat()
            )
            if day_str not in calendar:
                calendar[day_str] = []
            calendar[day_str].append(
                {
                    "entry_id": str(entry.entry_id),
                    "title": entry.title,
                    "mood": entry.mood,
                    "source": entry.source,
                }
            )

        return {
            "year": year,
            "month": month,
            "entries": calendar,
        }

    # =========================================================================
    # Embedding & RAG Operations
    # =========================================================================

    async def _update_embedding(self, entry: JournalEntry) -> None:
        """Generate and store embedding for a journal entry."""
        try:
            # Create text for embedding (title + content)
            text_to_embed = f"{entry.title or ''}\n{entry.content}".strip()
            embedding = await self.openai.generate_embedding(text_to_embed)

            # Store embedding using raw SQL (pgvector)
            self.db.execute(
                text("UPDATE journal_entries SET embedding = :embedding WHERE id = :id"),
                {"embedding": str(embedding), "id": entry.id},
            )
            self.db.commit()

            logger.info("embedding_updated", entry_id=str(entry.entry_id))
        except Exception as e:
            logger.error("embedding_update_failed", entry_id=str(entry.entry_id), error=str(e))

    async def semantic_search(
        self,
        query: str,
        limit: int = 5,
        min_similarity: float = 0.1,
    ) -> list[tuple[JournalEntry, float]]:
        """Search journal entries using semantic similarity."""
        try:
            # Generate embedding for query
            query_embedding = await self.openai.generate_embedding(query)
            embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

            # Perform cosine similarity search using pgvector
            # Note: Using direct psycopg2 and subquery approach for compatibility
            # Direct ORDER BY with pgvector operators has issues
            settings = get_settings()
            conn = psycopg2.connect(settings.database_url)
            cur = conn.cursor()
            sql = f"""
                SELECT id, similarity
                FROM (
                    SELECT id, 1 - (embedding <=> '{embedding_str}'::vector) as similarity
                    FROM journal_entries
                    WHERE embedding IS NOT NULL
                ) subq
                WHERE similarity >= {min_similarity}
                ORDER BY similarity DESC
                LIMIT {limit}
            """
            cur.execute(sql)
            rows = cur.fetchall()
            cur.close()
            conn.close()

            entries_with_scores = []
            for row in rows:
                entry_id, similarity = row
                entry = self.db.query(JournalEntry).filter_by(id=entry_id).first()
                if entry:
                    entries_with_scores.append((entry, similarity))

            return entries_with_scores
        except Exception as e:
            logger.error("semantic_search_failed", error=str(e))
            return []

    # =========================================================================
    # Context Building for LLM
    # =========================================================================

    def _count_tokens(self, text: str) -> int:
        """Count tokens in text."""
        return len(self.tokenizer.encode(text))

    async def build_journal_context(
        self,
        query: Optional[str] = None,
        include_recent_days: int = 7,
        max_rag_results: int = 5,
    ) -> str:
        """Build context for LLM from recent entries and RAG results."""
        context_parts = []
        remaining_tokens = self.max_context_tokens

        # Add recent entries
        recent_entries = self.get_recent_entries(days=include_recent_days)
        if recent_entries:
            recent_section = "## Recent Journal Entries (Last 7 Days)\n\n"
            for entry in recent_entries[:5]:  # Limit to 5 recent
                entry_text = self._format_entry_for_context(entry)
                tokens = self._count_tokens(entry_text)
                if tokens < remaining_tokens:
                    recent_section += entry_text + "\n---\n"
                    remaining_tokens -= tokens

            context_parts.append(recent_section)

        # Add RAG results if query provided
        if query and remaining_tokens > 500:
            rag_results = await self.semantic_search(query, limit=max_rag_results)
            if rag_results:
                rag_section = "## Relevant Historical Entries\n\n"
                for entry, score in rag_results:
                    # Skip if already in recent
                    if any(r.id == entry.id for r in recent_entries):
                        continue
                    entry_text = self._format_entry_for_context(entry)
                    tokens = self._count_tokens(entry_text)
                    if tokens < remaining_tokens:
                        rag_section += f"(Relevance: {score:.2f})\n{entry_text}\n---\n"
                        remaining_tokens -= tokens

                context_parts.append(rag_section)

        return "\n".join(context_parts)

    def _format_entry_for_context(self, entry: JournalEntry) -> str:
        """Format a journal entry for inclusion in LLM context."""
        date_str = (
            entry.date.isoformat()
            if isinstance(entry.date, date)
            else entry.date.date().isoformat()
        )
        parts = [f"**{date_str}**"]
        if entry.title:
            parts.append(f" - {entry.title}")
        parts.append(f"\n{entry.content[:500]}...")  # Truncate long content
        if entry.mood:
            parts.append(f"\nMood: {entry.mood}")
        if entry.tags:
            parts.append(f"\nTags: {', '.join(entry.tags)}")
        return "".join(parts)

    # =========================================================================
    # Chat Summary Operations
    # =========================================================================

    async def generate_chat_summary(
        self,
        session_id: str,
    ) -> Optional[JournalChatSummary]:
        """Generate a journal summary from a chat session."""
        # Get the chat session
        session = self.db.query(ChatSession).filter_by(session_id=session_id).first()
        if not session:
            logger.warning("session_not_found", session_id=session_id)
            return None

        # Get messages from session
        messages = (
            self.db.query(ChatMessage)
            .filter_by(session_id=session.id)
            .order_by(ChatMessage.created_at)
            .all()
        )
        if not messages:
            logger.warning("no_messages_in_session", session_id=session_id)
            return None

        # Build conversation text
        conversation = "\n".join(
            [
                f"{msg.role.upper()}: {msg.content}"
                for msg in messages
                if msg.role in ["user", "assistant"]
            ]
        )

        # Generate summary using OpenAI
        summary_prompt = [
            {
                "role": "system",
                "content": """You are a journaling assistant.
Summarize the following conversation into a personal journal entry.
Focus on:
- Key experiences or events discussed
- Emotions and feelings expressed
- Any insights or realizations
- Goals or intentions mentioned

Format as a first-person journal entry that captures the essence of the conversation.
Also extract:
- 3-5 key topics discussed (as a JSON array)
- Overall sentiment: positive, negative, neutral, or mixed

Respond in JSON format:
{
  "summary": "The journal entry text...",
  "key_topics": ["topic1", "topic2"],
  "sentiment": "positive"
}""",
            },
            {"role": "user", "content": f"Summarize this conversation:\n\n{conversation}"},
        ]

        try:
            response = await self.openai.chat(summary_prompt)
            data = json.loads(response)

            # Create summary record
            summary = JournalChatSummary(
                chat_session_id=session.id,
                summary_text=data.get("summary", ""),
                key_topics=data.get("key_topics", []),
                sentiment=data.get("sentiment", "neutral"),
                model_used=self.openai.model,
                tokens_used=self._count_tokens(conversation) + self._count_tokens(response),
                status="generated",
            )
            self.db.add(summary)
            self.db.commit()
            self.db.refresh(summary)

            logger.info(
                "summary_generated", session_id=session_id, summary_id=str(summary.summary_id)
            )
            return summary

        except Exception as e:
            logger.error("summary_generation_failed", session_id=session_id, error=str(e))
            return None

    def get_pending_summaries(self) -> list[JournalChatSummary]:
        """Get all summaries awaiting approval."""
        return (
            self.db.query(JournalChatSummary)
            .filter_by(status="generated")
            .order_by(JournalChatSummary.created_at.desc())
            .all()
        )

    async def approve_summary(
        self,
        summary_id: UUID,
        title: Optional[str] = None,
        mood: Optional[str] = None,
        energy_level: Optional[int] = None,
        tags: Optional[list[str]] = None,
    ) -> Optional[JournalEntry]:
        """Approve a summary and create a journal entry from it."""
        summary = self.db.query(JournalChatSummary).filter_by(summary_id=summary_id).first()
        if not summary or summary.status != "generated":
            return None

        # Create journal entry
        entry = await self.create_entry(
            content=summary.summary_text,
            title=title or f"Chat Summary - {summary.created_at.strftime('%B %d, %Y')}",
            mood=mood
            or (
                summary.sentiment
                if summary.sentiment in ["positive", "negative", "neutral"]
                else None
            ),
            energy_level=energy_level,
            tags=tags or summary.key_topics,
            source="chat_summary",
            source_session_id=str(summary.chat_session_id) if summary.chat_session_id else None,
        )

        # Update summary status
        summary.status = "approved"
        summary.journal_entry_id = entry.id
        self.db.commit()

        return entry

    def reject_summary(self, summary_id: UUID) -> bool:
        """Reject a summary."""
        summary = self.db.query(JournalChatSummary).filter_by(summary_id=summary_id).first()
        if not summary:
            return False

        summary.status = "rejected"
        self.db.commit()
        return True

    # =========================================================================
    # Statistics
    # =========================================================================

    def get_stats(self) -> dict[str, Any]:
        """Get journal statistics."""
        total_entries = self.db.query(JournalEntry).count()

        # Mood distribution
        mood_query = self.db.execute(
            text(
                "SELECT mood, COUNT(*) as count FROM journal_entries WHERE mood IS NOT NULL GROUP BY mood"
            )
        )
        mood_distribution = {row.mood: row.count for row in mood_query}

        # Entries by source
        source_query = self.db.execute(
            text("SELECT source, COUNT(*) as count FROM journal_entries GROUP BY source")
        )
        source_distribution = {row.source: row.count for row in source_query}

        # Streak calculation (consecutive days with entries)
        streak = 0
        check_date = date.today()
        while True:
            has_entry = self.db.query(JournalEntry).filter(JournalEntry.date == check_date).first()
            if has_entry:
                streak += 1
                check_date -= timedelta(days=1)
            else:
                break

        return {
            "total_entries": total_entries,
            "current_streak": streak,
            "mood_distribution": mood_distribution,
            "source_distribution": source_distribution,
            "pending_summaries": self.db.query(JournalChatSummary)
            .filter_by(status="generated")
            .count(),
        }
