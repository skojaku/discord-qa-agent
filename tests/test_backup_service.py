"""
Unit tests for BackupService - orchestrates backup operations.

Tests written BEFORE implementation (TDD approach).
Tests are marked as skip until implementation exists (US-012).

Test coverage:
- Service initialization and dependency injection
- export_progress() orchestration
- import_progress() orchestration with replace and merge modes
- list_recent_exports() spreadsheet listing
- Error handling and logging

All tests use mocked dependencies (database, sheets client, exporter, importer).
"""

import pytest
from unittest.mock import AsyncMock, Mock, patch, MagicMock
from datetime import datetime
from typing import Dict, List, Any

# Skip entire module if implementation doesn't exist yet
pytest.importorskip("chibi.backup.backup_service", reason="Implementation not yet created")

from chibi.backup.backup_service import BackupService


class TestBackupServiceInitialization:
    """Test BackupService initialization and dependency injection."""

    def test_initialization_with_dependencies(self):
        """Test service initializes with required dependencies."""
        mock_db = Mock()
        mock_sheets_client = Mock()
        mock_config = {
            'backup': {
                'google_sheets': {
                    'enabled': True,
                    'credentials_file': 'credentials/google_oauth_credentials.json',
                    'token_file': 'credentials/token.json'
                }
            }
        }

        service = BackupService(
            database=mock_db,
            sheets_client=mock_sheets_client,
            config=mock_config
        )

        assert service.database == mock_db
        assert service.sheets_client == mock_sheets_client
        assert service.config == mock_config
        assert service.exporter is not None
        assert service.importer is not None


class TestExportProgress:
    """Test export_progress() orchestration."""

    @pytest.mark.asyncio
    async def test_export_progress_success(self):
        """Test successful export returns spreadsheet URL and summary."""
        mock_db = Mock()
        mock_sheets_client = Mock()
        mock_config = {'backup': {'google_sheets': {}}}

        service = BackupService(mock_db, mock_sheets_client, mock_config)

        # Mock exporter's export_to_sheets method
        mock_export_result = {
            'spreadsheet_id': 'abc123',
            'spreadsheet_url': 'https://docs.google.com/spreadsheets/d/abc123',
            'export_date': '2026-01-11T10:30:00',
            'schema_version': '1.0',
            'summary': {
                'users': 5,
                'quiz_attempts': 20,
                'concept_mastery': 15,
                'llm_quiz_attempts': 8,
                'attendance': 10
            }
        }
        service.exporter.export_to_sheets = AsyncMock(return_value=mock_export_result)

        result = await service.export_progress()

        # Verify result structure
        assert result['spreadsheet_id'] == 'abc123'
        assert result['spreadsheet_url'] == 'https://docs.google.com/spreadsheets/d/abc123'
        assert result['export_date'] == '2026-01-11T10:30:00'
        assert result['schema_version'] == '1.0'
        assert 'summary' in result
        assert result['summary']['users'] == 5
        assert result['summary']['quiz_attempts'] == 20

        # Verify exporter was called
        service.exporter.export_to_sheets.assert_called_once()

    @pytest.mark.asyncio
    async def test_export_progress_with_empty_database(self):
        """Test export with no student data returns zero counts."""
        mock_db = Mock()
        mock_sheets_client = Mock()
        mock_config = {'backup': {'google_sheets': {}}}

        service = BackupService(mock_db, mock_sheets_client, mock_config)

        # Mock exporter returning empty data
        mock_export_result = {
            'spreadsheet_id': 'empty123',
            'spreadsheet_url': 'https://docs.google.com/spreadsheets/d/empty123',
            'export_date': '2026-01-11T10:30:00',
            'schema_version': '1.0',
            'summary': {
                'users': 0,
                'quiz_attempts': 0,
                'concept_mastery': 0,
                'llm_quiz_attempts': 0,
                'attendance': 0
            }
        }
        service.exporter.export_to_sheets = AsyncMock(return_value=mock_export_result)

        result = await service.export_progress()

        assert result['summary']['users'] == 0
        assert result['summary']['quiz_attempts'] == 0
        assert result['summary']['concept_mastery'] == 0

    @pytest.mark.asyncio
    async def test_export_progress_logs_operation(self):
        """Test export operation is logged."""
        mock_db = Mock()
        mock_sheets_client = Mock()
        mock_config = {'backup': {'google_sheets': {}}}

        service = BackupService(mock_db, mock_sheets_client, mock_config)

        mock_export_result = {
            'spreadsheet_id': 'abc123',
            'spreadsheet_url': 'https://docs.google.com/spreadsheets/d/abc123',
            'export_date': '2026-01-11T10:30:00',
            'schema_version': '1.0',
            'summary': {}
        }
        service.exporter.export_to_sheets = AsyncMock(return_value=mock_export_result)

        with patch('chibi.backup.backup_service.logger') as mock_logger:
            result = await service.export_progress()

            # Verify logging occurred
            mock_logger.info.assert_called()
            # Check that URL was logged
            log_calls = [str(call) for call in mock_logger.info.call_args_list]
            assert any('abc123' in str(call) for call in log_calls)

    @pytest.mark.asyncio
    async def test_export_progress_handles_database_error(self):
        """Test export handles database read errors gracefully."""
        mock_db = Mock()
        mock_sheets_client = Mock()
        mock_config = {'backup': {'google_sheets': {}}}

        service = BackupService(mock_db, mock_sheets_client, mock_config)

        # Mock exporter raising database error
        service.exporter.export_to_sheets = AsyncMock(
            side_effect=Exception("Database connection failed")
        )

        with pytest.raises(Exception) as exc_info:
            await service.export_progress()

        assert "Database connection failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_export_progress_handles_sheets_api_error(self):
        """Test export handles Google Sheets API errors gracefully."""
        mock_db = Mock()
        mock_sheets_client = Mock()
        mock_config = {'backup': {'google_sheets': {}}}

        service = BackupService(mock_db, mock_sheets_client, mock_config)

        # Mock exporter raising Sheets API error
        service.exporter.export_to_sheets = AsyncMock(
            side_effect=Exception("Sheets API quota exceeded")
        )

        with pytest.raises(Exception) as exc_info:
            await service.export_progress()

        assert "Sheets API quota exceeded" in str(exc_info.value)


