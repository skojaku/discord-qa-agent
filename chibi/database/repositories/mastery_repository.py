"""Mastery repository for concept mastery database operations."""

from typing import Dict, List

from ..mappers import row_to_concept_mastery
from ..models import ConceptMastery
from .base import BaseRepository


class MasteryRepository(BaseRepository):
    """Repository for concept mastery operations."""

    async def get_or_create(self, user_id: int, concept_id: str) -> ConceptMastery:
        """Get or create concept mastery record."""
        conn = self.connection
        cursor = await conn.execute(
            "SELECT * FROM concept_mastery WHERE user_id = ? AND concept_id = ?",
            (user_id, concept_id),
        )
        row = await cursor.fetchone()

        if row:
            return row_to_concept_mastery(row)

        # Create new mastery record
        cursor = await conn.execute(
            "INSERT INTO concept_mastery (user_id, concept_id) VALUES (?, ?)",
            (user_id, concept_id),
        )
        await conn.commit()

        return ConceptMastery(
            id=cursor.lastrowid,
            user_id=user_id,
            concept_id=concept_id,
        )

    async def update(
        self,
        user_id: int,
        concept_id: str,
        total_attempts: int,
        correct_attempts: int,
        avg_quality_score: float,
        mastery_level: str,
    ) -> None:
        """Update or insert concept mastery record."""
        conn = self.connection
        await conn.execute(
            """INSERT INTO concept_mastery
               (user_id, concept_id, total_attempts, correct_attempts,
                avg_quality_score, mastery_level, last_attempt_at)
               VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
               ON CONFLICT(user_id, concept_id) DO UPDATE SET
                   total_attempts = excluded.total_attempts,
                   correct_attempts = excluded.correct_attempts,
                   avg_quality_score = excluded.avg_quality_score,
                   mastery_level = excluded.mastery_level,
                   last_attempt_at = CURRENT_TIMESTAMP,
                   updated_at = CURRENT_TIMESTAMP""",
            (
                user_id,
                concept_id,
                total_attempts,
                correct_attempts,
                avg_quality_score,
                mastery_level,
            ),
        )
        await conn.commit()

    async def get_all_for_user(self, user_id: int) -> List[ConceptMastery]:
        """Get all concept mastery records for a user."""
        conn = self.connection
        cursor = await conn.execute(
            "SELECT * FROM concept_mastery WHERE user_id = ? ORDER BY concept_id",
            (user_id,),
        )
        rows = await cursor.fetchall()

        return [row_to_concept_mastery(row) for row in rows]

    async def get_summary(self, user_id: int) -> Dict[str, int]:
        """Get summary of user's mastery progress by level."""
        conn = self.connection

        # Get counts by mastery level
        cursor = await conn.execute(
            """SELECT mastery_level, COUNT(*) as count
               FROM concept_mastery
               WHERE user_id = ?
               GROUP BY mastery_level""",
            (user_id,),
        )
        rows = await cursor.fetchall()

        summary = {
            "novice": 0,
            "learning": 0,
            "proficient": 0,
            "mastered": 0,
        }
        for row in rows:
            if row["mastery_level"] in summary:
                summary[row["mastery_level"]] = row["count"]

        return summary

    async def get_all(self) -> List[ConceptMastery]:
        """Get all concept mastery records for all users."""
        conn = self.connection
        cursor = await conn.execute(
            "SELECT * FROM concept_mastery ORDER BY user_id, concept_id"
        )
        rows = await cursor.fetchall()

        return [row_to_concept_mastery(row) for row in rows]

    async def get_by_concepts(
        self, user_id: int, concept_ids: List[str]
    ) -> List[ConceptMastery]:
        """Get mastery records for specific concepts.

        Args:
            user_id: The user's database ID
            concept_ids: List of concept IDs to filter by

        Returns:
            List of ConceptMastery records for the specified concepts
        """
        if not concept_ids:
            return []

        conn = self.connection
        placeholders = ",".join("?" * len(concept_ids))
        cursor = await conn.execute(
            f"""SELECT * FROM concept_mastery
               WHERE user_id = ? AND concept_id IN ({placeholders})
               ORDER BY concept_id""",
            (user_id, *concept_ids),
        )
        rows = await cursor.fetchall()

        return [row_to_concept_mastery(row) for row in rows]
