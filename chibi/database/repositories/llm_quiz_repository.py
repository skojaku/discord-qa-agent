"""LLM Quiz Challenge repository for database operations."""

from datetime import datetime
from typing import Dict, List, Optional

from ..mappers import row_to_llm_quiz_attempt
from ..models import LLMQuizAttempt
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
    ) -> LLMQuizAttempt:
        """Log an LLM quiz challenge attempt."""
        conn = self.connection
        cursor = await conn.execute(
            """INSERT INTO llm_quiz_attempts
               (user_id, module_id, question, student_answer, llm_answer,
                student_wins, student_answer_correctness, evaluation_explanation)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                user_id,
                module_id,
                question,
                student_answer,
                llm_answer,
                student_wins,
                student_answer_correctness,
                evaluation_explanation,
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
            created_at=datetime.now(),
        )

    async def count_wins_for_module(self, user_id: int, module_id: str) -> int:
        """Count successful stumps for a user in a module."""
        conn = self.connection
        cursor = await conn.execute(
            """SELECT COUNT(*) as wins FROM llm_quiz_attempts
               WHERE user_id = ? AND module_id = ? AND student_wins = 1""",
            (user_id, module_id),
        )
        row = await cursor.fetchone()
        return row["wins"] if row else 0

    async def get_progress_by_module(self, user_id: int) -> Dict[str, int]:
        """Get stump count per module for a user."""
        conn = self.connection
        cursor = await conn.execute(
            """SELECT module_id, COUNT(*) as wins FROM llm_quiz_attempts
               WHERE user_id = ? AND student_wins = 1
               GROUP BY module_id""",
            (user_id,),
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
        """Get total wins for a user across all modules."""
        conn = self.connection
        cursor = await conn.execute(
            "SELECT COUNT(*) as wins FROM llm_quiz_attempts WHERE user_id = ? AND student_wins = 1",
            (user_id,),
        )
        row = await cursor.fetchone()
        return row["wins"] if row else 0
