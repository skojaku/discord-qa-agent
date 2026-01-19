"""Integration tests for full backup cycle: export, clear, import, verify.

These tests verify the complete workflow of exporting student progress to Google Sheets,
clearing the database, and restoring from backup. They test both replace and merge modes,
referential integrity, and data consistency.

Tests are marked as skip until implementation exists (US-009 to US-012).
"""

import pytest
from datetime import datetime
from typing import Dict, List, Any
from unittest.mock import AsyncMock, MagicMock, patch

# Skip entire module until implementation exists
pytest.importorskip("chibi.backup.backup_service", reason="BackupService not yet implemented")

from chibi.backup.backup_service import BackupService
from chibi.backup.google_sheets_client import GoogleSheetsClient
from chibi.backup.sheets_exporter import SheetsExporter
from chibi.backup.sheets_importer import SheetsImporter
from chibi.database.connection import Database


class TestFullBackupCycle:
    """Test complete export → clear → import workflow."""

    @pytest.fixture
    async def populated_database(self):
        """Create in-memory database with full schema and test data."""
        db = Database(":memory:")
        await db.connect()

        # Get connection for data insertion
        conn = db.connection

        # Create 3 test users
        users_data = [
            ("111111111", "student1", "S001", "Alice Student"),
            ("222222222", "student2", "S002", "Bob Student"),
            ("333333333", "student3", "S003", "Charlie Student"),
        ]

        user_ids = []
        for discord_id, username, student_id, student_name in users_data:
            cursor = await conn.execute(
                """INSERT INTO users (discord_id, username, student_id, student_name, created_at, last_active)
                VALUES (?, ?, ?, ?, ?, ?)""",
                (discord_id, username, student_id, student_name, "2024-01-01 10:00:00", "2024-01-10 15:30:00")
            )
            user_ids.append(cursor.lastrowid)

        # Create 10 quiz attempts (distributed across users)
        quiz_attempts_data = [
            (user_ids[0], "module01", "concept01", "free-form", "What is network centrality?",
             "It measures node importance", None, 1, "Good answer!", 85),
            (user_ids[0], "module01", "concept02", "mc", "What is a graph?",
             "A network structure", "A network structure", 1, "Correct!", 90),
            (user_ids[1], "module01", "concept01", "short_answer", "Define degree centrality",
             "Number of connections", "Number of direct connections", 0, "Partially correct", 60),
            (user_ids[1], "module02", "concept03", "tf", "Is a tree a graph?",
             "True", "True", 1, "Correct!", 95),
            (user_ids[2], "module01", "concept01", "free-form", "Explain betweenness centrality",
             "Measures how often a node appears on shortest paths", None, 1, "Excellent!", 95),
            (user_ids[2], "module01", "concept02", "mc", "What is eigenvector centrality?",
             "Centrality based on neighbor importance", "Centrality based on neighbor importance", 1, "Perfect!", 100),
            (user_ids[0], "module02", "concept03", "short_answer", "What is clustering coefficient?",
             "Probability neighbors are connected", "Probability that neighbors are connected", 1, "Great!", 88),
            (user_ids[1], "module02", "concept04", "free-form", "Describe PageRank",
             "Google's ranking algorithm", None, 1, "Good start", 70),
            (user_ids[2], "module02", "concept03", "tf", "Can a graph have cycles?",
             "True", "True", 1, "Correct!", 90),
            (user_ids[0], "module03", "concept05", "mc", "What is a directed graph?",
             "A graph with directed edges", "A graph with directed edges", 1, "Excellent!", 92),
        ]

        for user_id, module_id, concept_id, quiz_format, question, user_answer, correct_answer, is_correct, llm_feedback, llm_quality_score in quiz_attempts_data:
            await conn.execute(
                """INSERT INTO quiz_attempts
                (user_id, module_id, concept_id, quiz_format, question, user_answer, correct_answer,
                is_correct, llm_feedback, llm_quality_score, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (user_id, module_id, concept_id, quiz_format, question, user_answer, correct_answer,
                 is_correct, llm_feedback, llm_quality_score, "2024-01-10 14:00:00")
            )

        # Create 5 concept mastery records
        mastery_data = [
            (user_ids[0], "concept01", 4, 3, 87.5, "proficient", "2024-01-10 14:00:00"),
            (user_ids[0], "concept02", 2, 2, 91.0, "learning", "2024-01-10 14:05:00"),
            (user_ids[1], "concept01", 3, 2, 75.0, "learning", "2024-01-10 14:10:00"),
            (user_ids[2], "concept01", 2, 2, 95.0, "learning", "2024-01-10 14:15:00"),
            (user_ids[2], "concept02", 1, 1, 100.0, "novice", "2024-01-10 14:20:00"),
        ]

        for user_id, concept_id, total_attempts, correct_attempts, avg_quality_score, mastery_level, last_attempt_at in mastery_data:
            await conn.execute(
                """INSERT INTO concept_mastery
                (user_id, concept_id, total_attempts, correct_attempts, avg_quality_score,
                mastery_level, last_attempt_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (user_id, concept_id, total_attempts, correct_attempts, avg_quality_score,
                 mastery_level, last_attempt_at, "2024-01-10 14:30:00")
            )

        # Create 3 LLM quiz attempts
        llm_quiz_data = [
            (user_ids[0], "module01", "What makes eigenvector centrality different?",
             "It considers neighbor importance", "It only counts direct connections", 1,
             "Correct understanding", "Student correctly identified the key difference",
             "auto_approved", None, None, "111111111"),
            (user_ids[1], "module02", "How does PageRank handle dangling nodes?",
             "Teleportation to random pages", "Ignore them", 0,
             "Student answer is incomplete", "LLM provided more accurate explanation",
             "pending", None, None, "222222222"),
            (user_ids[2], "module01", "Why is betweenness expensive to compute?",
             "Requires all shortest paths", "It's not expensive", 1,
             "Excellent answer", "Student correctly explained computational complexity",
             "auto_approved", None, None, "333333333"),
        ]

        for user_id, module_id, question, student_answer, llm_answer, student_wins, student_answer_correctness, evaluation_explanation, review_status, reviewed_at, reviewed_by, discord_user_id in llm_quiz_data:
            await conn.execute(
                """INSERT INTO llm_quiz_attempts
                (user_id, module_id, question, student_answer, llm_answer, student_wins,
                student_answer_correctness, evaluation_explanation, review_status, reviewed_at,
                reviewed_by, discord_user_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (user_id, module_id, question, student_answer, llm_answer, student_wins,
                 student_answer_correctness, evaluation_explanation, review_status, reviewed_at,
                 reviewed_by, discord_user_id, "2024-01-10 15:00:00")
            )

        # Create 3 attendance records
        attendance_data = [
            (user_ids[0], "student1", "2024-01-08T10:00:00", "2024-01-08", "session01", "present"),
            (user_ids[1], "student2", "2024-01-08T10:05:00", "2024-01-08", "session01", "present"),
            (user_ids[2], "student3", "2024-01-08T10:10:00", "2024-01-08", "session01", "excused"),
        ]

        for user_id, username, timestamp, date_id, session_id, status in attendance_data:
            await conn.execute(
                """INSERT INTO attendance
                (user_id, username, timestamp, date_id, session_id, status)
                VALUES (?, ?, ?, ?, ?, ?)""",
                (user_id, username, timestamp, date_id, session_id, status)
            )

        await conn.commit()

        yield db, user_ids

        await db.close()

    @pytest.fixture
    def mock_sheets_client(self):
        """Mock Google Sheets client with realistic responses."""
        mock_client = MagicMock(spec=GoogleSheetsClient)

        # Mock spreadsheet creation (returns just the ID string)
        mock_client.create_spreadsheet = MagicMock(return_value="test_spreadsheet_123")

        # Store written data for later reads
        mock_client._sheets_data = {}

        def mock_write_sheet(spreadsheet_id: str, sheet_name: str, data: List[List[Any]]):
            """Store data for later retrieval."""
            mock_client._sheets_data[sheet_name] = data
            return {"updated_cells": len(data)}

        def mock_read_sheet(spreadsheet_id: str, sheet_name: str) -> List[List[Any]]:
            """Retrieve previously written data."""
            return mock_client._sheets_data.get(sheet_name, [])

        def mock_get_spreadsheet(spreadsheet_id: str):
            """Mock get_spreadsheet to return sheet list."""
            # Return structure with sheets that match what was written
            sheets = [{"properties": {"title": name}} for name in mock_client._sheets_data.keys()]
            return {
                "spreadsheetId": spreadsheet_id,
                "properties": {"title": "Test Spreadsheet"},
                "sheets": sheets
            }

        mock_client.write_sheet = mock_write_sheet
        mock_client.read_sheet = mock_read_sheet
        mock_client.get_spreadsheet = mock_get_spreadsheet

        return mock_client

    @pytest.fixture
    async def backup_service(self, populated_database, mock_sheets_client):
        """Create BackupService with mocked Google Sheets client."""
        db, _ = populated_database

        config = {
            "backup": {
                "google_sheets": {
                    "enabled": True,
                    "credentials_file": "credentials/google_oauth_credentials.json",
                    "token_file": "credentials/token.json",
                }
            }
        }

        # Patch GoogleSheetsClient to return mock
        with patch("chibi.backup.backup_service.GoogleSheetsClient", return_value=mock_sheets_client):
            service = BackupService(database=db, config=config)
            yield service

    async def test_export_to_sheets_all_data_present(self, backup_service, mock_sheets_client):
        """Test: Export creates spreadsheet with all 5 data tables."""
        # Export
        result = await backup_service.export_progress()

        # Verify result structure
        assert "spreadsheet_url" in result
        assert "spreadsheet_id" in result
        assert "summary" in result

        # Verify all sheets were created
        assert "Metadata" in mock_sheets_client._sheets_data
        assert "Users" in mock_sheets_client._sheets_data
        assert "QuizAttempts" in mock_sheets_client._sheets_data
        assert "ConceptMastery" in mock_sheets_client._sheets_data
        assert "LLMQuizAttempts" in mock_sheets_client._sheets_data
        assert "Attendance" in mock_sheets_client._sheets_data

        # Verify data counts
        users_sheet = mock_sheets_client._sheets_data["Users"]
        assert len(users_sheet) == 4  # Header + 3 users

        quiz_sheet = mock_sheets_client._sheets_data["QuizAttempts"]
        assert len(quiz_sheet) == 11  # Header + 10 attempts

        mastery_sheet = mock_sheets_client._sheets_data["ConceptMastery"]
        assert len(mastery_sheet) == 6  # Header + 5 records

        llm_quiz_sheet = mock_sheets_client._sheets_data["LLMQuizAttempts"]
        assert len(llm_quiz_sheet) == 4  # Header + 3 attempts

        attendance_sheet = mock_sheets_client._sheets_data["Attendance"]
        assert len(attendance_sheet) == 4  # Header + 3 records

        # Verify metadata sheet
        metadata_sheet = mock_sheets_client._sheets_data["Metadata"]
        assert len(metadata_sheet) >= 2  # At least header + data row
        assert any("export_date" in str(row) for row in metadata_sheet)
        assert any("schema_version" in str(row) for row in metadata_sheet)

    async def test_export_clear_import_replace_data_restored(self, backup_service, populated_database, mock_sheets_client):
        """Test: Export, clear database, import with replace mode, verify all data restored."""
        db, original_user_ids = populated_database

        # Step 1: Export
        export_result = await backup_service.export_progress()
        spreadsheet_id = export_result["spreadsheet_id"]

        # Verify original data counts
        cursor = await db.connection.execute("SELECT COUNT(*) FROM users")
        row = await cursor.fetchone()
        assert row[0] == 3

        cursor = await db.connection.execute("SELECT COUNT(*) FROM quiz_attempts")
        row = await cursor.fetchone()
        assert row[0] == 10

        # Step 2: Clear database
        await db.connection.execute("DELETE FROM quiz_attempts")
        await db.connection.execute("DELETE FROM concept_mastery")
        await db.connection.execute("DELETE FROM llm_quiz_attempts")
        await db.connection.execute("DELETE FROM attendance")
        await db.connection.execute("DELETE FROM users")
        await db.connection.commit()

        # Verify database is empty
        cursor = await db.connection.execute("SELECT COUNT(*) FROM users")
        row = await cursor.fetchone()
        assert row[0] == 0

        # Step 3: Import with replace mode
        import_result = await backup_service.import_progress(spreadsheet_id, mode="replace")

        # Verify import summary
        assert import_result["mode"] == "replace"
        assert import_result["status"] == "success"
        assert "counts" in import_result

        # Step 4: Verify all data restored
        cursor = await db.connection.execute("SELECT COUNT(*) FROM users")
        row = await cursor.fetchone()
        assert row[0] == 3

        cursor = await db.connection.execute("SELECT COUNT(*) FROM quiz_attempts")
        row = await cursor.fetchone()
        assert row[0] == 10

        cursor = await db.connection.execute("SELECT COUNT(*) FROM concept_mastery")
        row = await cursor.fetchone()
        assert row[0] == 5

        cursor = await db.connection.execute("SELECT COUNT(*) FROM llm_quiz_attempts")
        row = await cursor.fetchone()
        assert row[0] == 3

        cursor = await db.connection.execute("SELECT COUNT(*) FROM attendance")
        row = await cursor.fetchone()
        assert row[0] == 3

        # Verify specific user data
        cursor = await db.connection.execute(
            "SELECT discord_id, username, student_id FROM users WHERE discord_id = ?",
            ("111111111",)
        )
        user = await cursor.fetchone()
        assert user is not None
        assert user["username"] == "student1"
        assert user["student_id"] == "S001"

    async def test_export_add_user_import_merge_all_users_present(self, backup_service, populated_database, mock_sheets_client):
        """Test: Export with 3 users, delete 1, add 1 new, import with merge, verify 4 users total."""
        db, original_user_ids = populated_database

        # Step 1: Export first (captures all 3 original users)
        export_result = await backup_service.export_progress()
        spreadsheet_id = export_result["spreadsheet_id"]

        # Step 2: Delete one user from database (but it's in the export)
        await db.connection.execute("DELETE FROM quiz_attempts WHERE user_id = ?", (original_user_ids[2],))
        await db.connection.execute("DELETE FROM concept_mastery WHERE user_id = ?", (original_user_ids[2],))
        await db.connection.execute("DELETE FROM llm_quiz_attempts WHERE user_id = ?", (original_user_ids[2],))
        await db.connection.execute("DELETE FROM attendance WHERE user_id = ?", (original_user_ids[2],))
        await db.connection.execute("DELETE FROM users WHERE id = ?", (original_user_ids[2],))
        await db.connection.commit()

        # Verify only 2 users now
        cursor = await db.connection.execute("SELECT COUNT(*) FROM users")
        row = await cursor.fetchone()
        assert row[0] == 2

        # Step 3: Add a new local user that's NOT in the export
        cursor = await db.connection.execute(
            """INSERT INTO users (discord_id, username, student_id, student_name, created_at, last_active)
            VALUES (?, ?, ?, ?, ?, ?)""",
            ("444444444", "student4", "S004", "David Student", "2024-01-11 10:00:00", "2024-01-11 10:00:00")
        )
        new_user_id = cursor.lastrowid
        await db.connection.commit()

        # Verify 3 users locally (2 remaining + 1 new)
        cursor = await db.connection.execute("SELECT COUNT(*) FROM users")
        row = await cursor.fetchone()
        assert row[0] == 3

        # Step 4: Import with merge mode (should restore deleted user from export)
        import_result = await backup_service.import_progress(spreadsheet_id, mode="merge")

        # Verify merge result
        assert import_result["mode"] == "merge"
        assert import_result["status"] == "success"

        # Step 5: Verify all 4 users present (3 from export + 1 new local)
        cursor = await db.connection.execute("SELECT COUNT(*) FROM users")
        row = await cursor.fetchone()
        assert row[0] == 4

        # Verify the new local user is still there
        cursor = await db.connection.execute(
            "SELECT username FROM users WHERE discord_id = ?",
            ("444444444",)
        )
        user = await cursor.fetchone()
        assert user is not None
        assert user["username"] == "student4"

        # Verify the deleted user was restored
        cursor = await db.connection.execute(
            "SELECT username FROM users WHERE discord_id = ?",
            ("333333333",)
        )
        user = await cursor.fetchone()
        assert user is not None
        assert user["username"] == "student3"

    async def test_referential_integrity_maintained(self, backup_service, populated_database, mock_sheets_client):
        """Test: Verify foreign key relationships maintained through export/import cycle."""
        db, original_user_ids = populated_database

        # Export
        export_result = await backup_service.export_progress()
        spreadsheet_id = export_result["spreadsheet_id"]

        # Get original user with related records
        cursor = await db.connection.execute(
            """SELECT u.discord_id, u.username,
                      COUNT(DISTINCT qa.id) as quiz_count,
                      COUNT(DISTINCT cm.id) as mastery_count
               FROM users u
               LEFT JOIN quiz_attempts qa ON u.id = qa.user_id
               LEFT JOIN concept_mastery cm ON u.id = cm.user_id
               WHERE u.discord_id = ?
               GROUP BY u.id""",
            ("111111111",)
        )
        original_user = await cursor.fetchone()
        original_quiz_count = original_user["quiz_count"]
        original_mastery_count = original_user["mastery_count"]

        # Clear database
        await db.connection.execute("DELETE FROM quiz_attempts")
        await db.connection.execute("DELETE FROM concept_mastery")
        await db.connection.execute("DELETE FROM llm_quiz_attempts")
        await db.connection.execute("DELETE FROM attendance")
        await db.connection.execute("DELETE FROM users")
        await db.connection.commit()

        # Import with replace
        await backup_service.import_progress(spreadsheet_id, mode="replace")

        # Verify foreign keys maintained
        cursor = await db.connection.execute(
            """SELECT u.discord_id, u.username,
                      COUNT(DISTINCT qa.id) as quiz_count,
                      COUNT(DISTINCT cm.id) as mastery_count
               FROM users u
               LEFT JOIN quiz_attempts qa ON u.id = qa.user_id
               LEFT JOIN concept_mastery cm ON u.id = cm.user_id
               WHERE u.discord_id = ?
               GROUP BY u.id""",
            ("111111111",)
        )
        restored_user = await cursor.fetchone()

        # Verify counts match
        assert restored_user["quiz_count"] == original_quiz_count
        assert restored_user["mastery_count"] == original_mastery_count

        # Verify all quiz attempts have valid user_id
        cursor = await db.connection.execute(
            """SELECT COUNT(*) FROM quiz_attempts qa
               WHERE NOT EXISTS (SELECT 1 FROM users u WHERE u.id = qa.user_id)"""
        )
        orphaned = await cursor.fetchone()
        assert orphaned[0] == 0, "Found orphaned quiz_attempts with invalid user_id"

        # Verify all concept_mastery records have valid user_id
        cursor = await db.connection.execute(
            """SELECT COUNT(*) FROM concept_mastery cm
               WHERE NOT EXISTS (SELECT 1 FROM users u WHERE u.id = cm.user_id)"""
        )
        orphaned = await cursor.fetchone()
        assert orphaned[0] == 0, "Found orphaned concept_mastery with invalid user_id"


class TestBackupEdgeCases:
    """Test edge cases and error scenarios in backup integration."""

    @pytest.fixture
    async def empty_database(self):
        """Create in-memory database with schema but no data."""
        db = Database(":memory:")
        await db.connect()
        yield db
        await db.close()

    @pytest.fixture
    def mock_sheets_client(self):
        """Mock Google Sheets client."""
        mock_client = MagicMock(spec=GoogleSheetsClient)
        mock_client.create_spreadsheet = MagicMock(return_value="test_spreadsheet_456")
        mock_client._sheets_data = {}

        def mock_write_sheet(spreadsheet_id: str, sheet_name: str, data: List[List[Any]]):
            mock_client._sheets_data[sheet_name] = data
            return {"updated_cells": len(data)}

        def mock_read_sheet(spreadsheet_id: str, sheet_name: str) -> List[List[Any]]:
            return mock_client._sheets_data.get(sheet_name, [])

        def mock_get_spreadsheet(spreadsheet_id: str):
            """Mock get_spreadsheet to return sheet list."""
            # Return structure with sheets that match what was written
            sheets = [{"properties": {"title": name}} for name in mock_client._sheets_data.keys()]
            return {
                "spreadsheetId": spreadsheet_id,
                "properties": {"title": "Test Spreadsheet"},
                "sheets": sheets
            }

        mock_client.write_sheet = mock_write_sheet
        mock_client.read_sheet = mock_read_sheet
        mock_client.get_spreadsheet = mock_get_spreadsheet

        return mock_client

    @pytest.fixture
    async def backup_service_empty(self, empty_database, mock_sheets_client):
        """Create BackupService with empty database."""
        config = {
            "backup": {
                "google_sheets": {
                    "enabled": True,
                    "credentials_file": "credentials/google_oauth_credentials.json",
                    "token_file": "credentials/token.json",
                }
            }
        }

        with patch("chibi.backup.backup_service.GoogleSheetsClient", return_value=mock_sheets_client):
            service = BackupService(database=empty_database, config=config)
            yield service

    async def test_export_empty_database(self, backup_service_empty, mock_sheets_client):
        """Test: Export empty database creates valid structure with zero records."""
        result = await backup_service_empty.export_progress()

        # Should still create spreadsheet with proper structure
        assert "spreadsheet_url" in result

        # Verify sheets exist but only have headers
        users_sheet = mock_sheets_client._sheets_data.get("Users", [])
        assert len(users_sheet) == 1  # Only header row

        quiz_sheet = mock_sheets_client._sheets_data.get("QuizAttempts", [])
        assert len(quiz_sheet) == 1  # Only header row

    async def test_import_with_partial_data(self, backup_service_empty, mock_sheets_client):
        """Test: Import handles sheets with partial data (some tables empty)."""
        # Create export with only users, no quiz attempts
        mock_sheets_client._sheets_data = {
            "Metadata": [
                ["Key", "Value"],
                ["export_date", "2024-01-11 10:00:00"],
                ["schema_version", "1.0"],
            ],
            "Users": [
                ["id", "discord_id", "username", "student_id", "student_name", "created_at", "last_active"],
                [1, "111111111", "student1", "S001", "Alice", "2024-01-01 10:00:00", "2024-01-10 15:00:00"],
            ],
            "QuizAttempts": [
                ["id", "user_id", "module_id", "concept_id", "quiz_format", "question",
                 "user_answer", "correct_answer", "is_correct", "llm_feedback", "llm_quality_score", "created_at"],
            ],
            "ConceptMastery": [
                ["id", "user_id", "concept_id", "total_attempts", "correct_attempts",
                 "avg_quality_score", "mastery_level", "last_attempt_at", "updated_at"],
            ],
            "LLMQuizAttempts": [
                ["id", "user_id", "module_id", "question", "student_answer", "llm_answer",
                 "student_wins", "student_answer_correctness", "evaluation_explanation",
                 "review_status", "reviewed_at", "reviewed_by", "discord_user_id", "created_at"],
            ],
            "Attendance": [
                ["id", "user_id", "username", "timestamp", "date_id", "session_id", "status"],
            ],
        }

        # Import should succeed
        result = await backup_service_empty.import_progress("test_spreadsheet_456", mode="replace")

        assert result["status"] == "success"

        # Verify user was imported
        db = backup_service_empty.database
        cursor = await db.connection.execute("SELECT COUNT(*) FROM users")
        row = await cursor.fetchone()
        assert row[0] == 1

        # Verify other tables remain empty
        cursor = await db.connection.execute("SELECT COUNT(*) FROM quiz_attempts")
        row = await cursor.fetchone()
        assert row[0] == 0

    async def test_data_type_conversions_roundtrip(self, backup_service_empty, mock_sheets_client):
        """Test: Data type conversions are preserved through export/import cycle."""
        db = backup_service_empty.database

        # Insert user with various data types
        await db.connection.execute(
            """INSERT INTO users (discord_id, username, student_id, student_name, created_at, last_active)
            VALUES (?, ?, ?, ?, ?, ?)""",
            ("111111111", "testuser", None, None, "2024-01-01 10:00:00", "2024-01-10 15:00:00")
        )
        cursor = await db.connection.execute("SELECT last_insert_rowid()")
        row = await cursor.fetchone()
        user_id = row[0]

        # Insert quiz attempt with BOOLEAN, NULL, and TEXT
        await db.connection.execute(
            """INSERT INTO quiz_attempts
            (user_id, module_id, concept_id, quiz_format, question, user_answer,
             correct_answer, is_correct, llm_feedback, llm_quality_score, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (user_id, "module01", "concept01", "free-form", "Test question", "Test answer",
             None, 1, None, 85, "2024-01-10 14:00:00")
        )
        await db.connection.commit()

        # Export
        export_result = await backup_service_empty.export_progress()

        # Verify conversions in exported data
        quiz_sheet = mock_sheets_client._sheets_data["QuizAttempts"]
        data_row = quiz_sheet[1]  # First data row (after header)

        # Find is_correct column (should be "TRUE" not "1")
        header_row = quiz_sheet[0]
        is_correct_idx = header_row.index("is_correct")
        assert data_row[is_correct_idx] == "TRUE", "BOOLEAN 1 should export as TRUE"

        # NULL values should be empty strings
        correct_answer_idx = header_row.index("correct_answer")
        assert data_row[correct_answer_idx] == "", "NULL should export as empty string"

        # Clear and import
        await db.connection.execute("DELETE FROM quiz_attempts")
        await db.connection.execute("DELETE FROM users")
        await db.connection.commit()

        await backup_service_empty.import_progress(export_result["spreadsheet_id"], mode="replace")

        # Verify conversions back
        cursor = await db.connection.execute(
            "SELECT is_correct, correct_answer, llm_feedback FROM quiz_attempts"
        )
        row = await cursor.fetchone()

        assert row["is_correct"] == 1, "TRUE should import as 1"
        assert row["correct_answer"] is None, "Empty string should import as NULL"
        assert row["llm_feedback"] is None, "Empty string should import as NULL"
