"""
BackupService - Orchestrates backup operations for student progress data.

This service coordinates export, import, and listing operations by delegating to:
- GoogleSheetsClient: OAuth and Sheets API operations
- SheetsExporter: SQLite to Sheets data transformation
- SheetsImporter: Sheets to SQLite data transformation

Usage:
    service = BackupService(database, sheets_client, config)

    # Export student progress to Google Sheets
    result = await service.export_progress()
    print(f"Exported to: {result['spreadsheet_url']}")

    # Import from Google Sheets with replace mode
    result = await service.import_progress(spreadsheet_url, mode='replace')

    # Import with merge mode (updates existing, inserts new)
    result = await service.import_progress(spreadsheet_url, mode='merge')

    # List recent exports
    exports = await service.list_recent_exports(limit=10)
"""

import logging
from typing import Dict, List, Any, Optional
from chibi.backup.google_sheets_client import GoogleSheetsClient
from chibi.backup.sheets_exporter import SheetsExporter
from chibi.backup.sheets_importer import SheetsImporter
from chibi.database.connection import Database

logger = logging.getLogger(__name__)


class BackupService:
    """Service layer for orchestrating backup operations.

    Coordinates export and import operations by delegating to specialized
    components (exporter, importer, sheets client).

    Attributes:
        database: SQLite database connection
        sheets_client: Google Sheets API client
        config: Bot configuration dictionary
        exporter: SheetsExporter instance for export operations
        importer: SheetsImporter instance for import operations
    """

    def __init__(
        self,
        database: Database,
        sheets_client: Optional[GoogleSheetsClient] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        """Initialize BackupService with dependencies.

        Args:
            database: Database instance for accessing student data
            sheets_client: Optional GoogleSheetsClient (created if None)
            config: Configuration dictionary with backup settings
        """
        self.database = database
        self.config = config or {}

        # Initialize or use provided sheets client
        if sheets_client is None:
            backup_config = self.config.get('backup', {}).get('google_sheets', {})
            self.sheets_client = GoogleSheetsClient(
                credentials_file=backup_config.get('credentials_file', 'credentials/google_oauth_credentials.json'),
                token_file=backup_config.get('token_file', 'credentials/token.json'),
                scopes=backup_config.get('scopes', [
                    'https://www.googleapis.com/auth/spreadsheets',
                    'https://www.googleapis.com/auth/drive.file'
                ])
            )
        else:
            self.sheets_client = sheets_client

        # Initialize exporter and importer
        self.exporter = SheetsExporter(
            database=self.database,
            sheets_client=self.sheets_client
        )

        self.importer = SheetsImporter(
            database=self.database,
            sheets_client=self.sheets_client
        )

        logger.info("BackupService initialized")

    async def export_progress(self) -> Dict[str, Any]:
        """Export all student progress data to Google Sheets.

        Creates a new spreadsheet with all student data including:
        - Users (Discord profiles and student registration)
        - Quiz attempts with LLM feedback
        - Concept mastery tracking
        - LLM quiz challenge attempts
        - Attendance records

        Returns:
            Dict with keys:
                - spreadsheet_id: Google Sheets ID
                - spreadsheet_url: Full URL to spreadsheet
                - export_date: ISO timestamp of export
                - schema_version: Database schema version
                - summary: Dict with counts for each table

        Raises:
            Exception: If database read or Sheets API fails
        """
        logger.info("Starting export of student progress data")

        try:
            # Delegate to exporter
            result = await self.exporter.export_to_sheets()

            logger.info(
                f"Export completed successfully. "
                f"Spreadsheet ID: {result['spreadsheet_id']}, "
                f"URL: {result['spreadsheet_url']}"
            )

            # Log summary counts
            if 'summary' in result:
                summary = result['summary']
                logger.info(
                    f"Exported {summary.get('users', 0)} users, "
                    f"{summary.get('quiz_attempts', 0)} quiz attempts, "
                    f"{summary.get('concept_mastery', 0)} mastery records, "
                    f"{summary.get('llm_quiz_attempts', 0)} LLM quiz attempts, "
                    f"{summary.get('attendance', 0)} attendance records"
                )

            return result

        except Exception as e:
            logger.error(f"Export failed: {e}", exc_info=True)
            raise

    async def import_progress(
        self,
        spreadsheet_url: str,
        mode: str = 'replace'
    ) -> Dict[str, Any]:
        """Import student progress data from Google Sheets.

        Args:
            spreadsheet_url: Google Sheets URL or spreadsheet ID
            mode: Import mode - 'replace' (delete all then insert) or 'merge' (upsert)

        Returns:
            Dict with keys:
                - mode: Import mode used
                - spreadsheet_id: Source spreadsheet ID
                - import_date: ISO timestamp of import
                - schema_version: Imported schema version
                - summary: Dict with counts for each table
                - status: 'success' or error message

        Raises:
            ValueError: If spreadsheet URL is invalid or schema mismatch
            Exception: If import transaction fails
        """
        logger.info(
            f"Starting import from spreadsheet with mode={mode}: {spreadsheet_url}"
        )

        try:
            # Delegate to importer (using positional arg to match test expectations)
            result = await self.importer.import_from_sheets(
                spreadsheet_url, mode=mode
            )

            logger.info(
                f"Import completed successfully with mode={result.get('mode', mode)}. "
                f"Spreadsheet ID: {result.get('spreadsheet_id', 'unknown')}"
            )

            # Log summary counts
            if 'summary' in result:
                summary = result['summary']
                logger.info(
                    f"Imported {summary.get('users', 0)} users, "
                    f"{summary.get('quiz_attempts', 0)} quiz attempts, "
                    f"{summary.get('concept_mastery', 0)} mastery records, "
                    f"{summary.get('llm_quiz_attempts', 0)} LLM quiz attempts, "
                    f"{summary.get('attendance', 0)} attendance records"
                )

            return result

        except ValueError as e:
            logger.error(f"Import validation failed: {e}")
            raise
        except Exception as e:
            logger.error(f"Import failed: {e}", exc_info=True)
            raise

    async def list_recent_exports(self, limit: int = 10) -> List[Dict[str, Any]]:
        """List recent export spreadsheets.

        Queries Google Drive for spreadsheets with "Chibi Student Progress" in the name,
        sorted by creation date (newest first).

        Args:
            limit: Maximum number of exports to return (default: 10)

        Returns:
            List of dicts with keys:
                - id: Spreadsheet ID
                - name: Spreadsheet name
                - url: Full URL to spreadsheet
                - created_time: ISO timestamp of creation

        Raises:
            Exception: If Google Sheets API fails
        """
        logger.info(f"Listing recent exports (limit={limit})")

        try:
            # Query for spreadsheets with "Chibi Student Progress" in name
            query = "name contains 'Chibi Student Progress'"
            spreadsheets = await self.sheets_client.list_spreadsheets(query=query)

            # Return up to limit results (sheets_client should handle sorting)
            result = spreadsheets[:limit] if spreadsheets else []

            logger.info(f"Found {len(result)} recent exports")

            return result

        except Exception as e:
            logger.error(f"Failed to list exports: {e}", exc_info=True)
            raise
