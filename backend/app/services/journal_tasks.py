"""Background tasks for journal auto-summarization and learning."""

import asyncio
from datetime import datetime, timedelta
from typing import Any, Optional

from app.core.logging import get_logger
from app.database import SessionLocal
from app.models import ChatMessage, ChatSession, JournalChatSummary

logger = get_logger(__name__)


class JournalBackgroundProcessor:
    """Background processor for journal learning and auto-summarization.

    Handles:
    - Extracting facts from journal chat sessions
    - Auto-summarizing completed sessions
    - Retroactive processing of existing sessions
    """

    def __init__(self, check_interval: int = 300):
        """Initialize processor.

        Args:
            check_interval: Seconds between checks (default: 300 = 5 minutes).
        """
        self._check_interval = check_interval
        self._running = False
        self._processing_lock = asyncio.Lock()
        self._last_processed_session: Optional[str] = None

    async def start(self):
        """Start the background processing loop."""
        if self._running:
            return

        self._running = True
        logger.info("journal_processor_started", interval=self._check_interval)
        asyncio.create_task(self._processing_loop())

    async def stop(self):
        """Stop the background processing loop."""
        self._running = False
        logger.info("journal_processor_stopped")

    async def _processing_loop(self):
        """Main processing loop."""
        while self._running:
            try:
                await self._check_for_sessions_to_process()
            except Exception as e:
                logger.error("journal_processing_loop_error", error=str(e))

            await asyncio.sleep(self._check_interval)

    async def _check_for_sessions_to_process(self):
        """Check for journal sessions that need processing."""
        async with self._processing_lock:
            db = SessionLocal()
            try:
                # Find journal sessions updated in the last hour that haven't been summarized
                cutoff = datetime.utcnow() - timedelta(hours=1)
                sessions = (
                    db.query(ChatSession)
                    .filter(ChatSession.context == "journal")
                    .filter(ChatSession.updated_at >= cutoff)
                    .all()
                )

                for session in sessions:
                    await self._process_session(session.session_id, db)

            finally:
                db.close()

    async def _process_session(self, session_id: str, db) -> dict[str, Any]:
        """Process a single session for learning and summarization."""
        from app.services.journal import JournalService

        journal_service = JournalService(db)
        result = {
            "session_id": session_id,
            "facts_learned": 0,
            "entry_created": False,
        }

        try:
            # Get messages from session
            session = db.query(ChatSession).filter_by(session_id=session_id).first()
            if not session:
                logger.warning("session_not_found", session_id=session_id)
                return result

            messages = (
                db.query(ChatMessage)
                .filter_by(session_id=session.id)
                .order_by(ChatMessage.created_at)
                .all()
            )

            if not messages:
                logger.warning("session_has_no_messages", session_id=session_id)
                return result

            # Convert to dict format for learning
            message_dicts = [
                {"role": msg.role, "content": msg.content}
                for msg in messages
                if msg.role in ["user", "assistant"]
            ]

            logger.info(
                "processing_session_messages",
                session_id=session_id,
                total_messages=len(messages),
                filtered_messages=len(message_dicts),
                sample_content=message_dicts[0]["content"][:100] if message_dicts else "empty",
            )

            if not message_dicts:
                logger.warning("session_has_no_user_assistant_messages", session_id=session_id)
                return result

            # Learn from messages
            learning_result = await journal_service.learn_from_messages(message_dicts, session_id)
            result["facts_learned"] = learning_result.get("added", 0)

            logger.info(
                "session_learning_result",
                session_id=session_id,
                extracted=learning_result.get("extracted", 0),
                added=learning_result.get("added", 0),
            )

            # Auto-summarize if ready
            entry = await journal_service.auto_summarize_and_approve(session_id)
            if entry:
                result["entry_created"] = True
                result["entry_id"] = str(entry.entry_id)

            logger.info(
                "session_processed",
                session_id=session_id,
                facts_learned=result["facts_learned"],
                entry_created=result["entry_created"],
            )

        except Exception as e:
            logger.error("session_processing_failed", session_id=session_id, error=str(e))
            result["error"] = str(e)

        return result

    async def process_retroactive(self, limit: int = 100) -> dict[str, Any]:
        """Process all existing journal sessions retroactively.

        Args:
            limit: Maximum number of sessions to process.

        Returns:
            Summary of processing results.
        """
        async with self._processing_lock:
            db = SessionLocal()
            try:
                # Get all journal sessions without summaries
                processed_session_ids = (
                    db.query(JournalChatSummary.chat_session_id)
                    .filter(JournalChatSummary.chat_session_id.isnot(None))
                    .distinct()
                    .all()
                )
                processed_ids = {r[0] for r in processed_session_ids}

                sessions = (
                    db.query(ChatSession)
                    .filter(ChatSession.context == "journal")
                    .order_by(ChatSession.created_at.desc())
                    .limit(limit)
                    .all()
                )

                # Filter to unprocessed sessions
                unprocessed = [s for s in sessions if s.id not in processed_ids]

                logger.info(
                    "retroactive_processing_starting",
                    total_journal_sessions=len(sessions),
                    already_processed=len(processed_ids),
                    to_process=len(unprocessed),
                    session_ids=[s.session_id for s in unprocessed[:5]],  # First 5 for debugging
                )

                results = {
                    "total_sessions": len(sessions),
                    "unprocessed_sessions": len(unprocessed),
                    "processed": 0,
                    "entries_created": 0,
                    "facts_learned": 0,
                    "errors": 0,
                    "details": [],
                }

                for session in unprocessed:
                    try:
                        session_result = await self._process_session(session.session_id, db)
                        results["processed"] += 1
                        results["facts_learned"] += session_result.get("facts_learned", 0)
                        if session_result.get("entry_created"):
                            results["entries_created"] += 1
                        results["details"].append(session_result)
                    except Exception as e:
                        logger.error(
                            "retroactive_session_failed",
                            session_id=session.session_id,
                            error=str(e),
                        )
                        results["errors"] += 1

                logger.info(
                    "retroactive_processing_complete",
                    processed=results["processed"],
                    entries_created=results["entries_created"],
                    facts_learned=results["facts_learned"],
                )

                return results

            finally:
                db.close()


# Singleton instance
journal_processor = JournalBackgroundProcessor()


async def start_journal_tasks():
    """Start journal background tasks."""
    await journal_processor.start()


async def stop_journal_tasks():
    """Stop journal background tasks."""
    await journal_processor.stop()


async def process_session_now(session_id: str) -> dict[str, Any]:
    """Process a specific session immediately (for post-chat hook)."""
    db = SessionLocal()
    try:
        from app.services.journal import JournalService

        journal_service = JournalService(db)

        # Get messages
        session = db.query(ChatSession).filter_by(session_id=session_id).first()
        if not session:
            return {"error": "Session not found"}

        messages = (
            db.query(ChatMessage)
            .filter_by(session_id=session.id)
            .order_by(ChatMessage.created_at)
            .all()
        )

        if not messages:
            return {"error": "No messages in session"}

        # Convert to dict format
        message_dicts = [
            {"role": msg.role, "content": msg.content}
            for msg in messages
            if msg.role in ["user", "assistant"]
        ]

        # Learn from messages (fire-and-forget learning)
        learning_result = await journal_service.learn_from_messages(message_dicts, session_id)

        return {
            "session_id": session_id,
            "facts_extracted": learning_result.get("extracted", 0),
            "facts_added": learning_result.get("added", 0),
        }

    except Exception as e:
        logger.error("immediate_processing_failed", session_id=session_id, error=str(e))
        return {"error": str(e)}
    finally:
        db.close()
