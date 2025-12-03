"""Guidance service for generating grading guidance to help students achieve full grades."""

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, TYPE_CHECKING

from ..constants import (
    MASTERY_MASTERED,
    MASTERY_NOVICE,
    MASTERY_PROFICIENT,
    MASTERY_LEARNING,
    MASTERY_RATIO_MASTERED,
    MASTERY_RATIO_PROFICIENT,
    MASTERY_QUALITY_MASTERED,
)

if TYPE_CHECKING:
    from ..content.course import Concept, Course, Module
    from ..database.models import ConceptMastery
    from ..database.repositories import MasteryRepository
    from ..services.llm_quiz_service import LLMQuizChallengeService


@dataclass
class ConceptGuidance:
    """Guidance for a single concept."""

    concept_id: str
    concept_name: str
    current_level: str
    current_attempts: int
    current_correct: int
    current_accuracy: float
    current_quality: float
    is_complete: bool  # Already proficient or mastered
    needs_attempts: int  # Additional attempts needed
    needs_correct: int  # Additional correct answers needed for proficient
    needs_quality_improvement: bool  # Quality score needs improvement
    guidance_text: str  # Actionable guidance message


@dataclass
class LLMQuizGuidance:
    """Guidance for LLM Quiz Challenge."""

    module_id: str
    module_name: str
    current_wins: int
    target_wins: int
    is_complete: bool
    wins_needed: int
    guidance_text: str


@dataclass
class ModuleGuidance:
    """Complete guidance for a module."""

    module_id: str
    module_name: str
    completion_percentage: float
    concepts_complete: int
    concepts_total: int
    concept_guidance: List[ConceptGuidance]
    llm_quiz_guidance: Optional[LLMQuizGuidance]
    summary: str  # Overall guidance summary


@dataclass
class GradingGuidance:
    """Complete grading guidance for a student."""

    user_id: int
    overall_completion: float
    modules: List[ModuleGuidance]
    priority_actions: List[str]  # Top priority actions to take


