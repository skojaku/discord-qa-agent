"""Data models for Chibi bot database."""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class User:
    """Represents a Discord user in the database."""

    id: Optional[int]
    discord_id: str
    username: str
    created_at: Optional[datetime] = None
    last_active: Optional[datetime] = None


@dataclass
class QuizAttempt:
    """Represents a quiz attempt."""

    id: Optional[int]
    user_id: int
    module_id: str
    concept_id: str
    quiz_format: str
    question: str
    user_answer: str
    correct_answer: Optional[str]
    is_correct: bool
    llm_feedback: Optional[str] = None
    llm_quality_score: Optional[int] = None  # 1-5 for free-form
    created_at: Optional[datetime] = None


@dataclass
class ConceptMastery:
    """Represents a user's mastery of a concept."""

    id: Optional[int]
    user_id: int
    concept_id: str
    total_attempts: int = 0
    correct_attempts: int = 0
    avg_quality_score: float = 0.0
    mastery_level: str = "novice"  # novice, learning, proficient, mastered
    last_attempt_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class LLMQuizAttempt:
    """Represents an LLM Quiz Challenge attempt where student tries to stump the AI."""

    id: Optional[int]
    user_id: int
    module_id: str
    question: str
    student_answer: str
    llm_answer: str
    student_wins: bool
    student_answer_correctness: str  # "CORRECT", "INCORRECT", "PARTIALLY_CORRECT"
    evaluation_explanation: Optional[str] = None
    created_at: Optional[datetime] = None
