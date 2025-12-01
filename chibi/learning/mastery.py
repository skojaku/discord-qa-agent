"""Mastery calculation for learning profile system."""

from dataclasses import dataclass
from enum import Enum
from typing import List

from ..database.models import QuizAttempt


class MasteryLevel(Enum):
    """Mastery levels for concepts."""

    NOVICE = "novice"
    LEARNING = "learning"
    PROFICIENT = "proficient"
    MASTERED = "mastered"

    @property
    def emoji(self) -> str:
        """Get emoji for this mastery level."""
        return {
            MasteryLevel.NOVICE: "🌱",
            MasteryLevel.LEARNING: "📖",
            MasteryLevel.PROFICIENT: "⭐",
            MasteryLevel.MASTERED: "🏆",
        }.get(self, "⬜")

    @property
    def display_name(self) -> str:
        """Get display name for this mastery level."""
        return self.value.capitalize()


@dataclass
class MasteryConfig:
    """Configuration for mastery calculation."""

    min_attempts_for_mastery: int = 3
    quality_threshold: float = 3.5
    correct_ratio_threshold: float = 0.7

    # Level thresholds
    mastered_ratio: float = 0.85
    mastered_quality: float = 4.0
    proficient_ratio: float = 0.6
    learning_ratio: float = 0.3


@dataclass
class MasteryStats:
    """Statistics for mastery calculation."""

    total_attempts: int = 0
    correct_attempts: int = 0
    avg_quality_score: float = 0.0
    mastery_level: MasteryLevel = MasteryLevel.NOVICE

    @property
    def correct_ratio(self) -> float:
        """Calculate correct answer ratio."""
        return self.correct_attempts / self.total_attempts if self.total_attempts > 0 else 0.0

    @property
    def accuracy_percentage(self) -> float:
        """Get accuracy as percentage."""
        return self.correct_ratio * 100


class MasteryCalculator:
    """Calculator for determining concept mastery levels."""

    def __init__(self, config: MasteryConfig = None):
        self.config = config or MasteryConfig()

    def calculate_from_attempts(self, attempts: List[QuizAttempt]) -> MasteryStats:
        """Calculate mastery stats from quiz attempts.

        Args:
            attempts: List of quiz attempts for a concept

        Returns:
            MasteryStats with calculated values
        """
        if not attempts:
            return MasteryStats()

        total = len(attempts)
        correct = sum(1 for a in attempts if a.is_correct)

        # Calculate average quality score from attempts that have one
        quality_scores = [
            a.llm_quality_score
            for a in attempts
            if a.llm_quality_score is not None and a.llm_quality_score > 0
        ]
        avg_quality = sum(quality_scores) / len(quality_scores) if quality_scores else 0.0

        level = self.calculate_level(total, correct, avg_quality)

        return MasteryStats(
            total_attempts=total,
            correct_attempts=correct,
            avg_quality_score=avg_quality,
            mastery_level=level,
        )

    def calculate_level(
        self,
        total_attempts: int,
        correct_attempts: int,
        avg_quality_score: float,
    ) -> MasteryLevel:
        """Calculate mastery level based on performance metrics.

        Uses a hybrid approach combining:
        1. Minimum number of attempts required
        2. Correct answer ratio
        3. Average quality score (for free-form answers)

        Args:
            total_attempts: Total number of quiz attempts
            correct_attempts: Number of correct attempts
            avg_quality_score: Average LLM quality score (1-5)

        Returns:
            Calculated MasteryLevel
        """
        # Need minimum attempts before advancing from novice
        if total_attempts < self.config.min_attempts_for_mastery:
            return MasteryLevel.NOVICE

        ratio = correct_attempts / total_attempts if total_attempts > 0 else 0

        # Mastered: High ratio AND high quality
        if ratio >= self.config.mastered_ratio:
            if avg_quality_score >= self.config.mastered_quality or avg_quality_score == 0:
                return MasteryLevel.MASTERED

        # Proficient: Good ratio
        if ratio >= self.config.proficient_ratio:
            return MasteryLevel.PROFICIENT

        # Learning: Some progress
        if ratio >= self.config.learning_ratio:
            return MasteryLevel.LEARNING

        return MasteryLevel.NOVICE

    def level_from_string(self, level_str: str) -> MasteryLevel:
        """Convert string to MasteryLevel.

        Args:
            level_str: Level string (e.g., "mastered", "learning")

        Returns:
            Corresponding MasteryLevel
        """
        try:
            return MasteryLevel(level_str.lower())
        except ValueError:
            return MasteryLevel.NOVICE

    def get_next_level(self, current: MasteryLevel) -> MasteryLevel:
        """Get the next mastery level.

        Args:
            current: Current mastery level

        Returns:
            Next level, or current if already mastered
        """
        levels = list(MasteryLevel)
        current_idx = levels.index(current)
        if current_idx < len(levels) - 1:
            return levels[current_idx + 1]
        return current

    def get_requirements_for_level(self, level: MasteryLevel) -> str:
        """Get human-readable requirements for a mastery level.

        Args:
            level: Target mastery level

        Returns:
            Description of requirements
        """
        min_attempts = self.config.min_attempts_for_mastery

        if level == MasteryLevel.MASTERED:
            return (
                f"At least {min_attempts} attempts with {self.config.mastered_ratio*100:.0f}%+ "
                f"accuracy and quality score of {self.config.mastered_quality}+"
            )
        elif level == MasteryLevel.PROFICIENT:
            return (
                f"At least {min_attempts} attempts with {self.config.proficient_ratio*100:.0f}%+ accuracy"
            )
        elif level == MasteryLevel.LEARNING:
            return (
                f"At least {min_attempts} attempts with {self.config.learning_ratio*100:.0f}%+ accuracy"
            )
        else:
            return "Start practicing with quizzes!"
