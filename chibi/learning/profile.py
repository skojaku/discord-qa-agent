"""Student profile management for learning system."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

from ..database.models import ConceptMastery, Interaction, QuizAttempt
from ..database.repository import Repository
from .mastery import MasteryCalculator, MasteryLevel, MasteryStats


@dataclass
class StudentProfile:
    """Complete profile of a student's learning progress."""

    user_id: int
    discord_id: str
    username: str
    created_at: Optional[datetime] = None
    last_active: Optional[datetime] = None

    # Aggregated stats
    total_interactions: int = 0
    total_quiz_attempts: int = 0
    total_correct: int = 0

    # Mastery by concept
    concept_mastery: Dict[str, MasteryStats] = field(default_factory=dict)

    # Recent activity
    recent_modules: List[str] = field(default_factory=list)
    recent_concepts: List[str] = field(default_factory=list)

    @property
    def overall_accuracy(self) -> float:
        """Calculate overall quiz accuracy."""
        if self.total_quiz_attempts == 0:
            return 0.0
        return self.total_correct / self.total_quiz_attempts * 100

    @property
    def mastered_count(self) -> int:
        """Count of mastered concepts."""
        return sum(
            1 for m in self.concept_mastery.values()
            if m.mastery_level == MasteryLevel.MASTERED
        )

    @property
    def proficient_count(self) -> int:
        """Count of proficient concepts."""
        return sum(
            1 for m in self.concept_mastery.values()
            if m.mastery_level == MasteryLevel.PROFICIENT
        )

    @property
    def learning_count(self) -> int:
        """Count of learning concepts."""
        return sum(
            1 for m in self.concept_mastery.values()
            if m.mastery_level == MasteryLevel.LEARNING
        )

    @property
    def novice_count(self) -> int:
        """Count of novice concepts."""
        return sum(
            1 for m in self.concept_mastery.values()
            if m.mastery_level == MasteryLevel.NOVICE
        )

    def get_mastery_summary(self) -> str:
        """Get a summary string of mastery progress."""
        if not self.concept_mastery:
            return "No concepts started yet"

        return (
            f"🏆 {self.mastered_count} | "
            f"⭐ {self.proficient_count} | "
            f"📖 {self.learning_count} | "
            f"🌱 {self.novice_count}"
        )

    def get_recent_topics_string(self, limit: int = 3) -> str:
        """Get recent topics as a string."""
        if not self.recent_concepts:
            return "None"
        return ", ".join(self.recent_concepts[:limit])


class ProfileManager:
    """Manager for student learning profiles."""

    def __init__(self, repository: Repository):
        self.repository = repository
        self.mastery_calculator = MasteryCalculator()

    async def get_profile(self, discord_id: str, username: str) -> StudentProfile:
        """Get or create a complete student profile.

        Args:
            discord_id: Discord user ID
            username: Discord username

        Returns:
            Complete StudentProfile with all data
        """
        # Get or create user
        user = await self.repository.get_or_create_user(discord_id, username)

        # Get mastery records
        mastery_records = await self.repository.get_user_mastery_all(user.id)

        # Convert to MasteryStats
        concept_mastery = {}
        for record in mastery_records:
            concept_mastery[record.concept_id] = MasteryStats(
                total_attempts=record.total_attempts,
                correct_attempts=record.correct_attempts,
                avg_quality_score=record.avg_quality_score,
                mastery_level=self.mastery_calculator.level_from_string(
                    record.mastery_level
                ),
            )

        # Get summary stats
        summary = await self.repository.get_mastery_summary(user.id)

        # Get recent interactions
        recent_interactions = await self.repository.get_recent_interactions(
            user.id, limit=5
        )
        recent_modules = list(dict.fromkeys(i.module_id for i in recent_interactions))

        # Get recent quiz attempts
        recent_quizzes = await self.repository.get_recent_quiz_attempts(
            user.id, limit=5
        )
        recent_concepts = list(dict.fromkeys(q.concept_id for q in recent_quizzes))

        return StudentProfile(
            user_id=user.id,
            discord_id=discord_id,
            username=username,
            created_at=user.created_at,
            last_active=user.last_active,
            total_interactions=len(recent_interactions),  # This is approximate
            total_quiz_attempts=summary.get("total_quiz_attempts", 0),
            total_correct=summary.get("total_correct", 0),
            concept_mastery=concept_mastery,
            recent_modules=recent_modules,
            recent_concepts=recent_concepts,
        )

    async def get_concept_progress(
        self, discord_id: str, concept_id: str
    ) -> Optional[MasteryStats]:
        """Get progress for a specific concept.

        Args:
            discord_id: Discord user ID
            concept_id: Concept ID

        Returns:
            MasteryStats for the concept, or None if no data
        """
        user = await self.repository.get_user_by_discord_id(discord_id)
        if not user:
            return None

        mastery = await self.repository.get_or_create_mastery(user.id, concept_id)

        return MasteryStats(
            total_attempts=mastery.total_attempts,
            correct_attempts=mastery.correct_attempts,
            avg_quality_score=mastery.avg_quality_score,
            mastery_level=self.mastery_calculator.level_from_string(
                mastery.mastery_level
            ),
        )

    async def get_weak_concepts(
        self, discord_id: str, limit: int = 5
    ) -> List[str]:
        """Get concepts where student needs more practice.

        Args:
            discord_id: Discord user ID
            limit: Maximum number to return

        Returns:
            List of concept IDs that need work
        """
        user = await self.repository.get_user_by_discord_id(discord_id)
        if not user:
            return []

        mastery_records = await self.repository.get_user_mastery_all(user.id)

        # Filter to concepts that are not mastered/proficient
        weak = [
            m.concept_id
            for m in mastery_records
            if m.mastery_level in ("novice", "learning")
            and m.total_attempts > 0
        ]

        return weak[:limit]

    async def suggest_next_concept(
        self, discord_id: str, module_id: str = None
    ) -> Optional[str]:
        """Suggest the next concept to study.

        Uses a simple heuristic:
        1. Prefer concepts the student has started but not mastered
        2. Consider prerequisites
        3. Optionally filter by module

        Args:
            discord_id: Discord user ID
            module_id: Optional module to filter by

        Returns:
            Suggested concept ID, or None
        """
        weak = await self.get_weak_concepts(discord_id)
        if weak:
            return weak[0]

        return None
