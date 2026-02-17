"""Grade service for generating grade reports."""

from typing import Any, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..content.course import Course, Module
    from ..database.repositories import (
        LLMQuizRepository,
        MasteryRepository,
        UserRepository,
    )


class GradeService:
    """Service for grade calculations and sheet data generation."""

    def __init__(
        self,
        user_repo: "UserRepository",
        mastery_repo: "MasteryRepository",
        course: "Course",
        llm_quiz_repo: "LLMQuizRepository",
        llm_quiz_target_wins: int,
        min_attempts: int,
    ):
        self.user_repo = user_repo
        self.mastery_repo = mastery_repo
        self.course = course
        self.llm_quiz_repo = llm_quiz_repo
        self.llm_quiz_target_wins = llm_quiz_target_wins
        self.min_attempts = min_attempts

    async def generate_grade_sheet_data(
        self, target_module: Optional["Module"] = None
    ) -> List[List[Any]]:
        """Generate grade data as list of lists for Google Sheets export.

        Each row represents one student-module pair with quiz and LLM quiz progress.

        Args:
            target_module: If specified, only include data for this module

        Returns:
            List of lists: header row followed by data rows
        """
        users = await self.user_repo.get_all()

        if target_module:
            modules = [target_module]
        else:
            modules = self.course.modules

        header = [
            "discord_id",
            "username",
            "student_id",
            "student_name",
            "module",
            "quiz_progress",
            "quiz_complete",
            "llm_quiz_progress",
            "llm_quiz_complete",
        ]
        rows: List[List[Any]] = [header]

        for user in users:
            mastery_records = await self.mastery_repo.get_all_for_user(user.id)
            mastery_by_concept = {m.concept_id: m for m in mastery_records}

            for mod in modules:
                module_concepts = mod.concepts

                # Quiz progress: count correct attempts capped at min_attempts per concept
                total_correct_capped = sum(
                    min(mastery_by_concept[concept.id].correct_attempts, self.min_attempts)
                    for concept in module_concepts
                    if mastery_by_concept.get(concept.id)
                )
                total_required = len(module_concepts) * self.min_attempts
                quiz_progress = (
                    (total_correct_capped / total_required * 100)
                    if total_required > 0
                    else 0
                )
                quiz_complete = quiz_progress >= 100

                # LLM quiz progress
                approved_wins = await self.llm_quiz_repo.count_wins_for_module(
                    user.id, mod.id
                )
                llm_quiz_progress = min(
                    approved_wins / self.llm_quiz_target_wins * 100
                    if self.llm_quiz_target_wins > 0
                    else 0,
                    100,
                )
                llm_quiz_complete = approved_wins >= self.llm_quiz_target_wins

                rows.append([
                    user.discord_id,
                    user.username,
                    getattr(user, "student_id", ""),
                    getattr(user, "student_name", ""),
                    mod.id,
                    f"{quiz_progress:.1f}",
                    str(quiz_complete).upper(),
                    f"{llm_quiz_progress:.1f}",
                    str(llm_quiz_complete).upper(),
                ])

        return rows