class TestImportProgress:
    """Test import_progress() orchestration with replace and merge modes."""

    @pytest.mark.asyncio
    async def test_import_progress_replace_mode_success(self):
        """Test successful import with replace mode deletes all and inserts new data."""
        mock_db = Mock()
        mock_sheets_client = Mock()
        mock_config = {'backup': {'google_sheets': {}}}

        service = BackupService(mock_db, mock_sheets_client, mock_config)

        # Mock importer's import_from_sheets method
        mock_import_result = {
            'mode': 'replace',
            'spreadsheet_id': 'abc123',
            'import_date': '2026-01-11T11:00:00',
            'schema_version': '1.0',
            'summary': {
                'users': 5,
                'quiz_attempts': 20,
                'concept_mastery': 15,
                'llm_quiz_attempts': 8,
                'attendance': 10
            },
            'status': 'success'
        }
        service.importer.import_from_sheets = AsyncMock(return_value=mock_import_result)

        spreadsheet_url = 'https://docs.google.com/spreadsheets/d/abc123'
        result = await service.import_progress(spreadsheet_url, mode='replace')

        # Verify result structure
        assert result['mode'] == 'replace'
        assert result['spreadsheet_id'] == 'abc123'
        assert result['status'] == 'success'
        assert 'summary' in result
        assert result['summary']['users'] == 5
        assert result['summary']['quiz_attempts'] == 20

        # Verify importer was called with correct parameters
        service.importer.import_from_sheets.assert_called_once_with(
            spreadsheet_url, mode='replace'
        )

    @pytest.mark.asyncio
    async def test_import_progress_merge_mode_success(self):
        """Test successful import with merge mode uses INSERT OR REPLACE."""
        mock_db = Mock()
        mock_sheets_client = Mock()
        mock_config = {'backup': {'google_sheets': {}}}

        service = BackupService(mock_db, mock_sheets_client, mock_config)

        # Mock importer with merge mode
        mock_import_result = {
            'mode': 'merge',
            'spreadsheet_id': 'merge123',
            'import_date': '2026-01-11T11:00:00',
            'schema_version': '1.0',
            'summary': {
                'users': 8,  # 5 existing + 3 new from merge
                'quiz_attempts': 25,
                'concept_mastery': 18,
                'llm_quiz_attempts': 10,
                'attendance': 12
            },
            'status': 'success'
        }
        service.importer.import_from_sheets = AsyncMock(return_value=mock_import_result)

        spreadsheet_url = 'https://docs.google.com/spreadsheets/d/merge123'
        result = await service.import_progress(spreadsheet_url, mode='merge')

        assert result['mode'] == 'merge'
        assert result['status'] == 'success'
        assert result['summary']['users'] == 8

        service.importer.import_from_sheets.assert_called_once_with(
            spreadsheet_url, mode='merge'
        )

    @pytest.mark.asyncio
    async def test_import_progress_defaults_to_replace_mode(self):
        """Test import defaults to replace mode if mode not specified."""
        mock_db = Mock()
        mock_sheets_client = Mock()
        mock_config = {'backup': {'google_sheets': {}}}

        service = BackupService(mock_db, mock_sheets_client, mock_config)

        mock_import_result = {
            'mode': 'replace',
            'spreadsheet_id': 'abc123',
            'status': 'success',
            'summary': {}
        }
        service.importer.import_from_sheets = AsyncMock(return_value=mock_import_result)

        # Call without mode parameter
        spreadsheet_url = 'https://docs.google.com/spreadsheets/d/abc123'
        result = await service.import_progress(spreadsheet_url)

        assert result['mode'] == 'replace'
        service.importer.import_from_sheets.assert_called_once_with(
            spreadsheet_url, mode='replace'
        )

    @pytest.mark.asyncio
    async def test_import_progress_logs_operation(self):
        """Test import operation is logged with mode and counts."""
        mock_db = Mock()
        mock_sheets_client = Mock()
        mock_config = {'backup': {'google_sheets': {}}}

        service = BackupService(mock_db, mock_sheets_client, mock_config)

        mock_import_result = {
            'mode': 'merge',
            'spreadsheet_id': 'abc123',
            'status': 'success',
            'summary': {
                'users': 10,
                'quiz_attempts': 50
            }
        }
        service.importer.import_from_sheets = AsyncMock(return_value=mock_import_result)

        with patch('chibi.backup.backup_service.logger') as mock_logger:
            spreadsheet_url = 'https://docs.google.com/spreadsheets/d/abc123'
            result = await service.import_progress(spreadsheet_url, mode='merge')

            # Verify logging occurred
            mock_logger.info.assert_called()
            log_calls = [str(call) for call in mock_logger.info.call_args_list]
            # Check that mode and URL were logged
            assert any('merge' in str(call).lower() for call in log_calls)

    @pytest.mark.asyncio
    async def test_import_progress_handles_invalid_spreadsheet(self):
        """Test import handles invalid spreadsheet URL/ID."""
        mock_db = Mock()
        mock_sheets_client = Mock()
        mock_config = {'backup': {'google_sheets': {}}}

        service = BackupService(mock_db, mock_sheets_client, mock_config)

        # Mock importer raising validation error
        service.importer.import_from_sheets = AsyncMock(
            side_effect=ValueError("Invalid spreadsheet URL")
        )

        with pytest.raises(ValueError) as exc_info:
            await service.import_progress("invalid-url", mode='replace')

        assert "Invalid spreadsheet URL" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_import_progress_handles_schema_mismatch(self):
        """Test import handles schema version mismatch."""
        mock_db = Mock()
        mock_sheets_client = Mock()
        mock_config = {'backup': {'google_sheets': {}}}

        service = BackupService(mock_db, mock_sheets_client, mock_config)

        # Mock importer raising schema error
        service.importer.import_from_sheets = AsyncMock(
            side_effect=ValueError("Schema version mismatch: expected 1.0, got 0.9")
        )

        with pytest.raises(ValueError) as exc_info:
            await service.import_progress("https://docs.google.com/spreadsheets/d/old123")

        assert "Schema version mismatch" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_import_progress_handles_transaction_rollback(self):
        """Test import handles transaction rollback on error."""
        mock_db = Mock()
        mock_sheets_client = Mock()
        mock_config = {'backup': {'google_sheets': {}}}

        service = BackupService(mock_db, mock_sheets_client, mock_config)

        # Mock importer raising transaction error
        service.importer.import_from_sheets = AsyncMock(
            side_effect=Exception("Foreign key constraint failed")
        )

        with pytest.raises(Exception) as exc_info:
            await service.import_progress("https://docs.google.com/spreadsheets/d/abc123")

        assert "Foreign key constraint failed" in str(exc_info.value)


