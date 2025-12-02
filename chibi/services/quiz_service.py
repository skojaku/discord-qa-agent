"""Service for quiz operations."""

import logging
import random
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, Optional

from .base import BaseService
from ..constants import (
    QUIZ_TIMEOUT_MINUTES,
    TEMPERATURE_EVALUATION,
    TEMPERATURE_QUIZ_GENERATION,
)
from ..learning.mastery import MasteryCalculator, MasteryConfig
from ..prompts.templates import PromptTemplates

logger = logging.getLogger(__name__)


@dataclass
class PendingQuiz:
    """Represents a pending quiz awaiting student response."""

    user_id: int
    db_user_id: int
    channel_id: int
    message_id: int
    module_id: str
    concept_id: str
    concept_name: str
    concept_description: str
    quiz_format: str
    question: str
    correct_answer: Optional[str]
    created_at: datetime


@dataclass
class QuizQuestion:
    """Generated quiz question."""

    question_text: str
    concept_name: str
    module_name: str
    selection_reason: str
    correct_answer: Optional[str]
    success: bool
    error_message: Optional[str] = None


@dataclass
class EvaluationResult:
    """Quiz answer evaluation result."""

    is_pass: bool
    is_partial: bool
    quality_score: int
    feedback: str
    success: bool
    error_message: Optional[str] = None


