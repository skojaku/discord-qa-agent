"""Service for status and progress tracking."""

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional

from .base import BaseService
from ..database.models import ConceptMastery, Interaction, QuizAttempt

logger = logging.getLogger(__name__)


@dataclass
class StatusSummary:
    """Summary of user's learning status."""

    total_concepts: int
    concepts_started: int
    mastered_count: int
    proficient_count: int
    learning_count: int
    novice_count: int
    total_quiz_attempts: int
    correct_quiz_attempts: int
    progress_percentage: float
    accuracy_percentage: float


@dataclass
class ModuleProgress:
    """Progress for a single module."""

    module_id: str
    module_name: str
    concepts: List[dict]  # List of concept progress dicts


class StatusService(BaseService):
    """Service for status and progress tracking."""

    async def get_summary(self, user_discord_id: str, username: str) -> StatusSummary:
        """Get summary of user's learning progress.

        Args:
            user_discord_id: Discord user ID
            username: User's display name

        Returns:
            StatusSummary with progress data
        """
        user = await self.repository.get_or_create_user(
            discord_id=user_discord_id,
            username=username,
        )

        summary = await self.repository.get_mastery_summary(user.id)
        total_concepts = len(self.course.get_all_concepts())

        mastered = summary.get("mastered", 0)
        proficient = summary.get("proficient", 0)
        learning = summary.get("learning", 0)
        novice = summary.get("novice", 0)
        concepts_started = mastered + proficient + learning + novice

        total_quizzes = summary.get("total_quiz_attempts", 0)
        correct_quizzes = summary.get("total_correct", 0)

        progress_pct = (
            (mastered + proficient) / total_concepts * 100
            if total_concepts > 0
            else 0
        )
        accuracy_pct = correct_quizzes / total_quizzes * 100 if total_quizzes > 0 else 0

        return StatusSummary(
            total_concepts=total_concepts,
            concepts_started=concepts_started,
            mastered_count=mastered,
            proficient_count=proficient,
            learning_count=learning,
            novice_count=novice,
            total_quiz_attempts=total_quizzes,
            correct_quiz_attempts=correct_quizzes,
            progress_percentage=progress_pct,
            accuracy_percentage=accuracy_pct,
        )

    async def get_detailed_progress(
        self, user_discord_id: str, username: str
    ) -> List[ModuleProgress]:
        """Get detailed progress by module.

        Args:
            user_discord_id: Discord user ID
            username: User's display name

        Returns:
            List of ModuleProgress for each module
        """
        user = await self.repository.get_or_create_user(
            discord_id=user_discord_id,
            username=username,
        )

        # Get all mastery records
        mastery_records = await self.repository.get_user_mastery_all(user.id)
        mastery_by_concept = {m.concept_id: m for m in mastery_records}

        module_progress = []
        for module in self.course.modules:
            concepts = []
            for concept in module.concepts:
                mastery = mastery_by_concept.get(concept.id)
                if mastery:
                    accuracy = (
                        mastery.correct_attempts / mastery.total_attempts * 100
                        if mastery.total_attempts > 0
                        else 0
                    )
                    concepts.append({
                        "name": concept.name,
                        "id": concept.id,
                        "mastery_level": mastery.mastery_level,
                        "total_attempts": mastery.total_attempts,
                        "correct_attempts": mastery.correct_attempts,
                        "accuracy": accuracy,
                        "started": True,
                    })
                else:
                    concepts.append({
                        "name": concept.name,
                        "id": concept.id,
                        "mastery_level": "novice",
                        "total_attempts": 0,
                        "correct_attempts": 0,
                        "accuracy": 0,
                        "started": False,
                    })

            module_progress.append(ModuleProgress(
                module_id=module.id,
                module_name=module.name,
                concepts=concepts,
            ))

        return module_progress

    async def get_recent_activity(
        self, user_discord_id: str, username: str
    ) -> Dict[str, List]:
        """Get recent quiz attempts and interactions.

        Args:
            user_discord_id: Discord user ID
            username: User's display name

        Returns:
            Dictionary with 'quizzes' and 'interactions' lists
        """
        user = await self.repository.get_or_create_user(
            discord_id=user_discord_id,
            username=username,
        )

        recent_quizzes = await self.repository.get_recent_quiz_attempts(
            user.id, limit=5
        )
        recent_interactions = await self.repository.get_recent_interactions(
            user.id, limit=5
        )

        return {
            "quizzes": recent_quizzes,
            "interactions": recent_interactions,
        }

    async def get_concepts_by_mastery(
        self, user_discord_id: str, username: str
    ) -> Dict[str, List[dict]]:
        """Get concepts grouped by mastery level.

        Args:
            user_discord_id: Discord user ID
            username: User's display name

        Returns:
            Dictionary mapping mastery levels to lists of concept info
        """
        user = await self.repository.get_or_create_user(
            discord_id=user_discord_id,
            username=username,
        )

        mastery_records = await self.repository.get_user_mastery_all(user.id)
        all_concepts = self.course.get_all_concepts()

        levels = {
            "mastered": [],
            "proficient": [],
            "learning": [],
            "novice": [],
        }

        for mastery in mastery_records:
            concept = all_concepts.get(mastery.concept_id)
            if concept:
                levels[mastery.mastery_level].append({
                    "name": concept.name,
                    "id": concept.id,
                    "correct_attempts": mastery.correct_attempts,
                    "total_attempts": mastery.total_attempts,
                })

        return levels
