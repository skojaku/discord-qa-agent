"""Repository for database CRUD operations."""

from datetime import datetime
from typing import List, Optional

from .connection import Database
from .models import User, Interaction, QuizAttempt, ConceptMastery


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

        return User(
            id=row["id"],
            discord_id=row["discord_id"],
            username=row["username"],
            created_at=row["created_at"],
            last_active=row["last_active"],
        )

    # ==================== Interaction Operations ====================

    async def log_interaction(
        self, user_id: int, module_id: str, question: str, response: str
    ) -> Interaction:
        """Log a Q&A interaction."""
        conn = self.db.connection
        cursor = await conn.execute(
            """INSERT INTO interactions (user_id, module_id, question, response)
               VALUES (?, ?, ?, ?)""",
            (user_id, module_id, question, response),
        )
        await conn.commit()

        return Interaction(
            id=cursor.lastrowid,
            user_id=user_id,
            module_id=module_id,
            question=question,
            response=response,
            created_at=datetime.now(),
        )

    async def get_recent_interactions(
        self, user_id: int, limit: int = 10
    ) -> List[Interaction]:
        """Get recent interactions for a user."""
        conn = self.db.connection
        cursor = await conn.execute(
            """SELECT * FROM interactions
               WHERE user_id = ?
               ORDER BY created_at DESC
               LIMIT ?""",
            (user_id, limit),
        )
        rows = await cursor.fetchall()

        return [
            Interaction(
                id=row["id"],
                user_id=row["user_id"],
                module_id=row["module_id"],
                question=row["question"],
                response=row["response"],
                created_at=row["created_at"],
            )
            for row in rows
        ]

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

        return [
            QuizAttempt(
                id=row["id"],
                user_id=row["user_id"],
                module_id=row["module_id"],
                concept_id=row["concept_id"],
                quiz_format=row["quiz_format"],
                question=row["question"],
                user_answer=row["user_answer"],
                correct_answer=row["correct_answer"],
                is_correct=bool(row["is_correct"]),
                llm_feedback=row["llm_feedback"],
                llm_quality_score=row["llm_quality_score"],
                created_at=row["created_at"],
            )
            for row in rows
        ]

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

        return [
            QuizAttempt(
                id=row["id"],
                user_id=row["user_id"],
                module_id=row["module_id"],
                concept_id=row["concept_id"],
                quiz_format=row["quiz_format"],
                question=row["question"],
                user_answer=row["user_answer"],
                correct_answer=row["correct_answer"],
                is_correct=bool(row["is_correct"]),
                llm_feedback=row["llm_feedback"],
                llm_quality_score=row["llm_quality_score"],
                created_at=row["created_at"],
            )
            for row in rows
        ]

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
            return ConceptMastery(
                id=row["id"],
                user_id=row["user_id"],
                concept_id=row["concept_id"],
                total_attempts=row["total_attempts"],
                correct_attempts=row["correct_attempts"],
                avg_quality_score=row["avg_quality_score"],
                mastery_level=row["mastery_level"],
                last_attempt_at=row["last_attempt_at"],
                updated_at=row["updated_at"],
            )

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

        return [
            ConceptMastery(
                id=row["id"],
                user_id=row["user_id"],
                concept_id=row["concept_id"],
                total_attempts=row["total_attempts"],
                correct_attempts=row["correct_attempts"],
                avg_quality_score=row["avg_quality_score"],
                mastery_level=row["mastery_level"],
                last_attempt_at=row["last_attempt_at"],
                updated_at=row["updated_at"],
            )
            for row in rows
        ]

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