class QuizService(BaseService):
    """Service for quiz operations."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._pending_quizzes: Dict[int, PendingQuiz] = {}
        self._quiz_timeout = timedelta(minutes=QUIZ_TIMEOUT_MINUTES)

        # Initialize mastery calculator with config
        mastery_config = MasteryConfig(
            min_attempts_for_mastery=self.config.mastery.min_attempts_for_mastery,
        )
        self._mastery_calculator = MasteryCalculator(mastery_config)

    async def generate_quiz(
        self,
        user_discord_id: str,
        username: str,
        module_id: Optional[str] = None,
    ) -> tuple[QuizQuestion, Optional["PendingQuiz"]]:
        """Generate a quiz question for a user.

        Args:
            user_discord_id: Discord user ID
            username: User's display name
            module_id: Optional module ID to quiz on

        Returns:
            Tuple of (QuizQuestion, PendingQuiz or None)
        """
        # Get or create user
        user = await self.repository.get_or_create_user(
            discord_id=user_discord_id,
            username=username,
        )

        # Select module
        if module_id:
            module_obj = self.course.get_module(module_id)
        else:
            module_obj = random.choice(self.course.modules)

        if not module_obj:
            return QuizQuestion(
                question_text="",
                concept_name="",
                module_name="",
                selection_reason="",
                correct_answer=None,
                success=False,
                error_message="Could not find the specified module.",
            ), None

        # Select concept based on mastery level
        concept_obj, selection_reason = await self._select_concept_by_mastery(
            user.id, module_obj
        )

        if not concept_obj:
            return QuizQuestion(
                question_text="",
                concept_name="",
                module_name="",
                selection_reason="",
                correct_answer=None,
                success=False,
                error_message="No concepts found for this module.",
            ), None

        # Always use free-form format
        quiz_format = "free-form"

        # Generate quiz question
        quiz_prompt = PromptTemplates.get_quiz_prompt(
            concept_name=concept_obj.name,
            concept_description=concept_obj.description,
            quiz_focus=concept_obj.quiz_focus,
            quiz_format=quiz_format,
            module_content=module_obj.content or "",
        )

        response = await self.llm_manager.generate(
            prompt=quiz_prompt,
            max_tokens=self.config.llm.max_tokens,
            temperature=TEMPERATURE_QUIZ_GENERATION,
        )

        if not response:
            return QuizQuestion(
                question_text="",
                concept_name="",
                module_name="",
                selection_reason="",
                correct_answer=None,
                success=False,
                error_message=self.llm_manager.get_error_message(),
            ), None

        # Parse correct answer and clean question
        question_text = response.content
        correct_answer = self._extract_correct_answer(question_text, quiz_format)
        question_text = self._clean_question(question_text)

        # Create pending quiz (will be stored after message is sent)
        pending = PendingQuiz(
            user_id=int(user_discord_id),
            db_user_id=user.id,
            channel_id=0,  # To be set by caller
            message_id=0,  # To be set by caller
            module_id=module_obj.id,
            concept_id=concept_obj.id,
            concept_name=concept_obj.name,
            concept_description=concept_obj.description,
            quiz_format=quiz_format,
            question=question_text,
            correct_answer=correct_answer,
            created_at=datetime.now(),
        )

        logger.info(
            f"Quiz generated for {username}: {concept_obj.name} ({quiz_format})"
        )

        return QuizQuestion(
            question_text=question_text,
            concept_name=concept_obj.name,
            module_name=module_obj.name,
            selection_reason=selection_reason,
            correct_answer=correct_answer,
            success=True,
        ), pending

    def store_pending_quiz(self, pending: PendingQuiz) -> None:
        """Store a pending quiz for later evaluation.

        Args:
            pending: The pending quiz to store
        """
        self._pending_quizzes[pending.user_id] = pending

    def get_pending_quiz(self, user_id: int) -> Optional[PendingQuiz]:
        """Get a pending quiz for a user.

        Args:
            user_id: Discord user ID

        Returns:
            PendingQuiz if exists and not expired, None otherwise
        """
        if user_id not in self._pending_quizzes:
            return None

        pending = self._pending_quizzes[user_id]

        # Check if quiz has expired
        if datetime.now() - pending.created_at > self._quiz_timeout:
            del self._pending_quizzes[user_id]
            return None

        return pending

    def remove_pending_quiz(self, user_id: int) -> None:
        """Remove a pending quiz for a user.

        Args:
            user_id: Discord user ID
        """
        if user_id in self._pending_quizzes:
            del self._pending_quizzes[user_id]

    async def evaluate_answer(
        self,
        pending: PendingQuiz,
        student_answer: str,
    ) -> EvaluationResult:
        """Evaluate a student's quiz answer.

        Args:
            pending: The pending quiz
            student_answer: The student's answer

        Returns:
            EvaluationResult with feedback and scores
        """
        # Build evaluation prompt
        eval_prompt = PromptTemplates.get_evaluation_prompt(
            question=pending.question,
            student_answer=student_answer,
            concept_name=pending.concept_name,
            concept_description=pending.concept_description,
            correct_answer=pending.correct_answer or "",
        )

        response = await self.llm_manager.generate(
            prompt=eval_prompt,
            max_tokens=self.config.llm.max_tokens,
            temperature=TEMPERATURE_EVALUATION,
        )

        if not response:
            return EvaluationResult(
                is_pass=False,
                is_partial=False,
                quality_score=0,
                feedback="",
                success=False,
                error_message=self.llm_manager.get_error_message(),
            )

        # Parse evaluation response
        result = self._parse_evaluation_response(response.content)

        # For mastery: count PASS and PARTIAL as correct
        counts_as_correct = result.is_pass or result.is_partial

        # Log quiz attempt
        await self.repository.log_quiz_attempt(
            user_id=pending.db_user_id,
            module_id=pending.module_id,
            concept_id=pending.concept_id,
            quiz_format=pending.quiz_format,
            question=pending.question,
            user_answer=student_answer,
            correct_answer=pending.correct_answer,
            is_correct=counts_as_correct,
            llm_feedback=result.feedback,
            llm_quality_score=result.quality_score if result.quality_score > 0 else None,
        )

        # Update mastery
        await self._update_mastery(
            pending.db_user_id,
            pending.concept_id,
            counts_as_correct,
            result.quality_score,
        )

        return result

    async def _select_concept_by_mastery(self, user_id: int, module) -> tuple:
        """Select a concept based on mastery level.

        Priority:
        1. Concepts not yet attempted (novice with 0 attempts)
        2. Concepts with low mastery (learning, novice)
        3. Concepts needing reinforcement (proficient)
        4. Random from mastered (for review)

        Args:
            user_id: Database user ID
            module: Module object

        Returns:
            Tuple of (concept, selection_reason)
        """
        if not module.concepts:
            return None, ""

        # Get mastery for all concepts in this module
        concept_scores = []
        for concept in module.concepts:
            mastery = await self.repository.get_or_create_mastery(user_id, concept.id)

            # Calculate priority score (lower = higher priority for quizzing)
            if mastery.total_attempts == 0:
                score = 0  # Highest priority: never attempted
                reason = "New concept"
            elif mastery.mastery_level == "novice":
                score = 1
                reason = "Needs practice"
            elif mastery.mastery_level == "learning":
                score = 2
                reason = "Building understanding"
            elif mastery.mastery_level == "proficient":
                score = 3
                reason = "Reinforcement"
            else:  # mastered
                score = 4
                reason = "Review"

            concept_scores.append((concept, score, mastery.total_attempts, reason))

        # Sort by score (ascending), then by attempts (ascending)
        concept_scores.sort(key=lambda x: (x[1], x[2]))

        # Get concepts with the lowest score
        min_score = concept_scores[0][1]
        candidates = [(c, r) for c, s, _, r in concept_scores if s == min_score]

        # Random selection from candidates
        selected = random.choice(candidates)
        return selected[0], selected[1]

    def _extract_correct_answer(self, text: str, quiz_format: str) -> Optional[str]:
        """Extract the correct answer from the LLM response."""
        patterns = {
            "multiple-choice": r"\[CORRECT:\s*([A-D])\]",
            "short-answer": r"\[EXPECTED:\s*(.+?)\]",
            "true-false": r"\[CORRECT:\s*(True|False)\]",
            "fill-blank": r"\[ANSWER:\s*(.+?)\]",
        }

        pattern = patterns.get(quiz_format)
        if pattern:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()

        return None

    def _clean_question(self, text: str) -> str:
        """Remove answer markers from question text."""
        patterns = [
            r"\[CORRECT:\s*[A-D]\]",
            r"\[CORRECT:\s*(?:True|False)\]",
            r"\[EXPECTED:\s*.+?\]",
            r"\[ANSWER:\s*.+?\]",
        ]
        for pattern in patterns:
            text = re.sub(pattern, "", text, flags=re.IGNORECASE)
        return text.strip()

    def _parse_evaluation_response(self, eval_text: str) -> EvaluationResult:
        """Parse LLM evaluation response.

        Args:
            eval_text: Raw evaluation text from LLM

        Returns:
            EvaluationResult with parsed values
        """
        lines = eval_text.strip().split("\n")

        is_pass = False
        is_partial = False
        quality_score = 0
        feedback = eval_text

        if lines:
            first_line = lines[0].upper().strip()
            if first_line == "PASS":
                is_pass = True
            elif first_line == "PARTIAL":
                is_partial = True

            # Try to get quality score from second line
            if len(lines) > 1:
                try:
                    quality_score = int(lines[1].strip())
                    quality_score = max(1, min(5, quality_score))  # Clamp 1-5
                    # Feedback starts from line 3
                    feedback = "\n".join(lines[2:]).strip()
                except ValueError:
                    # No quality score, feedback starts from line 2
                    feedback = "\n".join(lines[1:]).strip()

        return EvaluationResult(
            is_pass=is_pass,
            is_partial=is_partial,
            quality_score=quality_score,
            feedback=feedback,
            success=True,
        )

    async def _update_mastery(
        self,
        user_id: int,
        concept_id: str,
        is_correct: bool,
        quality_score: int,
    ):
        """Update concept mastery after a quiz attempt."""
        # Get current mastery
        mastery = await self.repository.get_or_create_mastery(user_id, concept_id)

        # Update counts
        new_total = mastery.total_attempts + 1
        new_correct = mastery.correct_attempts + (1 if is_correct else 0)

        # Update average quality score
        if quality_score > 0:
            if mastery.avg_quality_score > 0:
                new_avg = (
                    mastery.avg_quality_score * mastery.total_attempts + quality_score
                ) / new_total
            else:
                new_avg = float(quality_score)
        else:
            new_avg = mastery.avg_quality_score

        # Calculate new mastery level using the calculator
        new_level = self._mastery_calculator.calculate_level(
            new_total, new_correct, new_avg
        )

        # Update database
        await self.repository.update_mastery(
            user_id=user_id,
            concept_id=concept_id,
            total_attempts=new_total,
            correct_attempts=new_correct,
            avg_quality_score=new_avg,
            mastery_level=new_level.value,  # Convert enum to string for DB
        )
