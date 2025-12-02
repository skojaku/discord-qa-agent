"""Row-to-model mappers for database operations."""

from datetime import datetime
from typing import Any, Optional

from .models import User, QuizAttempt, ConceptMastery, LLMQuizAttempt


def _parse_datetime(value: Any) -> Optional[datetime]:
    """Parse a datetime value from SQLite.

    SQLite stores datetimes as strings in ISO format.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        # SQLite stores in ISO format: "YYYY-MM-DD HH:MM:SS.ffffff" or "YYYY-MM-DD HH:MM:SS"
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
    return None


def row_to_user(row: Any) -> User:
    """Convert database row to User model."""
    return User(
        id=row["id"],
        discord_id=row["discord_id"],
        username=row["username"],
        created_at=_parse_datetime(row["created_at"]),
        last_active=_parse_datetime(row["last_active"]),
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
        created_at=_parse_datetime(row["created_at"]),
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
        last_attempt_at=_parse_datetime(row["last_attempt_at"]),
        updated_at=_parse_datetime(row["updated_at"]),
    )


def row_to_llm_quiz_attempt(row: Any) -> LLMQuizAttempt:
    """Convert database row to LLMQuizAttempt model."""
    return LLMQuizAttempt(
        id=row["id"],
        user_id=row["user_id"],
        module_id=row["module_id"],
        question=row["question"],
        student_answer=row["student_answer"],
        llm_answer=row["llm_answer"],
        student_wins=bool(row["student_wins"]),
        student_answer_correctness=row["student_answer_correctness"],
        evaluation_explanation=row["evaluation_explanation"],
        created_at=_parse_datetime(row["created_at"]),
    )
