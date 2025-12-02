"""Grade service for generating grade reports."""

import csv
import io
from typing import Optional, TYPE_CHECKING

from ..constants import MASTERY_MASTERED, MASTERY_PROFICIENT

if TYPE_CHECKING:
    from ..content.course import Course, Module
    from ..database.repositories import MasteryRepository, UserRepository


class GradeService:
    """Service for grade calculations and CSV generation."""

    def __init__(
        self,
        user_repo: "UserRepository",
        mastery_repo: "MasteryRepository",
        course: "Course",
    ):
        self.user_repo = user_repo
        self.mastery_repo = mastery_repo
        self.course = course

    async def generate_grade_csv(
        self, target_module: Optional["Module"] = None
    ) -> str:
        """Generate CSV content with student grades in tidy format.

        Args:
            target_module: If specified, only include data for this module

        Returns:
            CSV content as a string (one row per user-module combination)
        """
        users = await self.user_repo.get_all()

        if target_module:
            modules = [target_module]
        else:
            modules = self.course.modules

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["discord_id", "username", "module", "completion_pct"])

        for user in users:
            mastery_records = await self.mastery_repo.get_all_for_user(user.id)
            mastery_by_concept = {m.concept_id: m for m in mastery_records}

            for mod in modules:
                module_concepts = mod.concepts

                # Count completed concepts (proficient or mastered)
                completed_count = sum(
                    1
                    for concept in module_concepts
                    if mastery_by_concept.get(concept.id)
                    and mastery_by_concept[concept.id].mastery_level
                    in (MASTERY_PROFICIENT, MASTERY_MASTERED)
                )

                # Calculate completion percentage
                completion_pct = (
                    (completed_count / len(module_concepts) * 100)
                    if module_concepts
                    else 0
                )

                writer.writerow(
                    [
                        user.discord_id,
                        user.username,
                        mod.id,
                        f"{completion_pct:.1f}",
                    ]
                )

        return output.getvalue()
