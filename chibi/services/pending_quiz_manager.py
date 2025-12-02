"""Thread-safe manager for pending quiz sessions."""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class PendingQuiz:
    """Represents a pending quiz awaiting student response."""

    user_id: int
    db_user_id: int
    channel_id: int
    message_id: int
    module_id: str
    concept_id: str
    concept_name: str
    concept_description: str
    question: str
    correct_answer: Optional[str]
    created_at: datetime


class PendingQuizManager:
    """Thread-safe manager for pending quiz sessions.

    Uses asyncio locks to safely handle concurrent quiz operations.
    """

    def __init__(self, timeout_minutes: int = 30):
        self._pending: Dict[int, PendingQuiz] = {}
        self._lock = asyncio.Lock()
        self._timeout = timedelta(minutes=timeout_minutes)

    async def add(self, quiz: PendingQuiz) -> None:
        """Add a pending quiz for a user.

        If the user already has a pending quiz, it will be replaced.
        """
        async with self._lock:
            self._pending[quiz.user_id] = quiz
            logger.debug(f"Added pending quiz for user {quiz.user_id}")

    async def get(self, user_id: int) -> Optional[PendingQuiz]:
        """Get a pending quiz for a user.

        Returns None if no quiz exists or if it has expired.
        """
        async with self._lock:
            quiz = self._pending.get(user_id)
            if quiz is None:
                return None

            # Check expiration
            if datetime.now() - quiz.created_at > self._timeout:
                del self._pending[user_id]
                logger.debug(f"Quiz expired for user {user_id}")
                return None

            return quiz

    async def remove(self, user_id: int) -> Optional[PendingQuiz]:
        """Remove and return a pending quiz for a user."""
        async with self._lock:
            return self._pending.pop(user_id, None)

    async def has_pending(self, user_id: int) -> bool:
        """Check if a user has a non-expired pending quiz."""
        quiz = await self.get(user_id)
        return quiz is not None

    async def cleanup_expired(self) -> int:
        """Remove all expired quizzes and return count of removed."""
        async with self._lock:
            now = datetime.now()
            expired_users = [
                user_id
                for user_id, quiz in self._pending.items()
                if now - quiz.created_at > self._timeout
            ]
            for user_id in expired_users:
                del self._pending[user_id]

            if expired_users:
                logger.debug(f"Cleaned up {len(expired_users)} expired quizzes")

            return len(expired_users)

    @property
    def count(self) -> int:
        """Return number of pending quizzes (not thread-safe, for debugging only)."""
        return len(self._pending)
