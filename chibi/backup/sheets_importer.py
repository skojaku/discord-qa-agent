"""Google Sheets to SQLite importer.

This module provides functionality to import student progress data from Google Sheets
back to SQLite database with proper data type conversions and validation.
"""

import logging
import re
from typing import Any, Dict, List

from chibi.database.connection import Database
from chibi.backup.google_sheets_client import GoogleSheetsClient

logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """Raised when spreadsheet schema validation fails."""

    pass


class ImportError(Exception):
    """Raised when import operation fails."""

    pass


class SheetsImporter:
    """Imports Google Sheets student progress data to SQLite database."""

    # Expected schema version
    EXPECTED_SCHEMA_VERSION = "1.0"

    # Required sheets
    REQUIRED_SHEETS = [
        "Metadata",
        "Users",
        "QuizAttempts",
        "ConceptMastery",
        "LLMQuizAttempts",
        "Attendance",
    ]

    # Table names mapping
    TABLE_MAPPING = {
        "Users": "users",
        "QuizAttempts": "quiz_attempts",
        "ConceptMastery": "concept_mastery",
        "LLMQuizAttempts": "llm_quiz_attempts",
        "Attendance": "attendance",
    }

    # Boolean columns per table
    BOOLEAN_COLUMNS = {
        "quiz_attempts": ["is_correct"],
        "llm_quiz_attempts": ["student_wins"],
    }

    # Integer columns per table (for type conversion)
    INTEGER_COLUMNS = {
        "users": ["id"],
        "quiz_attempts": ["id", "user_id", "llm_quality_score"],
        "concept_mastery": ["id", "user_id", "total_attempts", "correct_attempts"],
        "llm_quiz_attempts": ["id", "user_id"],
        "attendance": ["id", "user_id"],
    }

    # Float columns per table
    FLOAT_COLUMNS = {
        "concept_mastery": ["avg_quality_score"],
    }

    def __init__(self, database: Database, sheets_client: GoogleSheetsClient):
        """
        Initialize the importer.

        Args:
            database: Database connection instance
            sheets_client: GoogleSheetsClient for Sheets API operations
        """
        self.database = database
        self.sheets_client = sheets_client

    def _extract_spreadsheet_id(self, spreadsheet_url_or_id: str) -> str:
        """
        Extract spreadsheet ID from URL or return as-is if already an ID.

        Supports formats:
        - https://docs.google.com/spreadsheets/d/SPREADSHEET_ID/edit#gid=0
        - https://docs.google.com/spreadsheets/d/SPREADSHEET_ID
        - SPREADSHEET_ID (plain ID)

        Args:
            spreadsheet_url_or_id: URL or ID of spreadsheet

        Returns:
            Spreadsheet ID
        """
        # Try to extract from URL pattern
        match = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", spreadsheet_url_or_id)
        if match:
            return match.group(1)

        # Assume it's already an ID
        return spreadsheet_url_or_id

    async def _validate_schema(self, spreadsheet_id: str) -> Dict[str, Any]:
        """
        Validate spreadsheet schema and structure.

        Checks:
        - All required sheets exist
        - Metadata sheet has schema_version
        - Schema version is compatible

        Args:
            spreadsheet_id: The spreadsheet ID to validate

        Returns:
            Dict with metadata information

        Raises:
            ValidationError: If schema validation fails
        """
        # Get spreadsheet to list sheets
        spreadsheet = self.sheets_client.get_spreadsheet(spreadsheet_id)
        sheet_names = [
            sheet["properties"]["title"] for sheet in spreadsheet.get("sheets", [])
        ]

        logger.debug(f"Found sheets: {sheet_names}")

        # Check for Metadata sheet
        if "Metadata" not in sheet_names:
            raise ValidationError("Metadata sheet not found in spreadsheet")

        # Check for required data sheets
        for required_sheet in self.REQUIRED_SHEETS:
            if required_sheet not in sheet_names:
                raise ValidationError(
                    f"Missing required sheet: {required_sheet}. "
                    f"Expected sheets: {', '.join(self.REQUIRED_SHEETS)}"
                )

        # Read and validate metadata
        metadata_rows = self.sheets_client.read_sheet(spreadsheet_id, "Metadata")

        # Convert to dict for easier access
        metadata = {}
        for row in metadata_rows[1:]:  # Skip header
            if len(row) >= 2:
                metadata[row[0]] = row[1]

        # Check schema version
        schema_version = metadata.get("schema_version")
        if schema_version != self.EXPECTED_SCHEMA_VERSION:
            raise ValidationError(
                f"Incompatible schema version: {schema_version}. "
                f"Expected: {self.EXPECTED_SCHEMA_VERSION}"
            )

        logger.info(f"Schema validation passed. Version: {schema_version}")
        return metadata

    def _convert_sheet_row_to_sqlite(
        self, sheets_row: Dict[str, Any], table_name: str
    ) -> Dict[str, Any]:
        """
        Convert a Sheets row to SQLite format with type conversions.

        Conversions:
        - "" (empty string) → None (NULL)
        - "TRUE"/"FALSE" → 1/0 (boolean)
        - Numeric strings → int or float
        - Timestamps → preserved as ISO strings

        Args:
            sheets_row: Dict with column names as keys
            table_name: Name of target table for type hints

        Returns:
            Dict with converted values
        """
        converted = {}

        for column, value in sheets_row.items():
            # Convert empty string to None
            if value == "":
                converted[column] = None
            # Convert TRUE/FALSE to 1/0 for boolean columns
            elif (
                column in self.BOOLEAN_COLUMNS.get(table_name, [])
                and isinstance(value, str)
            ):
                if value.upper() == "TRUE":
                    converted[column] = 1
                elif value.upper() == "FALSE":
                    converted[column] = 0
                else:
                    converted[column] = value
            # Convert numeric strings to int for integer columns
            elif column in self.INTEGER_COLUMNS.get(table_name, []):
                try:
                    converted[column] = int(value) if value != "" else None
                except (ValueError, TypeError):
                    converted[column] = value
            # Convert numeric strings to float for float columns
            elif column in self.FLOAT_COLUMNS.get(table_name, []):
                try:
                    converted[column] = float(value) if value != "" else None
                except (ValueError, TypeError):
                    converted[column] = value
            # Keep everything else as-is
            else:
                converted[column] = value

        return converted

    async def _import_table(
        self,
        spreadsheet_id: str,
        sheet_name: str,
        table_name: str,
        mode: str,
        conn: Any,
    ) -> int:
        """
        Import a single table from Sheets to SQLite.

        Args:
            spreadsheet_id: The spreadsheet ID
            sheet_name: Name of sheet to import from
            table_name: Name of SQLite table to import to
            mode: 'replace' or 'merge'
            conn: Database connection

        Returns:
            Number of rows imported

        Raises:
            ImportError: If import fails
        """
        # Read sheet data
        sheet_data = self.sheets_client.read_sheet(spreadsheet_id, sheet_name)

        if not sheet_data or len(sheet_data) < 1:
            logger.debug(f"No data in {sheet_name}, skipping")
            return 0

        # First row is headers
        headers = sheet_data[0]
        data_rows = sheet_data[1:]

        if not data_rows:
            logger.debug(f"No data rows in {sheet_name}")
            return 0

        # Delete existing data in replace mode
        if mode == "replace":
            await conn.execute(f"DELETE FROM {table_name}")
            logger.debug(f"Deleted existing data from {table_name}")

        # Insert or replace each row
        count = 0
        for row_values in data_rows:
            # Skip empty rows
            if not row_values or all(v == "" for v in row_values):
                continue

            # Pad row with empty strings if needed
            while len(row_values) < len(headers):
                row_values.append("")

            # Create dict from headers and values
            sheets_row = dict(zip(headers, row_values))

            # Convert types
            converted_row = self._convert_sheet_row_to_sqlite(sheets_row, table_name)

            # Build INSERT OR REPLACE statement
            columns = list(converted_row.keys())
            placeholders = ", ".join(["?"] * len(columns))
            columns_str = ", ".join(columns)

            if mode == "merge":
                sql = f"INSERT OR REPLACE INTO {table_name} ({columns_str}) VALUES ({placeholders})"
            else:  # replace mode
                sql = f"INSERT INTO {table_name} ({columns_str}) VALUES ({placeholders})"

            values = [converted_row[col] for col in columns]

            try:
                await conn.execute(sql, values)
                count += 1
            except Exception as e:
                logger.error(f"Failed to insert row into {table_name}: {e}")
                logger.error(f"Row data: {converted_row}")
                raise ImportError(f"Failed to insert row into {table_name}: {e}")

        logger.debug(f"Imported {count} rows into {table_name}")
        return count

    async def import_from_sheets(
        self, spreadsheet_url_or_id: str, mode: str = "replace"
    ) -> Dict[str, Any]:
        """
        Import student progress data from Google Sheets to SQLite.

        Modes:
        - 'replace': DELETE all existing data, then INSERT new data
        - 'merge': INSERT OR REPLACE (updates existing by ID, inserts new)

        Args:
            spreadsheet_url_or_id: URL or ID of spreadsheet to import
            mode: Import mode ('replace' or 'merge')

        Returns:
            Dict containing:
                - mode: The import mode used
                - users_imported: Number of user records imported
                - quiz_attempts_imported: Number of quiz attempts imported
                - concept_mastery_imported: Number of concept mastery records imported
                - llm_quiz_attempts_imported: Number of LLM quiz attempts imported
                - attendance_imported: Number of attendance records imported
                - export_date: Original export timestamp from metadata

        Raises:
            ValidationError: If schema validation fails
            ImportError: If import operation fails
        """
        # Extract spreadsheet ID
        spreadsheet_id = self._extract_spreadsheet_id(spreadsheet_url_or_id)
        logger.info(f"Importing from spreadsheet: {spreadsheet_id} (mode: {mode})")

        # Validate schema
        metadata = await self._validate_schema(spreadsheet_id)

        # Import all tables in a transaction
        conn = self.database.connection

        try:
            # Enable foreign key constraints
            await conn.execute("PRAGMA foreign_keys = ON")

            # Begin transaction
            await conn.execute("BEGIN")

            # Import tables in order (respecting foreign keys)
            users_count = await self._import_table(
                spreadsheet_id, "Users", "users", mode, conn
            )
            quiz_attempts_count = await self._import_table(
                spreadsheet_id, "QuizAttempts", "quiz_attempts", mode, conn
            )
            concept_mastery_count = await self._import_table(
                spreadsheet_id, "ConceptMastery", "concept_mastery", mode, conn
            )
            llm_quiz_attempts_count = await self._import_table(
                spreadsheet_id, "LLMQuizAttempts", "llm_quiz_attempts", mode, conn
            )
            attendance_count = await self._import_table(
                spreadsheet_id, "Attendance", "attendance", mode, conn
            )

            # Commit transaction
            await conn.commit()
            logger.info("Transaction committed successfully")

        except Exception as e:
            # Rollback on any error
            await conn.execute("ROLLBACK")
            logger.error(f"Import failed, transaction rolled back: {e}")
            raise ImportError(f"Import failed: {e}")

        # Build result
        from datetime import datetime
        import_timestamp = datetime.now().isoformat()

        result = {
            "mode": mode,
            "spreadsheet_id": spreadsheet_id,
            "import_date": import_timestamp,
            "schema_version": metadata.get("schema_version", "1.0"),
            "summary": {
                "users": users_count,
                "quiz_attempts": quiz_attempts_count,
                "concept_mastery": concept_mastery_count,
                "llm_quiz_attempts": llm_quiz_attempts_count,
                "attendance": attendance_count,
            },
            "status": "success",
            "counts": {  # Keep counts for backward compatibility
                "users": users_count,
                "quiz_attempts": quiz_attempts_count,
                "concept_mastery": concept_mastery_count,
                "llm_quiz_attempts": llm_quiz_attempts_count,
                "attendance": attendance_count,
            },
            # Backward compatibility keys
            "users_imported": users_count,
            "quiz_attempts_imported": quiz_attempts_count,
            "concept_mastery_imported": concept_mastery_count,
            "llm_quiz_attempts_imported": llm_quiz_attempts_count,
            "attendance_imported": attendance_count,
            "export_date": metadata.get("export_date", "unknown"),
        }

        logger.info(f"Import complete: {result}")
        return result
