"""Repository for database CRUD operations."""

from datetime import datetime
from typing import List, Optional

from .connection import Database
from .mappers import (
    row_to_concept_mastery,
    row_to_quiz_attempt,
    row_to_user,
)
from .models import User, QuizAttempt, ConceptMastery


class Repository:
    """Repository for all database operations."""

    def __init__(self, database: Database):
        self.db = database

    # ==================== User Operations ====================

    async def get_or_create_user(self, discord_id: str, username: str) -> User:
        """Get existing user or create new one."""
        conn = self.db.connection

        # Try to get existing user
        cursor = await conn.execute(
            "SELECT * FROM users WHERE discord_id = ?", (discord_id,)
        )
        row = await cursor.fetchone()

        if row:
            # Update last_active and username
            await conn.execute(
                "UPDATE users SET last_active = CURRENT_TIMESTAMP, username = ? WHERE discord_id = ?",
                (username, discord_id),
            )
            await conn.commit()
            return User(
                id=row["id"],
                discord_id=row["discord_id"],
                username=username,
                created_at=row["created_at"],
                last_active=datetime.now(),
            )

        # Create new user
        cursor = await conn.execute(
            "INSERT INTO users (discord_id, username) VALUES (?, ?)",
            (discord_id, username),
        )
        await conn.commit()

        return User(
            id=cursor.lastrowid,
            discord_id=discord_id,
            username=username,
            created_at=datetime.now(),
            last_active=datetime.now(),
        )

    async def get_user_by_discord_id(self, discord_id: str) -> Optional[User]:
        """Get user by Discord ID."""
        conn = self.db.connection
        cursor = await conn.execute(
            "SELECT * FROM users WHERE discord_id = ?", (discord_id,)
        )
        row = await cursor.fetchone()

        if not row:
            return None

        return row_to_user(row)

    # ==================== Quiz Operations ====================

    async def log_quiz_attempt(
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
        conn = self.db.connection
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

    async def get_quiz_attempts_for_concept(
        self, user_id: int, concept_id: str
    ) -> List[QuizAttempt]:
        """Get all quiz attempts for a specific concept."""
        conn = self.db.connection
        cursor = await conn.execute(
            """SELECT * FROM quiz_attempts
               WHERE user_id = ? AND concept_id = ?
               ORDER BY created_at DESC""",
            (user_id, concept_id),
        )
        rows = await cursor.fetchall()

        return [row_to_quiz_attempt(row) for row in rows]

    async def get_recent_quiz_attempts(
        self, user_id: int, limit: int = 10
    ) -> List[QuizAttempt]:
        """Get recent quiz attempts for a user."""
        conn = self.db.connection
        cursor = await conn.execute(
            """SELECT * FROM quiz_attempts
               WHERE user_id = ?
               ORDER BY created_at DESC
               LIMIT ?""",
            (user_id, limit),
        )
        rows = await cursor.fetchall()

        return [row_to_quiz_attempt(row) for row in rows]

    # ==================== Mastery Operations ====================

    async def get_or_create_mastery(
        self, user_id: int, concept_id: str
    ) -> ConceptMastery:
        """Get or create concept mastery record."""
        conn = self.db.connection
        cursor = await conn.execute(
            "SELECT * FROM concept_mastery WHERE user_id = ? AND concept_id = ?",
            (user_id, concept_id),
        )
        row = await cursor.fetchone()

        if row:
            return row_to_concept_mastery(row)

        # Create new mastery record
        cursor = await conn.execute(
            "INSERT INTO concept_mastery (user_id, concept_id) VALUES (?, ?)",
            (user_id, concept_id),
        )
        await conn.commit()

        return ConceptMastery(
            id=cursor.lastrowid,
            user_id=user_id,
            concept_id=concept_id,
        )

    async def update_mastery(
        self,
        user_id: int,
        concept_id: str,
        total_attempts: int,
        correct_attempts: int,
        avg_quality_score: float,
        mastery_level: str,
    ) -> None:
        """Update concept mastery record."""
        conn = self.db.connection
        await conn.execute(
            """UPDATE concept_mastery
               SET total_attempts = ?,
                   correct_attempts = ?,
                   avg_quality_score = ?,
                   mastery_level = ?,
                   last_attempt_at = CURRENT_TIMESTAMP,
                   updated_at = CURRENT_TIMESTAMP
               WHERE user_id = ? AND concept_id = ?""",
            (
                total_attempts,
                correct_attempts,
                avg_quality_score,
                mastery_level,
                user_id,
                concept_id,
            ),
        )
        await conn.commit()

    async def get_user_mastery_all(self, user_id: int) -> List[ConceptMastery]:
        """Get all concept mastery records for a user."""
        conn = self.db.connection
        cursor = await conn.execute(
            "SELECT * FROM concept_mastery WHERE user_id = ? ORDER BY concept_id",
            (user_id,),
        )
        rows = await cursor.fetchall()

        return [row_to_concept_mastery(row) for row in rows]

    async def get_mastery_summary(self, user_id: int) -> dict:
        """Get summary of user's mastery progress."""
        conn = self.db.connection

        # Get counts by mastery level
        cursor = await conn.execute(
            """SELECT mastery_level, COUNT(*) as count
               FROM concept_mastery
               WHERE user_id = ?
               GROUP BY mastery_level""",
            (user_id,),
        )
        rows = await cursor.fetchall()

        summary = {
            "novice": 0,
            "learning": 0,
            "proficient": 0,
            "mastered": 0,
        }
        for row in rows:
            if row["mastery_level"] in summary:
                summary[row["mastery_level"]] = row["count"]

        # Get total quiz attempts
        cursor = await conn.execute(
            "SELECT COUNT(*) as total FROM quiz_attempts WHERE user_id = ?",
            (user_id,),
        )
        row = await cursor.fetchone()
        summary["total_quiz_attempts"] = row["total"] if row else 0

        # Get total correct
        cursor = await conn.execute(
            "SELECT COUNT(*) as correct FROM quiz_attempts WHERE user_id = ? AND is_correct = 1",
            (user_id,),
        )
        row = await cursor.fetchone()
        summary["total_correct"] = row["correct"] if row else 0

        return summary

    # ==================== Admin Operations ====================

    async def get_all_users(self) -> List[User]:
        """Get all users in the database."""
        conn = self.db.connection
        cursor = await conn.execute(
            "SELECT * FROM users ORDER BY username"
        )
        rows = await cursor.fetchall()

        return [row_to_user(row) for row in rows]

    async def get_all_mastery_records(self) -> List[ConceptMastery]:
        """Get all concept mastery records for all users."""
        conn = self.db.connection
        cursor = await conn.execute(
            "SELECT * FROM concept_mastery ORDER BY user_id, concept_id"
        )
        rows = await cursor.fetchall()

        return [row_to_concept_mastery(row) for row in rows]

    async def get_mastery_by_module(
        self, user_id: int, concept_ids: List[str]
    ) -> List[ConceptMastery]:
        """Get mastery records for specific concepts (module filtering).

        Args:
            user_id: The user's database ID
            concept_ids: List of concept IDs to filter by

        Returns:
            List of ConceptMastery records for the specified concepts
        """
        if not concept_ids:
            return []

        conn = self.db.connection
        placeholders = ",".join("?" * len(concept_ids))
        cursor = await conn.execute(
            f"""SELECT * FROM concept_mastery
               WHERE user_id = ? AND concept_id IN ({placeholders})
               ORDER BY concept_id""",
            (user_id, *concept_ids),
        )
        rows = await cursor.fetchall()

        return [row_to_concept_mastery(row) for row in rows]
