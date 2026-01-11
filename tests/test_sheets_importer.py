"""Unit tests for Google Sheets to SQLite importer.

These tests verify the data transformation and import logic for converting
Google Sheets student progress data back to SQLite before implementation.
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

# Import will fail until implementation exists, but structure should be correct
pytest.importorskip("chibi.backup.sheets_importer", reason="Implementation not yet created")


class TestSheetsImporterInitialization:
    """Test SheetsImporter initialization and configuration."""

    @pytest.mark.skip(reason="Implementation not yet created")
    def test_initialization_with_dependencies(self):
        """
        Test SheetsImporter initializes with required dependencies.

        Given: Database and GoogleSheetsClient instances
        When: SheetsImporter is created
        Then: Should store dependencies correctly
        """
        from chibi.backup.sheets_importer import SheetsImporter

        mock_db = MagicMock()
        mock_sheets_client = MagicMock()

        importer = SheetsImporter(
            database=mock_db,
            sheets_client=mock_sheets_client,
        )

        assert importer.database == mock_db
        assert importer.sheets_client == mock_sheets_client


class TestSchemaValidation:
    """Test schema validation for Sheets data."""

    @pytest.mark.skip(reason="Implementation not yet created")
    @pytest.mark.asyncio
    async def test_valid_schema_passes_validation(self):
        """
        Test that valid Sheets structure passes validation.

        Given: Spreadsheet with correct Metadata sheet and 5 data sheets
        When: Schema is validated
        Then: Should pass without errors
        """
        from chibi.backup.sheets_importer import SheetsImporter

        mock_sheets_client = MagicMock()
        mock_sheets_client.read_sheet = AsyncMock()

        # Mock Metadata sheet
        mock_sheets_client.read_sheet.return_value = [
            ["Key", "Value"],
            ["export_date", "2026-01-11 10:00:00"],
            ["schema_version", "1.0"],
            ["users_count", "3"],
            ["quiz_attempts_count", "10"],
            ["concept_mastery_count", "5"],
            ["llm_quiz_attempts_count", "2"],
            ["attendance_count", "8"],
        ]

        # Mock getting spreadsheet to list sheets
        mock_sheets_client.get_spreadsheet = AsyncMock(return_value={
            "sheets": [
                {"properties": {"title": "Metadata"}},
                {"properties": {"title": "Users"}},
                {"properties": {"title": "QuizAttempts"}},
                {"properties": {"title": "ConceptMastery"}},
                {"properties": {"title": "LLMQuizAttempts"}},
                {"properties": {"title": "Attendance"}},
            ]
        })

        mock_db = MagicMock()
        importer = SheetsImporter(database=mock_db, sheets_client=mock_sheets_client)

        # Should not raise any exception
        await importer._validate_schema("test_spreadsheet_id")

    @pytest.mark.skip(reason="Implementation not yet created")
    @pytest.mark.asyncio
    async def test_missing_metadata_sheet_fails_validation(self):
        """
        Test that missing Metadata sheet fails validation.

        Given: Spreadsheet without Metadata sheet
        When: Schema is validated
        Then: Should raise ValidationError
        """
        from chibi.backup.sheets_importer import SheetsImporter, ValidationError

        mock_sheets_client = MagicMock()
        mock_sheets_client.get_spreadsheet = AsyncMock(return_value={
            "sheets": [
                {"properties": {"title": "Users"}},
                {"properties": {"title": "QuizAttempts"}},
            ]
        })

        mock_db = MagicMock()
        importer = SheetsImporter(database=mock_db, sheets_client=mock_sheets_client)

        with pytest.raises(ValidationError, match="Metadata sheet not found"):
            await importer._validate_schema("test_spreadsheet_id")

    @pytest.mark.skip(reason="Implementation not yet created")
    @pytest.mark.asyncio
    async def test_missing_data_sheet_fails_validation(self):
        """
        Test that missing required data sheet fails validation.

        Given: Spreadsheet missing QuizAttempts sheet
        When: Schema is validated
        Then: Should raise ValidationError
        """
        from chibi.backup.sheets_importer import SheetsImporter, ValidationError

        mock_sheets_client = MagicMock()
        mock_sheets_client.get_spreadsheet = AsyncMock(return_value={
            "sheets": [
                {"properties": {"title": "Metadata"}},
                {"properties": {"title": "Users"}},
                # Missing: QuizAttempts, ConceptMastery, LLMQuizAttempts, Attendance
            ]
        })

        mock_sheets_client.read_sheet = AsyncMock(return_value=[
            ["Key", "Value"],
            ["schema_version", "1.0"],
        ])

        mock_db = MagicMock()
        importer = SheetsImporter(database=mock_db, sheets_client=mock_sheets_client)

        with pytest.raises(ValidationError, match="Missing required sheet"):
            await importer._validate_schema("test_spreadsheet_id")

    @pytest.mark.skip(reason="Implementation not yet created")
    @pytest.mark.asyncio
    async def test_invalid_schema_version_fails_validation(self):
        """
        Test that incompatible schema version fails validation.

        Given: Spreadsheet with schema_version 2.0 (incompatible)
        When: Schema is validated
        Then: Should raise ValidationError
        """
        from chibi.backup.sheets_importer import SheetsImporter, ValidationError

        mock_sheets_client = MagicMock()
        mock_sheets_client.get_spreadsheet = AsyncMock(return_value={
            "sheets": [
                {"properties": {"title": "Metadata"}},
                {"properties": {"title": "Users"}},
                {"properties": {"title": "QuizAttempts"}},
                {"properties": {"title": "ConceptMastery"}},
                {"properties": {"title": "LLMQuizAttempts"}},
                {"properties": {"title": "Attendance"}},
            ]
        })

        mock_sheets_client.read_sheet = AsyncMock(return_value=[
            ["Key", "Value"],
            ["schema_version", "2.0"],  # Incompatible version
        ])

        mock_db = MagicMock()
        importer = SheetsImporter(database=mock_db, sheets_client=mock_sheets_client)

        with pytest.raises(ValidationError, match="Incompatible schema version"):
            await importer._validate_schema("test_spreadsheet_id")


class TestDataTypeConversions:
    """Test data type conversions from Sheets to SQLite."""

    @pytest.mark.skip(reason="Implementation not yet created")
    def test_convert_empty_string_to_none(self):
        """
        Test that empty strings are converted to None for NULL columns.

        Given: Sheet row with empty strings
        When: Data is converted to SQLite format
        Then: Empty strings should become None
        """
        from chibi.backup.sheets_importer import SheetsImporter

        mock_db = MagicMock()
        mock_sheets_client = MagicMock()
        importer = SheetsImporter(database=mock_db, sheets_client=mock_sheets_client)

        # Sheets data with empty strings
        sheets_row = {
            "id": "1",
            "discord_id": "123456",
            "username": "alice",
            "student_id": "",  # Empty string should become None
            "student_name": "",  # Empty string should become None
        }

        converted = importer._convert_sheet_row_to_sqlite(sheets_row, "users")

        assert converted["student_id"] is None
        assert converted["student_name"] is None
        assert converted["username"] == "alice"  # Non-empty preserved

    @pytest.mark.skip(reason="Implementation not yet created")
    def test_convert_true_false_strings_to_boolean(self):
        """
        Test that TRUE/FALSE strings are converted to 1/0 for BOOLEAN columns.

        Given: Sheet row with "TRUE" and "FALSE" strings
        When: Data is converted to SQLite format
        Then: Should become 1 and 0 integers
        """
        from chibi.backup.sheets_importer import SheetsImporter

        mock_db = MagicMock()
        mock_sheets_client = MagicMock()
        importer = SheetsImporter(database=mock_db, sheets_client=mock_sheets_client)

        # Sheets data with TRUE/FALSE strings
        sheets_row = {
            "id": "1",
            "user_id": "1",
            "module_id": "module01",
            "concept_id": "concept01",
            "quiz_format": "mc",
            "question": "What is a node?",
            "user_answer": "A vertex",
            "correct_answer": "A vertex",
            "is_correct": "TRUE",  # String should become 1
            "llm_feedback": "Good",
            "llm_quality_score": "95",
        }

        converted = importer._convert_sheet_row_to_sqlite(sheets_row, "quiz_attempts")

        assert converted["is_correct"] == 1  # TRUE → 1
        assert isinstance(converted["is_correct"], int)

    @pytest.mark.skip(reason="Implementation not yet created")
    def test_convert_numeric_strings_to_integers(self):
        """
        Test that numeric strings are converted to integers for INTEGER columns.

        Given: Sheet row with numeric strings
        When: Data is converted to SQLite format
        Then: Should become integers
        """
        from chibi.backup.sheets_importer import SheetsImporter

        mock_db = MagicMock()
        mock_sheets_client = MagicMock()
        importer = SheetsImporter(database=mock_db, sheets_client=mock_sheets_client)

        sheets_row = {
            "id": "5",
            "user_id": "1",
            "concept_id": "concept01",
            "total_attempts": "10",  # String should become int
            "correct_attempts": "8",  # String should become int
            "avg_quality_score": "85.5",  # String should become float
            "mastery_level": "mastered",
        }

        converted = importer._convert_sheet_row_to_sqlite(sheets_row, "concept_mastery")

        assert converted["total_attempts"] == 10
        assert isinstance(converted["total_attempts"], int)
        assert converted["avg_quality_score"] == 85.5
        assert isinstance(converted["avg_quality_score"], float)

    @pytest.mark.skip(reason="Implementation not yet created")
    def test_preserve_timestamp_format(self):
        """
        Test that timestamp strings are preserved as-is.

        Given: Sheet row with ISO timestamp strings
        When: Data is converted to SQLite format
        Then: Should remain as ISO string
        """
        from chibi.backup.sheets_importer import SheetsImporter

        mock_db = MagicMock()
        mock_sheets_client = MagicMock()
        importer = SheetsImporter(database=mock_db, sheets_client=mock_sheets_client)

        timestamp = "2026-01-11 14:30:00"
        sheets_row = {
            "id": "1",
            "discord_id": "123456",
            "username": "alice",
            "student_id": "A001",
            "student_name": "Alice Smith",
            "created_at": timestamp,
            "last_active": timestamp,
        }

        converted = importer._convert_sheet_row_to_sqlite(sheets_row, "users")

        assert converted["created_at"] == timestamp
        assert isinstance(converted["created_at"], str)


class TestReplaceMode:
    """Test import with replace mode (DELETE all, then INSERT)."""

    @pytest.mark.skip(reason="Implementation not yet created")
    @pytest.mark.asyncio
    async def test_replace_mode_deletes_then_inserts(self, test_database):
        """
        Test that replace mode deletes existing data then inserts new data.

        Given: Database with existing users [Alice, Bob]
        And: Sheets with users [Charlie, David]
        When: import_from_sheets is called with mode='replace'
        Then: Database should contain only [Charlie, David]
        """
        from chibi.backup.sheets_importer import SheetsImporter

        # Insert existing data
        async with test_database.connection.execute(
            "INSERT INTO users (discord_id, username, student_id, student_name) VALUES (?, ?, ?, ?)",
            ("111", "alice", "A001", "Alice")
        ):
            pass
        async with test_database.connection.execute(
            "INSERT INTO users (discord_id, username, student_id, student_name) VALUES (?, ?, ?, ?)",
            ("222", "bob", "B002", "Bob")
        ):
            pass
        await test_database.connection.commit()

        # Mock sheets client with new data
        mock_sheets_client = MagicMock()
        mock_sheets_client.get_spreadsheet = AsyncMock(return_value={
            "sheets": [
                {"properties": {"title": "Metadata"}},
                {"properties": {"title": "Users"}},
                {"properties": {"title": "QuizAttempts"}},
                {"properties": {"title": "ConceptMastery"}},
                {"properties": {"title": "LLMQuizAttempts"}},
                {"properties": {"title": "Attendance"}},
            ]
        })

        def read_sheet_side_effect(spreadsheet_id, sheet_name):
            if sheet_name == "Metadata":
                return [
                    ["Key", "Value"],
                    ["schema_version", "1.0"],
                    ["export_date", "2026-01-11 10:00:00"],
                    ["users_count", "2"],
                ]
            elif sheet_name == "Users":
                return [
                    ["id", "discord_id", "username", "student_id", "student_name", "created_at", "last_active"],
                    ["1", "333", "charlie", "C003", "Charlie", "2026-01-11 10:00:00", "2026-01-11 10:00:00"],
                    ["2", "444", "david", "D004", "David", "2026-01-11 10:00:00", "2026-01-11 10:00:00"],
                ]
            else:
                # Empty data sheets
                return [[]]

        mock_sheets_client.read_sheet = AsyncMock(side_effect=read_sheet_side_effect)

        importer = SheetsImporter(database=test_database, sheets_client=mock_sheets_client)

        result = await importer.import_from_sheets("test_spreadsheet_id", mode="replace")

        # Verify old data is gone
        async with test_database.connection.execute("SELECT * FROM users ORDER BY discord_id") as cursor:
            rows = await cursor.fetchall()
            assert len(rows) == 2
            assert rows[0]["discord_id"] == "333"
            assert rows[0]["username"] == "charlie"
            assert rows[1]["discord_id"] == "444"
            assert rows[1]["username"] == "david"

        assert result["mode"] == "replace"
        assert result["users_imported"] == 2

    @pytest.mark.skip(reason="Implementation not yet created")
    @pytest.mark.asyncio
    async def test_replace_mode_preserves_foreign_key_relationships(self, test_database):
        """
        Test that replace mode maintains foreign key relationships.

        Given: Sheets with users and their quiz_attempts
        When: import_from_sheets is called with mode='replace'
        Then: Foreign key relationships should be maintained
        """
        from chibi.backup.sheets_importer import SheetsImporter

        # Mock sheets client with related data
        mock_sheets_client = MagicMock()
        mock_sheets_client.get_spreadsheet = AsyncMock(return_value={
            "sheets": [
                {"properties": {"title": "Metadata"}},
                {"properties": {"title": "Users"}},
                {"properties": {"title": "QuizAttempts"}},
                {"properties": {"title": "ConceptMastery"}},
                {"properties": {"title": "LLMQuizAttempts"}},
                {"properties": {"title": "Attendance"}},
            ]
        })

        def read_sheet_side_effect(spreadsheet_id, sheet_name):
            if sheet_name == "Metadata":
                return [
                    ["Key", "Value"],
                    ["schema_version", "1.0"],
                ]
            elif sheet_name == "Users":
                return [
                    ["id", "discord_id", "username", "student_id", "student_name", "created_at", "last_active"],
                    ["1", "123", "alice", "A001", "Alice", "2026-01-11 10:00:00", "2026-01-11 10:00:00"],
                ]
            elif sheet_name == "QuizAttempts":
                return [
                    ["id", "user_id", "module_id", "concept_id", "quiz_format", "question", "user_answer", "correct_answer", "is_correct", "llm_feedback", "llm_quality_score", "created_at"],
                    ["1", "1", "module01", "concept01", "mc", "What is a node?", "A vertex", "A vertex", "TRUE", "Good", "95", "2026-01-11 10:00:00"],
                ]
            else:
                return [[]]

        mock_sheets_client.read_sheet = AsyncMock(side_effect=read_sheet_side_effect)

        importer = SheetsImporter(database=test_database, sheets_client=mock_sheets_client)
        await importer.import_from_sheets("test_spreadsheet_id", mode="replace")

        # Verify foreign key relationship
        async with test_database.connection.execute(
            "SELECT q.*, u.username FROM quiz_attempts q JOIN users u ON q.user_id = u.id"
        ) as cursor:
            row = await cursor.fetchone()
            assert row["username"] == "alice"
            assert row["question"] == "What is a node?"


class TestMergeMode:
    """Test import with merge mode (INSERT OR REPLACE)."""

    @pytest.mark.skip(reason="Implementation not yet created")
    @pytest.mark.asyncio
    async def test_merge_mode_updates_existing_and_inserts_new(self, test_database):
        """
        Test that merge mode updates existing records and inserts new ones.

        Given: Database with users [Alice, Bob]
        And: Sheets with users [Alice (updated), Charlie]
        When: import_from_sheets is called with mode='merge'
        Then: Database should contain [Alice (updated), Bob, Charlie]
        """
        from chibi.backup.sheets_importer import SheetsImporter

        # Insert existing data
        async with test_database.connection.execute(
            "INSERT INTO users (id, discord_id, username, student_id, student_name) VALUES (?, ?, ?, ?, ?)",
            (1, "111", "alice", "A001", "Alice Old")
        ):
            pass
        async with test_database.connection.execute(
            "INSERT INTO users (id, discord_id, username, student_id, student_name) VALUES (?, ?, ?, ?, ?)",
            (2, "222", "bob", "B002", "Bob")
        ):
            pass
        await test_database.connection.commit()

        # Mock sheets client
        mock_sheets_client = MagicMock()
        mock_sheets_client.get_spreadsheet = AsyncMock(return_value={
            "sheets": [
                {"properties": {"title": "Metadata"}},
                {"properties": {"title": "Users"}},
                {"properties": {"title": "QuizAttempts"}},
                {"properties": {"title": "ConceptMastery"}},
                {"properties": {"title": "LLMQuizAttempts"}},
                {"properties": {"title": "Attendance"}},
            ]
        })

        def read_sheet_side_effect(spreadsheet_id, sheet_name):
            if sheet_name == "Metadata":
                return [
                    ["Key", "Value"],
                    ["schema_version", "1.0"],
                ]
            elif sheet_name == "Users":
                return [
                    ["id", "discord_id", "username", "student_id", "student_name", "created_at", "last_active"],
                    ["1", "111", "alice", "A001", "Alice Updated", "2026-01-11 10:00:00", "2026-01-11 10:00:00"],  # Updated
                    ["3", "333", "charlie", "C003", "Charlie", "2026-01-11 10:00:00", "2026-01-11 10:00:00"],  # New
                ]
            else:
                return [[]]

        mock_sheets_client.read_sheet = AsyncMock(side_effect=read_sheet_side_effect)

        importer = SheetsImporter(database=test_database, sheets_client=mock_sheets_client)
        result = await importer.import_from_sheets("test_spreadsheet_id", mode="merge")

        # Verify data
        async with test_database.connection.execute("SELECT * FROM users ORDER BY id") as cursor:
            rows = await cursor.fetchall()
            assert len(rows) == 3
            # Alice updated
            assert rows[0]["id"] == 1
            assert rows[0]["student_name"] == "Alice Updated"
            # Bob unchanged
            assert rows[1]["id"] == 2
            assert rows[1]["username"] == "bob"
            # Charlie added
            assert rows[2]["id"] == 3
            assert rows[2]["username"] == "charlie"

        assert result["mode"] == "merge"


class TestTransactionRollback:
    """Test transaction rollback on errors."""

    @pytest.mark.skip(reason="Implementation not yet created")
    @pytest.mark.asyncio
    async def test_rollback_on_foreign_key_violation(self, test_database):
        """
        Test that transaction rolls back on foreign key violation.

        Given: Sheets with quiz_attempts referencing non-existent user_id
        When: import_from_sheets is called
        Then: Transaction should rollback, no partial data inserted
        """
        from chibi.backup.sheets_importer import SheetsImporter, ImportError

        # Insert one user
        async with test_database.connection.execute(
            "INSERT INTO users (id, discord_id, username) VALUES (?, ?, ?)",
            (1, "111", "alice")
        ):
            pass
        await test_database.connection.commit()

        # Mock sheets client with invalid foreign key
        mock_sheets_client = MagicMock()
        mock_sheets_client.get_spreadsheet = AsyncMock(return_value={
            "sheets": [
                {"properties": {"title": "Metadata"}},
                {"properties": {"title": "Users"}},
                {"properties": {"title": "QuizAttempts"}},
                {"properties": {"title": "ConceptMastery"}},
                {"properties": {"title": "LLMQuizAttempts"}},
                {"properties": {"title": "Attendance"}},
            ]
        })

        def read_sheet_side_effect(spreadsheet_id, sheet_name):
            if sheet_name == "Metadata":
                return [
                    ["Key", "Value"],
                    ["schema_version", "1.0"],
                ]
            elif sheet_name == "Users":
                return [
                    ["id", "discord_id", "username", "student_id", "student_name", "created_at", "last_active"],
                ]
            elif sheet_name == "QuizAttempts":
                return [
                    ["id", "user_id", "module_id", "concept_id", "quiz_format", "question", "user_answer", "correct_answer", "is_correct", "llm_feedback", "llm_quality_score", "created_at"],
                    ["1", "999", "module01", "concept01", "mc", "What?", "Answer", "Answer", "TRUE", "Good", "95", "2026-01-11 10:00:00"],  # user_id 999 doesn't exist
                ]
            else:
                return [[]]

        mock_sheets_client.read_sheet = AsyncMock(side_effect=read_sheet_side_effect)

        importer = SheetsImporter(database=test_database, sheets_client=mock_sheets_client)

        # Should raise error and rollback
        with pytest.raises(ImportError):
            await importer.import_from_sheets("test_spreadsheet_id", mode="replace")

        # Verify no quiz_attempts were inserted
        async with test_database.connection.execute("SELECT COUNT(*) as count FROM quiz_attempts") as cursor:
            row = await cursor.fetchone()
            assert row["count"] == 0

    @pytest.mark.skip(reason="Implementation not yet created")
    @pytest.mark.asyncio
    async def test_rollback_preserves_original_data(self, test_database):
        """
        Test that rollback preserves original data on error.

        Given: Database with existing data
        And: Import fails midway
        When: Transaction rolls back
        Then: Original data should be preserved unchanged
        """
        from chibi.backup.sheets_importer import SheetsImporter, ImportError

        # Insert original data
        async with test_database.connection.execute(
            "INSERT INTO users (id, discord_id, username) VALUES (?, ?, ?)",
            (1, "111", "alice")
        ):
            pass
        await test_database.connection.commit()

        # Mock sheets client that will cause error
        mock_sheets_client = MagicMock()
        mock_sheets_client.get_spreadsheet = AsyncMock(return_value={
            "sheets": [
                {"properties": {"title": "Metadata"}},
                {"properties": {"title": "Users"}},
                {"properties": {"title": "QuizAttempts"}},
                {"properties": {"title": "ConceptMastery"}},
                {"properties": {"title": "LLMQuizAttempts"}},
                {"properties": {"title": "Attendance"}},
            ]
        })

        def read_sheet_side_effect(spreadsheet_id, sheet_name):
            if sheet_name == "Metadata":
                return [
                    ["Key", "Value"],
                    ["schema_version", "1.0"],
                ]
            elif sheet_name == "Users":
                # Invalid data that will cause error (missing required field)
                return [
                    ["id", "discord_id", "username", "student_id", "student_name", "created_at", "last_active"],
                    ["2", "", "bob", "B002", "Bob", "2026-01-11 10:00:00", "2026-01-11 10:00:00"],  # Empty discord_id (NOT NULL constraint)
                ]
            else:
                return [[]]

        mock_sheets_client.read_sheet = AsyncMock(side_effect=read_sheet_side_effect)

        importer = SheetsImporter(database=test_database, sheets_client=mock_sheets_client)

        # Should raise error
        with pytest.raises((ImportError, Exception)):
            await importer.import_from_sheets("test_spreadsheet_id", mode="replace")

        # Verify original data is preserved
        async with test_database.connection.execute("SELECT * FROM users") as cursor:
            rows = await cursor.fetchall()
            assert len(rows) == 1
            assert rows[0]["discord_id"] == "111"
            assert rows[0]["username"] == "alice"


class TestSpreadsheetURLExtraction:
    """Test extracting spreadsheet ID from various URL formats."""

    @pytest.mark.skip(reason="Implementation not yet created")
    def test_extract_id_from_full_url(self):
        """
        Test extracting spreadsheet ID from full Google Sheets URL.

        Given: Full URL like https://docs.google.com/spreadsheets/d/SPREADSHEET_ID/edit
        When: Spreadsheet ID is extracted
        Then: Should return just SPREADSHEET_ID
        """
        from chibi.backup.sheets_importer import SheetsImporter

        mock_db = MagicMock()
        mock_sheets_client = MagicMock()
        importer = SheetsImporter(database=mock_db, sheets_client=mock_sheets_client)

        url = "https://docs.google.com/spreadsheets/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms/edit#gid=0"
        spreadsheet_id = importer._extract_spreadsheet_id(url)

        assert spreadsheet_id == "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms"

    @pytest.mark.skip(reason="Implementation not yet created")
    def test_extract_id_from_short_url(self):
        """
        Test extracting spreadsheet ID from short URL.

        Given: Short URL without /edit
        When: Spreadsheet ID is extracted
        Then: Should return just SPREADSHEET_ID
        """
        from chibi.backup.sheets_importer import SheetsImporter

        mock_db = MagicMock()
        mock_sheets_client = MagicMock()
        importer = SheetsImporter(database=mock_db, sheets_client=mock_sheets_client)

        url = "https://docs.google.com/spreadsheets/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms"
        spreadsheet_id = importer._extract_spreadsheet_id(url)

        assert spreadsheet_id == "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms"

    @pytest.mark.skip(reason="Implementation not yet created")
    def test_handle_plain_spreadsheet_id(self):
        """
        Test handling plain spreadsheet ID (not a URL).

        Given: Just the spreadsheet ID string
        When: Spreadsheet ID is extracted
        Then: Should return the same ID unchanged
        """
        from chibi.backup.sheets_importer import SheetsImporter

        mock_db = MagicMock()
        mock_sheets_client = MagicMock()
        importer = SheetsImporter(database=mock_db, sheets_client=mock_sheets_client)

        spreadsheet_id = "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms"
        result = importer._extract_spreadsheet_id(spreadsheet_id)

        assert result == spreadsheet_id


class TestFullImportWorkflow:
    """Test complete import workflow end-to-end."""

    @pytest.mark.skip(reason="Implementation not yet created")
    @pytest.mark.asyncio
    async def test_successful_import_returns_summary(self, test_database):
        """
        Test that successful import returns comprehensive summary.

        Given: Valid spreadsheet with complete data
        When: import_from_sheets is called
        Then: Should return dict with mode, counts, and success status
        """
        from chibi.backup.sheets_importer import SheetsImporter

        # Mock sheets client
        mock_sheets_client = MagicMock()
        mock_sheets_client.get_spreadsheet = AsyncMock(return_value={
            "sheets": [
                {"properties": {"title": "Metadata"}},
                {"properties": {"title": "Users"}},
                {"properties": {"title": "QuizAttempts"}},
                {"properties": {"title": "ConceptMastery"}},
                {"properties": {"title": "LLMQuizAttempts"}},
                {"properties": {"title": "Attendance"}},
            ]
        })

        def read_sheet_side_effect(spreadsheet_id, sheet_name):
            if sheet_name == "Metadata":
                return [
                    ["Key", "Value"],
                    ["schema_version", "1.0"],
                    ["export_date", "2026-01-11 10:00:00"],
                ]
            elif sheet_name == "Users":
                return [
                    ["id", "discord_id", "username", "student_id", "student_name", "created_at", "last_active"],
                    ["1", "111", "alice", "A001", "Alice", "2026-01-11 10:00:00", "2026-01-11 10:00:00"],
                    ["2", "222", "bob", "B002", "Bob", "2026-01-11 10:00:00", "2026-01-11 10:00:00"],
                ]
            else:
                return [[]]

        mock_sheets_client.read_sheet = AsyncMock(side_effect=read_sheet_side_effect)

        importer = SheetsImporter(database=test_database, sheets_client=mock_sheets_client)
        result = await importer.import_from_sheets("test_spreadsheet_id", mode="replace")

        assert result["mode"] == "replace"
        assert result["users_imported"] == 2
        assert result["quiz_attempts_imported"] == 0
        assert result["concept_mastery_imported"] == 0
        assert result["llm_quiz_attempts_imported"] == 0
        assert result["attendance_imported"] == 0
        assert "export_date" in result