class GuidanceService:
    """Service for generating personalized grading guidance."""

    def __init__(
        self,
        mastery_repo: "MasteryRepository",
        llm_quiz_service: "LLMQuizChallengeService",
        course: "Course",
        min_attempts: int = 3,
    ):
        self.mastery_repo = mastery_repo
        self.llm_quiz_service = llm_quiz_service
        self.course = course
        self.min_attempts = min_attempts

    async def get_guidance(
        self,
        user_id: int,
        module_id: Optional[str] = None,
    ) -> GradingGuidance:
        """Generate comprehensive grading guidance for a student.

        Args:
            user_id: Database user ID
            module_id: Optional specific module to get guidance for

        Returns:
            GradingGuidance with detailed recommendations
        """
        # Get all mastery records for the user
        mastery_records = await self.mastery_repo.get_all_for_user(user_id)
        mastery_by_concept: Dict[str, "ConceptMastery"] = {
            m.concept_id: m for m in mastery_records
        }

        # Get LLM Quiz progress
        llm_quiz_progress = await self.llm_quiz_service.get_all_progress(user_id)

        # Determine which modules to analyze
        if module_id:
            target_module = self.course.get_module(module_id)
            modules_to_analyze = [target_module] if target_module else []
        else:
            modules_to_analyze = self.course.modules

        # Generate guidance for each module
        module_guidance_list: List[ModuleGuidance] = []
        total_complete = 0
        total_concepts = 0
        priority_actions: List[str] = []

        for module in modules_to_analyze:
            module_guidance = await self._generate_module_guidance(
                module, mastery_by_concept, llm_quiz_progress
            )
            module_guidance_list.append(module_guidance)
            total_complete += module_guidance.concepts_complete
            total_concepts += module_guidance.concepts_total

            # Collect priority actions from incomplete concepts
            for cg in module_guidance.concept_guidance:
                if not cg.is_complete:
                    priority_actions.append(
                        f"[{module.name}] {cg.concept_name}: {cg.guidance_text}"
                    )

            # Add LLM Quiz as priority if not complete
            if (
                module_guidance.llm_quiz_guidance
                and not module_guidance.llm_quiz_guidance.is_complete
            ):
                priority_actions.append(
                    f"[{module.name}] LLM Quiz: {module_guidance.llm_quiz_guidance.guidance_text}"
                )

        overall_completion = (
            (total_complete / total_concepts * 100) if total_concepts > 0 else 0.0
        )

        # Limit priority actions to top 5
        priority_actions = priority_actions[:5]

        return GradingGuidance(
            user_id=user_id,
            overall_completion=overall_completion,
            modules=module_guidance_list,
            priority_actions=priority_actions,
        )

    async def _generate_module_guidance(
        self,
        module: "Module",
        mastery_by_concept: Dict[str, "ConceptMastery"],
        llm_quiz_progress: Dict[str, Tuple[int, int]],
    ) -> ModuleGuidance:
        """Generate guidance for a single module."""
        concept_guidance_list: List[ConceptGuidance] = []
        concepts_complete = 0

        for concept in module.concepts:
            cg = self._generate_concept_guidance(concept, mastery_by_concept)
            concept_guidance_list.append(cg)
            if cg.is_complete:
                concepts_complete += 1

        # Generate LLM Quiz guidance
        llm_guidance = self._generate_llm_quiz_guidance(
            module.id, module.name, llm_quiz_progress
        )

        completion_pct = (
            (concepts_complete / len(module.concepts) * 100)
            if module.concepts
            else 100.0
        )

        # Generate summary
        summary = self._generate_module_summary(
            module.name,
            concepts_complete,
            len(module.concepts),
            concept_guidance_list,
            llm_guidance,
        )

        return ModuleGuidance(
            module_id=module.id,
            module_name=module.name,
            completion_percentage=completion_pct,
            concepts_complete=concepts_complete,
            concepts_total=len(module.concepts),
            concept_guidance=concept_guidance_list,
            llm_quiz_guidance=llm_guidance,
            summary=summary,
        )

    def _generate_concept_guidance(
        self,
        concept: "Concept",
        mastery_by_concept: Dict[str, "ConceptMastery"],
    ) -> ConceptGuidance:
        """Generate guidance for a single concept."""
        mastery = mastery_by_concept.get(concept.id)

        if mastery is None:
            # Not started yet
            return ConceptGuidance(
                concept_id=concept.id,
                concept_name=concept.name,
                current_level=MASTERY_NOVICE,
                current_attempts=0,
                current_correct=0,
                current_accuracy=0.0,
                current_quality=0.0,
                is_complete=False,
                needs_attempts=self.min_attempts,
                needs_correct=math.ceil(self.min_attempts * MASTERY_RATIO_PROFICIENT),
                needs_quality_improvement=False,
                guidance_text=f"Start practicing! Complete at least {self.min_attempts} quizzes with 60%+ accuracy.",
            )

        current_level = mastery.mastery_level or MASTERY_NOVICE
        total_attempts = mastery.total_attempts
        correct_attempts = mastery.correct_attempts
        accuracy = correct_attempts / total_attempts if total_attempts > 0 else 0.0
        quality = mastery.avg_quality_score or 0.0

        is_complete = current_level in (MASTERY_PROFICIENT, MASTERY_MASTERED)

        if is_complete:
            return ConceptGuidance(
                concept_id=concept.id,
                concept_name=concept.name,
                current_level=current_level,
                current_attempts=total_attempts,
                current_correct=correct_attempts,
                current_accuracy=accuracy * 100,
                current_quality=quality,
                is_complete=True,
                needs_attempts=0,
                needs_correct=0,
                needs_quality_improvement=False,
                guidance_text="Complete! Great job!",
            )

        # Calculate what's needed to reach proficient
        needs_attempts, needs_correct, guidance_text = self._calculate_requirements(
            total_attempts, correct_attempts, accuracy, quality
        )

        needs_quality_improvement = (
            accuracy >= MASTERY_RATIO_MASTERED
            and quality < MASTERY_QUALITY_MASTERED
            and quality > 0
        )

        return ConceptGuidance(
            concept_id=concept.id,
            concept_name=concept.name,
            current_level=current_level,
            current_attempts=total_attempts,
            current_correct=correct_attempts,
            current_accuracy=accuracy * 100,
            current_quality=quality,
            is_complete=False,
            needs_attempts=needs_attempts,
            needs_correct=needs_correct,
            needs_quality_improvement=needs_quality_improvement,
            guidance_text=guidance_text,
        )

    def _calculate_requirements(
        self,
        total_attempts: int,
        correct_attempts: int,
        current_accuracy: float,
        current_quality: float,
    ) -> Tuple[int, int, str]:
        """Calculate what's needed to reach proficient level.

        Returns:
            Tuple of (additional_attempts_needed, additional_correct_needed, guidance_text)
        """
        # If not enough attempts yet
        if total_attempts < self.min_attempts:
            attempts_needed = self.min_attempts - total_attempts
            # Calculate correct answers needed for 60% accuracy at min_attempts
            target_correct = math.ceil(self.min_attempts * MASTERY_RATIO_PROFICIENT)
            correct_needed = max(0, target_correct - correct_attempts)

            if correct_needed > attempts_needed:
                # Need more correct answers than remaining attempts
                guidance = (
                    f"Complete {attempts_needed} more quiz(zes). "
                    f"Need {correct_needed} correct to reach 60% accuracy."
                )
            else:
                guidance = (
                    f"Complete {attempts_needed} more quiz(zes) with good answers. "
                    f"Current: {correct_attempts}/{total_attempts} correct."
                )

            return attempts_needed, correct_needed, guidance

        # Have minimum attempts but accuracy too low
        if current_accuracy < MASTERY_RATIO_PROFICIENT:
            # Calculate how many more correct answers needed
            # For ratio >= 0.6: correct / total >= 0.6
            # If we add N more correct answers: (correct + N) / (total + N) >= 0.6
            # Solving: N >= (0.6 * total - correct) / 0.4

            deficit = MASTERY_RATIO_PROFICIENT * total_attempts - correct_attempts
            if deficit > 0:
                # Need consecutive correct answers
                additional_correct = math.ceil(deficit / (1 - MASTERY_RATIO_PROFICIENT))
                guidance = (
                    f"Answer {additional_correct} more quiz(zes) correctly in a row "
                    f"to reach 60% accuracy. Current: {current_accuracy*100:.0f}%"
                )
                return additional_correct, additional_correct, guidance

        # Have good accuracy, check quality for mastered
        if current_accuracy >= MASTERY_RATIO_MASTERED:
            if current_quality < MASTERY_QUALITY_MASTERED and current_quality > 0:
                guidance = (
                    f"Accuracy is great ({current_accuracy*100:.0f}%)! "
                    f"Improve answer quality (current: {current_quality:.1f}/5.0, need: 4.0+) "
                    f"for mastered level."
                )
                return 1, 1, guidance

        # Should be proficient but isn't (edge case)
        guidance = (
            f"Keep practicing! Current: {total_attempts} attempts, "
            f"{current_accuracy*100:.0f}% accuracy."
        )
        return 1, 1, guidance

    def _generate_llm_quiz_guidance(
        self,
        module_id: str,
        module_name: str,
        llm_quiz_progress: Dict[str, Tuple[int, int]],
    ) -> LLMQuizGuidance:
        """Generate guidance for LLM Quiz Challenge."""
        if module_id in llm_quiz_progress:
            wins, target = llm_quiz_progress[module_id]
        else:
            wins = 0
            target = self.llm_quiz_service.target_wins_per_module

        is_complete = wins >= target
        wins_needed = max(0, target - wins)

        if is_complete:
            guidance_text = "Complete! You've successfully challenged the AI."
        elif wins == 0:
            guidance_text = (
                f"Start the LLM Quiz Challenge! Stump the AI {target} times "
                f"with tricky questions to complete this requirement."
            )
        else:
            guidance_text = (
                f"Win {wins_needed} more LLM Quiz Challenge(s). "
                f"Progress: {wins}/{target} wins."
            )

        return LLMQuizGuidance(
            module_id=module_id,
            module_name=module_name,
            current_wins=wins,
            target_wins=target,
            is_complete=is_complete,
            wins_needed=wins_needed,
            guidance_text=guidance_text,
        )

    def _generate_module_summary(
        self,
        module_name: str,
        concepts_complete: int,
        concepts_total: int,
        concept_guidance: List[ConceptGuidance],
        llm_guidance: Optional[LLMQuizGuidance],
    ) -> str:
        """Generate a summary of what's needed for full module completion."""
        parts = []

        if concepts_complete == concepts_total:
            parts.append(f"All {concepts_total} concepts mastered!")
        else:
            incomplete = concepts_total - concepts_complete
            parts.append(f"{incomplete} concept(s) need more practice.")

            # Find the easiest wins (closest to completion)
            incomplete_concepts = [cg for cg in concept_guidance if not cg.is_complete]
            if incomplete_concepts:
                # Sort by needs_correct (ascending)
                incomplete_concepts.sort(key=lambda x: x.needs_correct)
                closest = incomplete_concepts[0]
                parts.append(
                    f"Focus on '{closest.concept_name}' - "
                    f"only {closest.needs_correct} more correct answer(s) needed."
                )

        if llm_guidance and not llm_guidance.is_complete:
            parts.append(f"LLM Quiz: {llm_guidance.wins_needed} more win(s) needed.")
        elif llm_guidance and llm_guidance.is_complete:
            parts.append("LLM Quiz: Complete!")

        return " ".join(parts)
