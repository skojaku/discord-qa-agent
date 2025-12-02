"""Repository facade for backward-compatible database operations.

This module provides a unified interface to the database while internally
delegating to domain-specific repositories.
"""

from typing import List, Optional

from .connection import Database
from .models import User, QuizAttempt, ConceptMastery
from .repositories import UserRepository, QuizRepository, MasteryRepository


class Repository:
    """Facade for all database operations.

    Maintains backward compatibility while delegating to specialized repositories.
    """

    def __init__(self, database: Database):
        self.db = database
        # Initialize specialized repositories
        self.users = UserRepository(database)
        self.quizzes = QuizRepository(database)
        self.mastery = MasteryRepository(database)

    # ==================== User Operations ====================
    # Delegate to UserRepository

    async def get_or_create_user(self, discord_id: str, username: str) -> User:
        """Get existing user or create new one."""
        return await self.users.get_or_create(discord_id, username)

    async def get_user_by_discord_id(self, discord_id: str) -> Optional[User]:
        """Get user by Discord ID."""
        return await self.users.get_by_discord_id(discord_id)

    async def get_all_users(self) -> List[User]:
        """Get all users in the database."""
        return await self.users.get_all()

    async def search_user_by_identifier(self, identifier: str) -> Optional[User]:
        """Search for a user by Discord ID, username, or partial match."""
        return await self.users.search_by_identifier(identifier)

    # ==================== Quiz Operations ====================
    # Delegate to QuizRepository

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
        return await self.quizzes.log_attempt(
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
        )

    async def get_quiz_attempts_for_concept(
        self, user_id: int, concept_id: str
    ) -> List[QuizAttempt]:
        """Get all quiz attempts for a specific concept."""
        return await self.quizzes.get_for_concept(user_id, concept_id)

    async def get_recent_quiz_attempts(
        self, user_id: int, limit: int = 10
    ) -> List[QuizAttempt]:
        """Get recent quiz attempts for a user."""
        return await self.quizzes.get_recent(user_id, limit)

    # ==================== Mastery Operations ====================
    # Delegate to MasteryRepository

    async def get_or_create_mastery(
        self, user_id: int, concept_id: str
    ) -> ConceptMastery:
        """Get or create concept mastery record."""
        return await self.mastery.get_or_create(user_id, concept_id)

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
        await self.mastery.update(
            user_id=user_id,
            concept_id=concept_id,
            total_attempts=total_attempts,
            correct_attempts=correct_attempts,
            avg_quality_score=avg_quality_score,
            mastery_level=mastery_level,
        )

    async def get_user_mastery_all(self, user_id: int) -> List[ConceptMastery]:
        """Get all concept mastery records for a user."""
        return await self.mastery.get_all_for_user(user_id)

    async def get_mastery_summary(self, user_id: int) -> dict:
        """Get summary of user's mastery progress."""
        # Get mastery level counts
        summary = await self.mastery.get_summary(user_id)

        # Add quiz attempt stats
        summary["total_quiz_attempts"] = await self.quizzes.count_for_user(user_id)
        summary["total_correct"] = await self.quizzes.count_correct_for_user(user_id)

        return summary

    async def get_all_mastery_records(self) -> List[ConceptMastery]:
        """Get all concept mastery records for all users."""
        return await self.mastery.get_all()

    async def get_mastery_by_module(
        self, user_id: int, concept_ids: List[str]
    ) -> List[ConceptMastery]:
        """Get mastery records for specific concepts (module filtering)."""
        return await self.mastery.get_by_concepts(user_id, concept_ids)