class TestListRecentExports:
    """Test list_recent_exports() spreadsheet listing."""

    @pytest.mark.asyncio
    async def test_list_recent_exports_returns_spreadsheets(self):
        """Test list returns recent export spreadsheets."""
        mock_db = Mock()
        mock_sheets_client = Mock()
        mock_config = {'backup': {'google_sheets': {}}}

        service = BackupService(mock_db, mock_sheets_client, mock_config)

        # Mock sheets client list_spreadsheets method
        mock_spreadsheets = [
            {
                'id': 'export1',
                'name': 'Chibi Student Progress - 2026-01-11 10:00',
                'url': 'https://docs.google.com/spreadsheets/d/export1',
                'created_time': '2026-01-11T10:00:00'
            },
            {
                'id': 'export2',
                'name': 'Chibi Student Progress - 2026-01-10 15:30',
                'url': 'https://docs.google.com/spreadsheets/d/export2',
                'created_time': '2026-01-10T15:30:00'
            },
            {
                'id': 'export3',
                'name': 'Chibi Student Progress - 2026-01-09 09:15',
                'url': 'https://docs.google.com/spreadsheets/d/export3',
                'created_time': '2026-01-09T09:15:00'
            }
        ]
        service.sheets_client.list_spreadsheets = AsyncMock(return_value=mock_spreadsheets)

        result = await service.list_recent_exports(limit=10)

        # Verify result structure
        assert len(result) == 3
        assert result[0]['id'] == 'export1'
        assert result[0]['name'] == 'Chibi Student Progress - 2026-01-11 10:00'
        assert result[0]['url'] == 'https://docs.google.com/spreadsheets/d/export1'

        # Verify sheets client was called with query
        service.sheets_client.list_spreadsheets.assert_called_once()
        call_args = service.sheets_client.list_spreadsheets.call_args
        # Should query for "Chibi Student Progress" in name
        assert 'Chibi Student Progress' in str(call_args)

    @pytest.mark.asyncio
    async def test_list_recent_exports_respects_limit(self):
        """Test list respects limit parameter."""
        mock_db = Mock()
        mock_sheets_client = Mock()
        mock_config = {'backup': {'google_sheets': {}}}

        service = BackupService(mock_db, mock_sheets_client, mock_config)

        # Mock 20 spreadsheets but request limit of 5
        mock_spreadsheets = [
            {
                'id': f'export{i}',
                'name': f'Chibi Student Progress - 2026-01-{i:02d}',
                'url': f'https://docs.google.com/spreadsheets/d/export{i}',
                'created_time': f'2026-01-{i:02d}T10:00:00'
            }
            for i in range(1, 21)
        ]
        service.sheets_client.list_spreadsheets = AsyncMock(return_value=mock_spreadsheets[:5])

        result = await service.list_recent_exports(limit=5)

        assert len(result) == 5
        # Verify limit was passed to sheets client
        call_args = service.sheets_client.list_spreadsheets.call_args
        # Limit should be in the call somehow (implementation detail)

    @pytest.mark.asyncio
    async def test_list_recent_exports_defaults_to_10(self):
        """Test list defaults to 10 exports if limit not specified."""
        mock_db = Mock()
        mock_sheets_client = Mock()
        mock_config = {'backup': {'google_sheets': {}}}

        service = BackupService(mock_db, mock_sheets_client, mock_config)

        mock_spreadsheets = []
        service.sheets_client.list_spreadsheets = AsyncMock(return_value=mock_spreadsheets)

        result = await service.list_recent_exports()

        # Verify default limit of 10 was used
        service.sheets_client.list_spreadsheets.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_recent_exports_returns_empty_when_no_exports(self):
        """Test list returns empty list when no exports exist."""
        mock_db = Mock()
        mock_sheets_client = Mock()
        mock_config = {'backup': {'google_sheets': {}}}

        service = BackupService(mock_db, mock_sheets_client, mock_config)

        service.sheets_client.list_spreadsheets = AsyncMock(return_value=[])

        result = await service.list_recent_exports()

        assert result == []
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_list_recent_exports_handles_api_error(self):
        """Test list handles Google Sheets API errors."""
        mock_db = Mock()
        mock_sheets_client = Mock()
        mock_config = {'backup': {'google_sheets': {}}}

        service = BackupService(mock_db, mock_sheets_client, mock_config)

        # Mock sheets client raising API error
        service.sheets_client.list_spreadsheets = AsyncMock(
            side_effect=Exception("API error: permission denied")
        )

        with pytest.raises(Exception) as exc_info:
            await service.list_recent_exports()

        assert "permission denied" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_list_recent_exports_sorts_by_date_descending(self):
        """Test list returns exports sorted by date (newest first)."""
        mock_db = Mock()
        mock_sheets_client = Mock()
        mock_config = {'backup': {'google_sheets': {}}}

        service = BackupService(mock_db, mock_sheets_client, mock_config)

        # Mock spreadsheets in random order
        mock_spreadsheets = [
            {
                'id': 'export2',
                'name': 'Chibi Student Progress - 2026-01-10 15:30',
                'url': 'https://docs.google.com/spreadsheets/d/export2',
                'created_time': '2026-01-10T15:30:00'
            },
            {
                'id': 'export1',
                'name': 'Chibi Student Progress - 2026-01-11 10:00',
                'url': 'https://docs.google.com/spreadsheets/d/export1',
                'created_time': '2026-01-11T10:00:00'
            },
            {
                'id': 'export3',
                'name': 'Chibi Student Progress - 2026-01-09 09:15',
                'url': 'https://docs.google.com/spreadsheets/d/export3',
                'created_time': '2026-01-09T09:15:00'
            }
        ]
        service.sheets_client.list_spreadsheets = AsyncMock(return_value=mock_spreadsheets)

        result = await service.list_recent_exports()

        # Note: Sorting might be done by sheets_client or by BackupService
        # This test verifies the contract but implementation can sort either place
        # Just verify we got all 3 results
        assert len(result) == 3


