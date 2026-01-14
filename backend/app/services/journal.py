import json
import math
import uuid as uuid_module
from datetime import date, datetime, timedelta
from typing import Any, Optional
from uuid import UUID

import psycopg2
import tiktoken
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.logging import get_logger
from app.models import (
    ChatMessage,
    ChatSession,
    JournalChatSummary,
    JournalEntry,
    JournalFactExtraction,
    JournalUserProfile,
)
from app.services.llm_usage import log_llm_usage
from app.services.openai_service import OpenAIService

logger = get_logger(__name__)


def cosine_similarity(vec1: list[float], vec2: list[float]) -> float:
    """Calculate cosine similarity between two vectors."""
    dot_product = sum(a * b for a, b in zip(vec1, vec2, strict=False))
    magnitude1 = math.sqrt(sum(a * a for a in vec1))
    magnitude2 = math.sqrt(sum(b * b for b in vec2))
    if magnitude1 == 0 or magnitude2 == 0:
        return 0.0
    return dot_product / (magnitude1 * magnitude2)


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
            embedding, usage = await self.openai.generate_embedding_with_usage(text_to_embed)

            # Log usage
            log_llm_usage(
                feature="journal",
                model=usage.model,
                prompt_tokens=usage.prompt_tokens,
                completion_tokens=usage.completion_tokens,
                function_name="entry_embedding",
            )

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
            query_embedding, usage = await self.openai.generate_embedding_with_usage(query)

            # Log usage
            log_llm_usage(
                feature="journal",
                model=usage.model,
                prompt_tokens=usage.prompt_tokens,
                completion_tokens=usage.completion_tokens,
                function_name="semantic_search",
            )

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
            response, usage = await self.openai.chat_with_usage(summary_prompt)

            # Log usage
            log_llm_usage(
                feature="journal",
                model=usage.model,
                prompt_tokens=usage.prompt_tokens,
                completion_tokens=usage.completion_tokens,
                function_name="generate_summary",
                session_id=session_id,
            )

            data = json.loads(response)

            # Create summary record
            summary = JournalChatSummary(
                chat_session_id=session.id,
                summary_text=data.get("summary", ""),
                key_topics=data.get("key_topics", []),
                sentiment=data.get("sentiment", "neutral"),
                model_used=usage.model,
                tokens_used=usage.total_tokens,
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

    # =========================================================================
    # User Profile Management
    # =========================================================================

    def get_profile(self) -> Optional[JournalUserProfile]:
        """Get the user's journal profile (singleton)."""
        return self.db.query(JournalUserProfile).first()

    def get_or_create_profile(self) -> JournalUserProfile:
        """Get existing profile or create a new empty one."""
        profile = self.get_profile()
        if not profile:
            profile = JournalUserProfile(
                learned_facts=[],
                life_context={},
                interests=[],
                goals=[],
                challenges=[],
                values=[],
            )
            self.db.add(profile)
            self.db.commit()
            self.db.refresh(profile)
        return profile

    def update_profile(
        self,
        name: Optional[str] = None,
        nickname: Optional[str] = None,
        life_context: Optional[dict] = None,
        interests: Optional[list[str]] = None,
        goals: Optional[list[str]] = None,
        challenges: Optional[list[str]] = None,
        values: Optional[list[str]] = None,
        communication_style: Optional[str] = None,
    ) -> JournalUserProfile:
        """Update profile fields."""
        profile = self.get_or_create_profile()

        if name is not None:
            profile.name = name
        if nickname is not None:
            profile.nickname = nickname
        if life_context is not None:
            profile.life_context = life_context
        if interests is not None:
            profile.interests = interests
        if goals is not None:
            profile.goals = goals
        if challenges is not None:
            profile.challenges = challenges
        if values is not None:
            profile.values = values
        if communication_style is not None:
            profile.communication_style = communication_style

        profile.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(profile)
        return profile

    def add_learned_fact(
        self,
        fact: str,
        category: str,
        confidence: float = 0.8,
        source_session_id: Optional[str] = None,
    ) -> JournalUserProfile:
        """Add a new learned fact to the profile."""
        profile = self.get_or_create_profile()
        facts = profile.learned_facts or []

        new_fact = {
            "id": str(uuid_module.uuid4()),
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

    def verify_fact(self, fact_id: str, verified: bool = True) -> Optional[JournalUserProfile]:
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

    # =========================================================================
    # Learning from Conversations
    # =========================================================================

    async def extract_facts_from_messages(
        self,
        messages: list[dict[str, str]],
        session_id: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """Extract user facts from conversation messages using LLM."""
        if not messages:
            return []

        # Include FULL conversation - both user messages AND assistant responses
        conversation_text = "\n".join(
            [f"{m.get('role', 'user').title()}: {m.get('content', '')}" for m in messages]
        )

        prompt = [
            {
                "role": "system",
                "content": """You are a personal fact extractor. Extract EVERY fact about the user from this conversation.

## EXTRACTION RULES - BE AGGRESSIVE

1. **Extract EVERYTHING mentioned** - If the user mentions ANY of the following, extract it:
   - Names of people (family, friends, coworkers, anyone)
   - Relationships (brother, sister, wife, husband, child, parent, friend, pet)
   - Sports teams they follow or play for
   - Favorite foods, restaurants, activities
   - Where they live, work, or have lived
   - Their job, role, or profession
   - Hobbies, interests, games they play
   - Health conditions, feelings, emotional states
   - Opinions, preferences, likes, dislikes
   - Goals, dreams, aspirations
   - Daily routines, schedules
   - Important dates, events, milestones

2. **Confidence scoring** - Use these guidelines:
   - 0.9-1.0: Explicitly stated facts ("My brother John...", "I live in...")
   - 0.7-0.9: Clearly implied facts ("We went to John's game" implies John plays sports)
   - 0.5-0.7: Reasonable inferences ("I was exhausted" suggests possible sleep/health issue)
   - 0.4-0.5: Weak inferences (only use for very uncertain deductions)

3. **Be specific** - Include names, details, specifics when mentioned:
   - BAD: "Has a brother"
   - GOOD: "Has a brother named John who plays baseball"

## CATEGORIES
- identity: name, age, location, job, physical traits
- relationships: family, friends, pets, coworkers (INCLUDE NAMES)
- interests: hobbies, sports teams, games, entertainment, food preferences
- goals: aspirations, things they want to achieve
- challenges: struggles, health issues, obstacles, stressors
- values: beliefs, principles, priorities
- life_events: milestones, significant happenings, daily events

## OUTPUT FORMAT
Return a JSON array. Each fact:
- "fact": Specific fact with details (include names!)
- "category": One of the categories above
- "confidence": 0.4 to 1.0

## EXAMPLES
[
  {"fact": "Has a brother named John who plays baseball", "category": "relationships", "confidence": 0.95},
  {"fact": "Follows the Chicago Cubs", "category": "interests", "confidence": 0.9},
  {"fact": "Wife's name is Sarah", "category": "relationships", "confidence": 0.95},
  {"fact": "Works as a software engineer", "category": "identity", "confidence": 0.9},
  {"fact": "Enjoys playing video games, especially RPGs", "category": "interests", "confidence": 0.85},
  {"fact": "Feeling stressed about work deadlines", "category": "challenges", "confidence": 0.8},
  {"fact": "Lives in the Chicago area", "category": "identity", "confidence": 0.85},
  {"fact": "Has a dog named Buddy", "category": "relationships", "confidence": 0.95},
  {"fact": "Trying to exercise more regularly", "category": "goals", "confidence": 0.8}
]

IMPORTANT: Extract MORE facts rather than fewer. It's better to capture something that might be filtered later than to miss important information. Return [] only if truly no personal information is present.""",
            },
            {
                "role": "user",
                "content": f"Extract ALL personal facts about the user from this journal conversation. Be thorough - extract every name, relationship, interest, and detail mentioned:\n\n{conversation_text}",
            },
        ]

        try:
            response, usage = await self.openai.chat_with_usage(prompt, model="gpt-4o-mini")

            # Log usage
            log_llm_usage(
                feature="journal",
                model=usage.model,
                prompt_tokens=usage.prompt_tokens,
                completion_tokens=usage.completion_tokens,
                function_name="extract_facts",
                session_id=session_id,
            )

            logger.info(
                "fact_extraction_llm_response",
                session_id=session_id,
                response_length=len(response) if response else 0,
                response_preview=response[:200] if response else "empty",
            )
            # Handle potential markdown code blocks in response
            response_text = response.strip()
            if response_text.startswith("```"):
                # Remove markdown code block
                lines = response_text.split("\n")
                response_text = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])

            facts = json.loads(response_text)
            if not isinstance(facts, list):
                logger.warning("fact_extraction_not_list", response_type=type(facts).__name__)
                return []

            logger.info(
                "facts_extracted",
                session_id=session_id,
                count=len(facts),
                facts_preview=[f.get("fact", "")[:50] for f in facts[:3]] if facts else [],
            )

            # Add session tracking
            for fact in facts:
                fact["source_session_id"] = session_id

            return facts
        except Exception as e:
            logger.error("fact_extraction_failed", error=str(e), session_id=session_id)
            return []

    async def learn_from_messages(
        self,
        messages: list[dict[str, str]],
        session_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """Extract and store facts from conversation messages."""
        extracted = await self.extract_facts_from_messages(messages, session_id)

        added_facts = []
        filtered_facts = []
        profile = self.get_profile()
        existing_facts = profile.learned_facts if profile else []

        for fact_data in extracted:
            fact_text = fact_data.get("fact", "")
            confidence = fact_data.get("confidence", 0)
            category = fact_data.get("category", "general")

            # Skip low-confidence facts (threshold lowered to 0.4)
            if confidence < 0.4:
                self._record_extraction(
                    session_id,
                    fact_text,
                    category,
                    confidence,
                    status="low_confidence",
                    duplicate_of=None,
                )
                filtered_facts.append(
                    {"fact": fact_text, "reason": "low_confidence", "confidence": confidence}
                )
                continue

            # Check for semantic duplicates using embeddings
            is_dup, dup_match = await self._is_semantic_duplicate(fact_text, existing_facts)

            if is_dup:
                self._record_extraction(
                    session_id,
                    fact_text,
                    category,
                    confidence,
                    status="duplicate",
                    duplicate_of=dup_match,
                )
                filtered_facts.append(
                    {"fact": fact_text, "reason": "duplicate", "matched": dup_match}
                )
                continue

            # Add the fact
            self.add_learned_fact(
                fact=fact_text,
                category=category,
                confidence=confidence,
                source_session_id=session_id,
            )
            self._record_extraction(
                session_id, fact_text, category, confidence, status="added", duplicate_of=None
            )
            added_facts.append(fact_data)

            # Update existing_facts for subsequent duplicate checks in this batch
            existing_facts = self.get_profile().learned_facts if self.get_profile() else []

        logger.info(
            "learning_complete",
            session_id=session_id,
            extracted=len(extracted),
            added=len(added_facts),
            filtered=len(filtered_facts),
        )

        return {
            "extracted": len(extracted),
            "added": len(added_facts),
            "filtered": len(filtered_facts),
            "facts": added_facts,
            "filtered_details": filtered_facts,
        }

    async def _is_semantic_duplicate(
        self,
        new_fact: str,
        existing_facts: list[dict],
        similarity_threshold: float = 0.85,
    ) -> tuple[bool, Optional[str]]:
        """Check if a fact is semantically similar to existing facts using embeddings."""
        if not existing_facts:
            return False, None

        try:
            # Get embedding for the new fact
            new_embedding, usage = await self.openai.generate_embedding_with_usage(new_fact)

            # Log usage
            log_llm_usage(
                feature="journal",
                model=usage.model,
                prompt_tokens=usage.prompt_tokens,
                completion_tokens=usage.completion_tokens,
                function_name="fact_dedup_embedding",
            )

            # Compare against existing facts
            for existing in existing_facts:
                existing_text = existing.get("fact", "")
                existing_embedding = existing.get("embedding")

                # Generate embedding if not cached
                if not existing_embedding:
                    existing_embedding, emb_usage = await self.openai.generate_embedding_with_usage(
                        existing_text
                    )

                    # Log usage
                    log_llm_usage(
                        feature="journal",
                        model=emb_usage.model,
                        prompt_tokens=emb_usage.prompt_tokens,
                        completion_tokens=emb_usage.completion_tokens,
                        function_name="fact_dedup_embedding",
                    )

                similarity = cosine_similarity(new_embedding, existing_embedding)
                if similarity >= similarity_threshold:
                    logger.debug(
                        "semantic_duplicate_found",
                        new_fact=new_fact[:50],
                        matched=existing_text[:50],
                        similarity=round(similarity, 3),
                    )
                    return True, existing_text

            return False, None

        except Exception as e:
            logger.warning("semantic_duplicate_check_failed", error=str(e))
            # Fall back to simple substring matching
            for existing in existing_facts:
                existing_text = existing.get("fact", "").lower()
                if new_fact.lower() in existing_text or existing_text in new_fact.lower():
                    return True, existing.get("fact")
            return False, None

    def _record_extraction(
        self,
        session_id: Optional[str],
        fact_text: str,
        category: str,
        confidence: float,
        status: str,
        duplicate_of: Optional[str],
    ) -> None:
        """Record a fact extraction for visibility/debugging."""
        try:
            extraction = JournalFactExtraction(
                session_id=session_id,
                fact_text=fact_text,
                category=category,
                confidence=confidence,
                status=status,
                duplicate_of=duplicate_of,
            )
            self.db.add(extraction)
            self.db.commit()
        except Exception as e:
            logger.warning("record_extraction_failed", error=str(e))
            self.db.rollback()

    # =========================================================================
    # Profile Context Building for Chat Injection
    # =========================================================================

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
        if profile.nickname:
            identity_parts.append(f'(goes by "{profile.nickname}")')
        if identity_parts:
            parts.append(f"**Name:** {' '.join(identity_parts)}")

        # Life context
        if profile.life_context:
            ctx = profile.life_context
            if ctx.get("relationships"):
                parts.append("\n**Key People:**")
                for rel in ctx["relationships"][:5]:
                    if isinstance(rel, dict):
                        name = rel.get("name", "")
                        relation = rel.get("relation", "")
                        parts.append(f"- {name}" + (f" ({relation})" if relation else ""))
                    else:
                        parts.append(f"- {rel}")
            if ctx.get("pets"):
                parts.append(f"\n**Pets:** {', '.join(ctx['pets'][:5])}")
            if ctx.get("living_situation"):
                parts.append(f"\n**Living Situation:** {ctx['living_situation']}")

        # Interests
        if profile.interests:
            interests_str = ", ".join(profile.interests[:8])
            parts.append(f"\n**Interests:** {interests_str}")

        # Goals
        if profile.goals:
            parts.append("\n**Personal Goals:**")
            for i, goal in enumerate(profile.goals[:5], 1):
                parts.append(f"{i}. {goal}")

        # Challenges
        if profile.challenges:
            parts.append("\n**Current Challenges:**")
            for challenge in profile.challenges[:3]:
                parts.append(f"- {challenge}")

        # Values
        if profile.values:
            values_str = ", ".join(profile.values[:6])
            parts.append(f"\n**Values:** {values_str}")

        # Communication style
        if profile.communication_style:
            parts.append(f"\n**Communication Style:** {profile.communication_style}")

        # Include some learned facts
        if profile.learned_facts:
            verified_facts = [f for f in profile.learned_facts if f.get("verified")]
            high_confidence = [f for f in profile.learned_facts if f.get("confidence", 0) >= 0.85]
            facts_to_show = verified_facts[:3] or high_confidence[:3]
            if facts_to_show:
                parts.append("\n**Things I Remember:**")
                for fact in facts_to_show:
                    parts.append(f"- {fact.get('fact', '')}")

        # Only include if we have meaningful content
        if len(parts) <= 1:
            return ""

        parts.append("\nUse this context to provide personalized, empathetic support.")
        return "\n".join(parts)

    # =========================================================================
    # Auto-Summarization Helpers
    # =========================================================================

    def should_summarize_session(self, session_id: str) -> bool:
        """Check if a session has enough content to warrant summarization."""
        session = self.db.query(ChatSession).filter_by(session_id=session_id).first()
        if not session:
            return False

        # Check if already summarized
        existing = self.db.query(JournalChatSummary).filter_by(chat_session_id=session.id).first()
        if existing:
            return False

        # Get user messages
        messages = (
            self.db.query(ChatMessage)
            .filter_by(session_id=session.id)
            .filter(ChatMessage.role == "user")
            .all()
        )

        # Minimum thresholds: 3+ user messages, 100+ words total
        if len(messages) < 3:
            return False

        total_words = sum(len(msg.content.split()) for msg in messages)
        return total_words >= 100

    async def auto_summarize_and_approve(self, session_id: str) -> Optional[JournalEntry]:
        """Generate a summary and automatically create a journal entry."""
        if not self.should_summarize_session(session_id):
            return None

        # Generate summary
        summary = await self.generate_chat_summary(session_id)
        if not summary:
            return None

        # Auto-approve it
        entry = await self.approve_summary(
            summary_id=summary.summary_id,
            title=f"Journal - {summary.created_at.strftime('%B %d, %Y')}",
            mood=summary.sentiment
            if summary.sentiment in ["positive", "negative", "neutral"]
            else None,
            tags=summary.key_topics,
        )

        logger.info(
            "auto_summarized_session",
            session_id=session_id,
            entry_id=str(entry.entry_id) if entry else None,
        )
        return entry
