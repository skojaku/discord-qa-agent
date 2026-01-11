"""SQLite to Google Sheets exporter.

This module provides functionality to export student progress data from SQLite
database to Google Sheets format with proper data type conversions.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List

from chibi.database.connection import Database
from chibi.backup.google_sheets_client import GoogleSheetsClient

logger = logging.getLogger(__name__)


class SheetsExporter:
    """Exports SQLite student progress data to Google Sheets."""

    def __init__(self, database: Database, sheets_client: GoogleSheetsClient):
        """
        Initialize the exporter.

        Args:
            database: Database connection instance
            sheets_client: GoogleSheetsClient for Sheets API operations
        """
        self.database = database
        self.sheets_client = sheets_client

    async def export_to_sheets(self) -> Dict[str, Any]:
        """
        Export all student progress data to a new Google Sheets spreadsheet.

        Returns:
            Dict containing:
                - spreadsheet_id: The created spreadsheet ID
                - url: Spreadsheet URL
                - summary: Dict with row counts for each table

        Raises:
            Exception: If export fails
        """
        # Create spreadsheet with timestamp
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        spreadsheet_title = f"Chibi Student Progress - {timestamp}"

        logger.info(f"Creating spreadsheet: {spreadsheet_title}")
        spreadsheet_id = self.sheets_client.create_spreadsheet(spreadsheet_title)

        # Export all tables
        logger.info("Exporting tables...")
        users_data = await self._export_users_table()
        quiz_attempts_data = await self._export_quiz_attempts_table()
        concept_mastery_data = await self._export_concept_mastery_table()
        llm_quiz_attempts_data = await self._export_llm_quiz_attempts_table()
        attendance_data = await self._export_attendance_table()

        # Create metadata sheet
        metadata_data = self._create_metadata_sheet(
            export_date=timestamp,
            users_count=len(users_data) - 1,  # Subtract header
            quiz_attempts_count=len(quiz_attempts_data) - 1,
            concept_mastery_count=len(concept_mastery_data) - 1,
            llm_quiz_attempts_count=len(llm_quiz_attempts_data) - 1,
            attendance_count=len(attendance_data) - 1,
        )

        # Write all sheets
        logger.info("Writing data to sheets...")
        self.sheets_client.write_sheet(spreadsheet_id, "Metadata", metadata_data)
        self.sheets_client.write_sheet(spreadsheet_id, "Users", users_data)
        self.sheets_client.write_sheet(
            spreadsheet_id, "QuizAttempts", quiz_attempts_data
        )
        self.sheets_client.write_sheet(
            spreadsheet_id, "ConceptMastery", concept_mastery_data
        )
        self.sheets_client.write_sheet(
            spreadsheet_id, "LLMQuizAttempts", llm_quiz_attempts_data
        )
        self.sheets_client.write_sheet(spreadsheet_id, "Attendance", attendance_data)

        # Build result
        spreadsheet_url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}"
        summary = {
            "users": len(users_data) - 1,
            "quiz_attempts": len(quiz_attempts_data) - 1,
            "concept_mastery": len(concept_mastery_data) - 1,
            "llm_quiz_attempts": len(llm_quiz_attempts_data) - 1,
            "attendance": len(attendance_data) - 1,
        }

        logger.info(f"Export complete: {summary}")

        return {
            "spreadsheet_id": spreadsheet_id,
            "url": spreadsheet_url,
            "summary": summary,
        }

    def _create_metadata_sheet(
        self,
        export_date: str,
        users_count: int,
        quiz_attempts_count: int,
        concept_mastery_count: int,
        llm_quiz_attempts_count: int,
        attendance_count: int,
    ) -> List[List[Any]]:
        """
        Create metadata sheet with export information.

        Args:
            export_date: Export timestamp
            users_count: Number of user records
            quiz_attempts_count: Number of quiz attempt records
            concept_mastery_count: Number of concept mastery records
            llm_quiz_attempts_count: Number of LLM quiz attempt records
            attendance_count: Number of attendance records

        Returns:
            List of lists with metadata
        """
        return [
            ["field", "value"],
            ["export_date", export_date],
            ["schema_version", "1.0"],
            ["users_count", str(users_count)],
            ["quiz_attempts_count", str(quiz_attempts_count)],
            ["concept_mastery_count", str(concept_mastery_count)],
            ["llm_quiz_attempts_count", str(llm_quiz_attempts_count)],
            ["attendance_count", str(attendance_count)],
        ]

    async def _export_users_table(self) -> List[List[Any]]:
        """
        Export users table.

        Returns:
            List of lists with header row and data rows
        """
        headers = [
            "id",
            "discord_id",
            "username",
            "student_id",
            "student_name",
            "created_at",
            "last_active",
        ]

        rows = [headers]

        conn = self.database.connection
        async with conn.execute("SELECT * FROM users ORDER BY id") as cursor:
                async for row in cursor:
                    rows.append(self._transform_row(row, headers))

        logger.debug(f"Exported {len(rows) - 1} users")
        return rows

    async def _export_quiz_attempts_table(self) -> List[List[Any]]:
        """
        Export quiz_attempts table.

        Returns:
            List of lists with header row and data rows
        """
        headers = [
            "id",
            "user_id",
            "module_id",
            "concept_id",
            "quiz_format",
            "question",
            "user_answer",
            "correct_answer",
            "is_correct",
            "llm_feedback",
            "llm_quality_score",
            "created_at",
        ]

        rows = [headers]

        conn = self.database.connection
        async with conn.execute(
                "SELECT * FROM quiz_attempts ORDER BY id"
            ) as cursor:
                async for row in cursor:
                    rows.append(self._transform_row(row, headers))

        logger.debug(f"Exported {len(rows) - 1} quiz attempts")
        return rows

    async def _export_concept_mastery_table(self) -> List[List[Any]]:
        """
        Export concept_mastery table.

        Returns:
            List of lists with header row and data rows
        """
        headers = [
            "id",
            "user_id",
            "concept_id",
            "total_attempts",
            "correct_attempts",
            "avg_quality_score",
            "mastery_level",
            "last_attempt_at",
            "updated_at",
        ]

        rows = [headers]

        conn = self.database.connection
        async with conn.execute(
                "SELECT * FROM concept_mastery ORDER BY id"
            ) as cursor:
                async for row in cursor:
                    rows.append(self._transform_row(row, headers))

        logger.debug(f"Exported {len(rows) - 1} concept mastery records")
        return rows

    async def _export_llm_quiz_attempts_table(self) -> List[List[Any]]:
        """
        Export llm_quiz_attempts table.

        Returns:
            List of lists with header row and data rows
        """
        headers = [
            "id",
            "user_id",
            "module_id",
            "question",
            "student_answer",
            "llm_answer",
            "student_wins",
            "student_answer_correctness",
            "evaluation_explanation",
            "review_status",
            "reviewed_at",
            "reviewed_by",
            "discord_user_id",
            "created_at",
        ]

        rows = [headers]

        conn = self.database.connection
        async with conn.execute(
                "SELECT * FROM llm_quiz_attempts ORDER BY id"
            ) as cursor:
                async for row in cursor:
                    rows.append(self._transform_row(row, headers))

        logger.debug(f"Exported {len(rows) - 1} LLM quiz attempts")
        return rows

    async def _export_attendance_table(self) -> List[List[Any]]:
        """
        Export attendance table.

        Returns:
            List of lists with header row and data rows
        """
        headers = [
            "id",
            "user_id",
            "username",
            "timestamp",
            "date_id",
            "session_id",
            "status",
        ]

        rows = [headers]

        conn = self.database.connection
        async with conn.execute("SELECT * FROM attendance ORDER BY id") as cursor:
                async for row in cursor:
                    rows.append(self._transform_row(row, headers))

        logger.debug(f"Exported {len(rows) - 1} attendance records")
        return rows

    def _transform_row(self, row: Dict[str, Any], headers: List[str]) -> List[Any]:
        """
        Transform a SQLite row to Sheets format with type conversions.

        Conversions:
        - None → "" (empty string)
        - 0/1 (boolean) → "FALSE"/"TRUE"
        - Text > 50k chars → truncated to 50k
        - Timestamps → preserved as ISO strings

        Args:
            row: SQLite row as dict
            headers: List of column names in desired order

        Returns:
            List of values in same order as headers
        """
        transformed = []

        for header in headers:
            value = row[header]

            # Convert None to empty string
            if value is None:
                transformed.append("")
            # Convert boolean columns (0/1) to TRUE/FALSE
            elif header in [
                "is_correct",
                "student_wins",
            ] and isinstance(value, int):
                transformed.append("TRUE" if value == 1 else "FALSE")
            # Truncate long text fields to 50k chars
            elif isinstance(value, str) and len(value) > 50000:
                transformed.append(value[:50000])
            # Keep everything else as-is (timestamps, integers, floats, regular text)
            else:
                transformed.append(value)

        return transformed
