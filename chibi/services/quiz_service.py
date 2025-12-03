"""Quiz service for quiz generation and evaluation logic."""

import logging
import random
import re
from dataclasses import dataclass
from typing import Optional, Tuple, TYPE_CHECKING

from ..constants import TEMPERATURE_EVALUATION, TEMPERATURE_QUIZ_GENERATION
from ..learning.mastery import MasteryCalculator
from ..prompts.templates import PromptTemplates

if TYPE_CHECKING:
    from ..content.course import Concept, Module
    from ..database.repositories import MasteryRepository, QuizRepository
    from ..llm.manager import LLMManager

logger = logging.getLogger(__name__)


@dataclass
class EvaluationResult:
    """Result of evaluating a quiz answer."""

    is_correct: bool
    is_partial: bool
    quality_score: int
    feedback: str
    counts_as_correct: bool  # For mastery calculation


class QuizService:
    """Service for quiz generation and evaluation."""

    def __init__(
        self,
        mastery_repo: "MasteryRepository",
        quiz_repo: "QuizRepository",
        llm_manager: "LLMManager",
        mastery_calculator: MasteryCalculator,
        max_tokens: int = 1000,
    ):
        self.mastery_repo = mastery_repo
        self.quiz_repo = quiz_repo
        self.llm_manager = llm_manager
        self.mastery_calculator = mastery_calculator
        self.max_tokens = max_tokens

    async def select_concept_by_mastery(
        self, user_id: int, module: "Module"
    ) -> Tuple[Optional["Concept"], str]:
        """Select a concept based on mastery level.

        Priority:
        1. Concepts not yet attempted (novice with 0 attempts)
        2. Concepts with low mastery (learning, novice)
        3. Concepts needing reinforcement (proficient)
        4. Random from mastered (for review)

        Returns:
            Tuple of (concept, selection_reason)
        """
        if not module.concepts:
            return None, ""

        # Get mastery for all concepts in this module
        concept_scores = []
        for concept in module.concepts:
            mastery = await self.mastery_repo.get_or_create(user_id, concept.id)

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

    async def generate_question(
        self, concept: "Concept", module: "Module", context: Optional[str] = None
    ) -> Optional[Tuple[str, Optional[str]]]:
        """Generate a quiz question for a concept.

        Args:
            concept: The concept to quiz on
            module: The module containing the concept
            context: Optional RAG-retrieved context (overrides module.content)

        Returns:
            Tuple of (question_text, correct_answer) or None if generation fails
        """
        quiz_format = "free-form"

        # Use RAG context if provided, otherwise fall back to module content
        module_content = context if context else (module.content or "")

        quiz_prompt = PromptTemplates.get_quiz_prompt(
            concept_name=concept.name,
            concept_description=concept.description,
            quiz_focus=concept.quiz_focus,
            quiz_format=quiz_format,
            module_content=module_content,
        )

        response = await self.llm_manager.generate(
            prompt=quiz_prompt,
            max_tokens=self.max_tokens,
            temperature=TEMPERATURE_QUIZ_GENERATION,
        )

        if not response:
            return None

        question_text = response.content
        logger.debug(f"Raw LLM question response: {question_text[:200] if question_text else 'EMPTY'}...")
        correct_answer = self._extract_correct_answer(question_text, quiz_format)
        question_text = self._clean_question(question_text)
        logger.debug(f"Cleaned question text: {question_text[:200] if question_text else 'EMPTY'}...")

        return question_text, correct_answer

    async def evaluate_answer(
        self,
        question: str,
        student_answer: str,
        concept_name: str,
        concept_description: str,
        correct_answer: Optional[str] = None,
        context: Optional[str] = None,
    ) -> Optional[EvaluationResult]:
        """Evaluate a student's answer.

        Args:
            question: The quiz question
            student_answer: The student's answer
            concept_name: Name of the concept being tested
            concept_description: Description of the concept
            correct_answer: Expected correct answer (if available)
            context: Optional RAG-retrieved context for evaluation

        Returns:
            EvaluationResult or None if evaluation fails
        """
        # Build concept description with context if available
        enhanced_description = concept_description
        if context:
            enhanced_description = f"{concept_description}\n\nRelevant context:\n{context}"

        eval_prompt = PromptTemplates.get_evaluation_prompt(
            question=question,
            student_answer=student_answer,
            concept_name=concept_name,
            concept_description=enhanced_description,
            correct_answer=correct_answer or "",
        )

        response = await self.llm_manager.generate(
            prompt=eval_prompt,
            max_tokens=self.max_tokens,
            temperature=TEMPERATURE_EVALUATION,
        )

        if not response:
            return None

        return self._parse_evaluation_response(response.content)

    def _parse_evaluation_response(self, eval_text: str) -> EvaluationResult:
        """Parse the LLM evaluation response.

        Expected format:
        Line 1: PASS, PARTIAL, or FAIL
        Line 2: Score (1-5)
        Line 3+: Feedback

        Also handles variations where score/feedback may be on same line.
        """
        logger.debug(f"Parsing evaluation response: {eval_text[:200]}...")

        lines = [line.strip() for line in eval_text.strip().split("\n") if line.strip()]

        is_correct = False
        is_partial = False
        quality_score = 1  # Default to 1
        feedback = ""

        if not lines:
            logger.warning("Empty evaluation response")
            return EvaluationResult(
                is_correct=False,
                is_partial=False,
                quality_score=1,
                feedback="❌ Unable to evaluate your answer. Please try again.",
                counts_as_correct=False,
            )

        # Parse first line for verdict
        first_line = lines[0].upper()
        if "PASS" in first_line:
            is_correct = True
        elif "PARTIAL" in first_line:
            is_partial = True

        # Try to extract score using regex (handles "2" or "Score: 2" or "2/5")
        score_match = re.search(r'\b([1-5])\b', eval_text[:100])  # Look in first 100 chars
        if score_match:
            quality_score = int(score_match.group(1))

        # Extract feedback - everything after verdict and score
        # Look for emoji-prefixed feedback or just take remaining content
        feedback_patterns = [
            r'[✅🔶❌]\s*(.+)',  # Emoji-prefixed feedback
            r'(?:PASS|PARTIAL|FAIL)\s*\n\s*\d\s*\n\s*(.+)',  # Standard format
        ]

        for pattern in feedback_patterns:
            match = re.search(pattern, eval_text, re.DOTALL | re.IGNORECASE)
            if match:
                feedback = match.group(1).strip()
                break

        # If no pattern matched, try to get feedback from line 3 onwards
        if not feedback and len(lines) > 2:
            feedback = "\n".join(lines[2:]).strip()

        # If still no feedback, use everything except first line
        if not feedback and len(lines) > 1:
            # Skip the verdict line and any line that's just a number
            remaining = []
            for line in lines[1:]:
                if not re.match(r'^\d$', line):  # Skip single digit lines (score)
                    remaining.append(line)
            feedback = "\n".join(remaining).strip()

        # Final fallback
        if not feedback:
            logger.warning("Could not extract feedback from evaluation response")
            if is_correct:
                feedback = "✅ Good job! Your answer demonstrates understanding of the concept."
            elif is_partial:
                feedback = "🔶 Your answer shows some understanding but could be more complete."
            else:
                feedback = "❌ Your answer needs improvement. Please review the concept and try again."

        logger.debug(f"Parsed: correct={is_correct}, partial={is_partial}, score={quality_score}")

        return EvaluationResult(
            is_correct=is_correct,
            is_partial=is_partial,
            quality_score=quality_score,
            feedback=feedback,
            counts_as_correct=is_correct or is_partial,
        )

    async def log_attempt_and_update_mastery(
        self,
        user_id: int,
        module_id: str,
        concept_id: str,
        question: str,
        user_answer: str,
        correct_answer: Optional[str],
        result: EvaluationResult,
    ) -> None:
        """Log quiz attempt and update mastery level."""
        # Log the attempt
        await self.quiz_repo.log_attempt(
            user_id=user_id,
            module_id=module_id,
            concept_id=concept_id,
            quiz_format="free-form",
            question=question,
            user_answer=user_answer,
            correct_answer=correct_answer,
            is_correct=result.counts_as_correct,
            llm_feedback=result.feedback,
            llm_quality_score=result.quality_score if result.quality_score > 0 else None,
        )

        # Update mastery
        await self._update_mastery(
            user_id, concept_id, result.counts_as_correct, result.quality_score
        )

    async def _update_mastery(
        self,
        user_id: int,
        concept_id: str,
        is_correct: bool,
        quality_score: int,
    ) -> None:
        """Update concept mastery after a quiz attempt."""
        mastery = await self.mastery_repo.get_or_create(user_id, concept_id)

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

        # Calculate new mastery level
        new_level = self.mastery_calculator.calculate_level(
            new_total, new_correct, new_avg
        )

        # Update database
        await self.mastery_repo.update(
            user_id=user_id,
            concept_id=concept_id,
            total_attempts=new_total,
            correct_attempts=new_correct,
            avg_quality_score=new_avg,
            mastery_level=new_level.value,
        )

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
        """Remove answer markers and prefixes from question text."""
        patterns = [
            r"\[CORRECT:\s*[A-D]\]",
            r"\[CORRECT:\s*(?:True|False)\]",
            r"\[EXPECTED:\s*.+?\]",
            r"\[ANSWER:\s*.+?\]",
        ]
        for pattern in patterns:
            text = re.sub(pattern, "", text, flags=re.IGNORECASE)

        # Remove "Question:" prefix if LLM added it
        text = re.sub(r"^Question:\s*", "", text.strip(), flags=re.IGNORECASE)

        return text.strip()
