"""LLM Quiz Challenge repository for database operations."""

from datetime import datetime
from typing import Dict, List, Optional

from ..mappers import row_to_llm_quiz_attempt
from ..models import LLMQuizAttempt, ReviewStatus
from .base import BaseRepository


class LLMQuizRepository(BaseRepository):
    """Repository for LLM Quiz Challenge operations."""

    async def log_attempt(
        self,
        user_id: int,
        module_id: str,
        question: str,
        student_answer: str,
        llm_answer: str,
        student_wins: bool,
        student_answer_correctness: str,
        evaluation_explanation: Optional[str] = None,
        review_status: str = ReviewStatus.AUTO_APPROVED,
        discord_user_id: Optional[str] = None,
    ) -> LLMQuizAttempt:
        """Log an LLM quiz challenge attempt."""
        conn = self.connection
        cursor = await conn.execute(
            """INSERT INTO llm_quiz_attempts
               (user_id, module_id, question, student_answer, llm_answer,
                student_wins, student_answer_correctness, evaluation_explanation,
                review_status, discord_user_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                user_id,
                module_id,
                question,
                student_answer,
                llm_answer,
                student_wins,
                student_answer_correctness,
                evaluation_explanation,
                review_status,
                discord_user_id,
            ),
        )
        await conn.commit()

        return LLMQuizAttempt(
            id=cursor.lastrowid,
            user_id=user_id,
            module_id=module_id,
            question=question,
            student_answer=student_answer,
            llm_answer=llm_answer,
            student_wins=student_wins,
            student_answer_correctness=student_answer_correctness,
            evaluation_explanation=evaluation_explanation,
            review_status=review_status,
            discord_user_id=discord_user_id,
            created_at=datetime.now(),
        )

    async def update_review_status(
        self,
        attempt_id: int,
        review_status: str,
        reviewed_by: str,
    ) -> Optional[LLMQuizAttempt]:
        """Update the review status of an attempt."""
        conn = self.connection
        await conn.execute(
            """UPDATE llm_quiz_attempts
               SET review_status = ?, reviewed_at = ?, reviewed_by = ?
               WHERE id = ?""",
            (review_status, datetime.now().isoformat(), reviewed_by, attempt_id),
        )
        await conn.commit()

        # Return the updated attempt
        return await self.get_by_id(attempt_id)

    async def get_by_id(self, attempt_id: int) -> Optional[LLMQuizAttempt]:
        """Get an attempt by ID."""
        conn = self.connection
        cursor = await conn.execute(
            "SELECT * FROM llm_quiz_attempts WHERE id = ?",
            (attempt_id,),
        )
        row = await cursor.fetchone()
        if row:
            return row_to_llm_quiz_attempt(row)
        return None

    async def get_pending_reviews(self, limit: int = 50) -> List[LLMQuizAttempt]:
        """Get all pending review attempts."""
        conn = self.connection
        cursor = await conn.execute(
            """SELECT * FROM llm_quiz_attempts
               WHERE review_status = ?
               ORDER BY created_at ASC
               LIMIT ?""",
            (ReviewStatus.PENDING, limit),
        )
        rows = await cursor.fetchall()
        return [row_to_llm_quiz_attempt(row) for row in rows]

    async def count_wins_for_module(self, user_id: int, module_id: str) -> int:
        """Count successful stumps for a user in a module (only approved ones)."""
        conn = self.connection
        # Only count wins that have been approved (approved, approved_with_bonus, or auto_approved)
        approved_statuses = tuple(ReviewStatus.APPROVED_STATUSES)
        placeholders = ",".join("?" * len(approved_statuses))
        cursor = await conn.execute(
            f"""SELECT COUNT(*) as wins FROM llm_quiz_attempts
               WHERE user_id = ? AND module_id = ? AND student_wins = 1
               AND review_status IN ({placeholders})""",
            (user_id, module_id) + approved_statuses,
        )
        row = await cursor.fetchone()
        return row["wins"] if row else 0

    async def get_progress_by_module(self, user_id: int) -> Dict[str, int]:
        """Get stump count per module for a user (only approved ones)."""
        conn = self.connection
        approved_statuses = tuple(ReviewStatus.APPROVED_STATUSES)
        placeholders = ",".join("?" * len(approved_statuses))
        cursor = await conn.execute(
            f"""SELECT module_id, COUNT(*) as wins FROM llm_quiz_attempts
               WHERE user_id = ? AND student_wins = 1
               AND review_status IN ({placeholders})
               GROUP BY module_id""",
            (user_id,) + approved_statuses,
        )
        rows = await cursor.fetchall()
        return {row["module_id"]: row["wins"] for row in rows}

    async def get_attempts_for_module(
        self, user_id: int, module_id: str
    ) -> List[LLMQuizAttempt]:
        """Get all LLM quiz attempts for a specific module."""
        conn = self.connection
        cursor = await conn.execute(
            """SELECT * FROM llm_quiz_attempts
               WHERE user_id = ? AND module_id = ?
               ORDER BY created_at DESC""",
            (user_id, module_id),
        )
        rows = await cursor.fetchall()
        return [row_to_llm_quiz_attempt(row) for row in rows]

    async def get_recent_for_user(
        self, user_id: int, limit: int = 10
    ) -> List[LLMQuizAttempt]:
        """Get recent LLM quiz attempts for a user."""
        conn = self.connection
        cursor = await conn.execute(
            """SELECT * FROM llm_quiz_attempts
               WHERE user_id = ?
               ORDER BY created_at DESC
               LIMIT ?""",
            (user_id, limit),
        )
        rows = await cursor.fetchall()
        return [row_to_llm_quiz_attempt(row) for row in rows]

    async def count_total_for_user(self, user_id: int) -> int:
        """Get total LLM quiz attempts for a user."""
        conn = self.connection
        cursor = await conn.execute(
            "SELECT COUNT(*) as total FROM llm_quiz_attempts WHERE user_id = ?",
            (user_id,),
        )
        row = await cursor.fetchone()
        return row["total"] if row else 0

    async def count_wins_for_user(self, user_id: int) -> int:
        """Get total wins for a user across all modules (only approved ones)."""
        conn = self.connection
        approved_statuses = tuple(ReviewStatus.APPROVED_STATUSES)
        placeholders = ",".join("?" * len(approved_statuses))
        cursor = await conn.execute(
            f"""SELECT COUNT(*) as wins FROM llm_quiz_attempts
               WHERE user_id = ? AND student_wins = 1
               AND review_status IN ({placeholders})""",
            (user_id,) + approved_statuses,
        )
        row = await cursor.fetchone()
        return row["wins"] if row else 0