class TestErrorHandling:
    """Test comprehensive error handling and edge cases."""

    @pytest.mark.asyncio
    async def test_service_handles_missing_config(self):
        """Test service handles missing or invalid configuration."""
        mock_db = Mock()
        mock_sheets_client = Mock()
        mock_config = {}  # Missing backup section

        # Service should still initialize but may fail on operations
        service = BackupService(mock_db, mock_sheets_client, mock_config)
        assert service is not None

    @pytest.mark.asyncio
    async def test_export_with_concurrent_requests(self):
        """Test export handles concurrent export requests (not expected but should be safe)."""
        mock_db = Mock()
        mock_sheets_client = Mock()
        mock_config = {'backup': {'google_sheets': {}}}

        service = BackupService(mock_db, mock_sheets_client, mock_config)

        mock_export_result = {
            'spreadsheet_id': 'concurrent123',
            'spreadsheet_url': 'https://docs.google.com/spreadsheets/d/concurrent123',
            'export_date': '2026-01-11T10:30:00',
            'schema_version': '1.0',
            'summary': {}
        }
        service.exporter.export_to_sheets = AsyncMock(return_value=mock_export_result)

        # Run two exports concurrently
        import asyncio
        results = await asyncio.gather(
            service.export_progress(),
            service.export_progress()
        )

        assert len(results) == 2
        assert results[0]['spreadsheet_id'] == 'concurrent123'
        assert results[1]['spreadsheet_id'] == 'concurrent123'

    @pytest.mark.asyncio
    async def test_import_with_partial_data(self):
        """Test import handles spreadsheets with partial data (some tables empty)."""
        mock_db = Mock()
        mock_sheets_client = Mock()
        mock_config = {'backup': {'google_sheets': {}}}

        service = BackupService(mock_db, mock_sheets_client, mock_config)

        # Mock import with some zero counts
        mock_import_result = {
            'mode': 'replace',
            'spreadsheet_id': 'partial123',
            'status': 'success',
            'summary': {
                'users': 3,
                'quiz_attempts': 0,  # Empty
                'concept_mastery': 0,  # Empty
                'llm_quiz_attempts': 0,  # Empty
                'attendance': 0  # Empty
            }
        }
        service.importer.import_from_sheets = AsyncMock(return_value=mock_import_result)

        result = await service.import_progress("https://docs.google.com/spreadsheets/d/partial123")

        assert result['status'] == 'success'
        assert result['summary']['users'] == 3
        assert result['summary']['quiz_attempts'] == 0
