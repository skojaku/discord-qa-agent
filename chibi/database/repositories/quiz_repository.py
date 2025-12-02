"""Quiz repository for quiz attempt database operations."""

from datetime import datetime
from typing import List, Optional

from ..mappers import row_to_quiz_attempt
from ..models import QuizAttempt
from .base import BaseRepository


class QuizRepository(BaseRepository):
    """Repository for quiz attempt operations."""

    async def log_attempt(
        self,
        user_id: int,
        module_id: str,
        concept_id: str,
        quiz_format: str,
        question: str,
        user_answer: str,
        correct_answer: Optional[str],
        is_correct: bool,
        llm_feedback: Optional[str] = None,
        llm_quality_score: Optional[int] = None,
    ) -> QuizAttempt:
        """Log a quiz attempt."""
        conn = self.connection
        cursor = await conn.execute(
            """INSERT INTO quiz_attempts
               (user_id, module_id, concept_id, quiz_format, question,
                user_answer, correct_answer, is_correct, llm_feedback, llm_quality_score)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                user_id,
                module_id,
                concept_id,
                quiz_format,
                question,
                user_answer,
                correct_answer,
                is_correct,
                llm_feedback,
                llm_quality_score,
            ),
        )
        await conn.commit()

        return QuizAttempt(
            id=cursor.lastrowid,
            user_id=user_id,
            module_id=module_id,
            concept_id=concept_id,
            quiz_format=quiz_format,
            question=question,
            user_answer=user_answer,
            correct_answer=correct_answer,
            is_correct=is_correct,
            llm_feedback=llm_feedback,
            llm_quality_score=llm_quality_score,
            created_at=datetime.now(),
        )

    async def get_for_concept(
        self, user_id: int, concept_id: str
    ) -> List[QuizAttempt]:
        """Get all quiz attempts for a specific concept."""
        conn = self.connection
        cursor = await conn.execute(
            """SELECT * FROM quiz_attempts
               WHERE user_id = ? AND concept_id = ?
               ORDER BY created_at DESC""",
            (user_id, concept_id),
        )
        rows = await cursor.fetchall()

        return [row_to_quiz_attempt(row) for row in rows]

    async def get_recent(self, user_id: int, limit: int = 10) -> List[QuizAttempt]:
        """Get recent quiz attempts for a user."""
        conn = self.connection
        cursor = await conn.execute(
            """SELECT * FROM quiz_attempts
               WHERE user_id = ?
               ORDER BY created_at DESC
               LIMIT ?""",
            (user_id, limit),
        )
        rows = await cursor.fetchall()

        return [row_to_quiz_attempt(row) for row in rows]

    async def count_for_user(self, user_id: int) -> int:
        """Get total quiz attempts for a user."""
        conn = self.connection
        cursor = await conn.execute(
            "SELECT COUNT(*) as total FROM quiz_attempts WHERE user_id = ?",
            (user_id,),
        )
        row = await cursor.fetchone()
        return row["total"] if row else 0

    async def count_correct_for_user(self, user_id: int) -> int:
        """Get total correct quiz attempts for a user."""
        conn = self.connection
        cursor = await conn.execute(
            "SELECT COUNT(*) as correct FROM quiz_attempts WHERE user_id = ? AND is_correct = 1",
            (user_id,),
        )
        row = await cursor.fetchone()
        return row["correct"] if row else 0
