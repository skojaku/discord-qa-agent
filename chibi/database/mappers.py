"""Row-to-model mappers for database operations."""

from typing import Any

from .models import User, Interaction, QuizAttempt, ConceptMastery


def row_to_user(row: Any) -> User:
    """Convert database row to User model."""
    return User(
        id=row["id"],
        discord_id=row["discord_id"],
        username=row["username"],
        created_at=row["created_at"],
        last_active=row["last_active"],
    )


def row_to_interaction(row: Any) -> Interaction:
    """Convert database row to Interaction model."""
    return Interaction(
        id=row["id"],
        user_id=row["user_id"],
        module_id=row["module_id"],
        question=row["question"],
        response=row["response"],
        created_at=row["created_at"],
    )


def row_to_quiz_attempt(row: Any) -> QuizAttempt:
    """Convert database row to QuizAttempt model."""
    return QuizAttempt(
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


def row_to_concept_mastery(row: Any) -> ConceptMastery:
    """Convert database row to ConceptMastery model."""
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
