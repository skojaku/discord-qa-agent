"""Unit tests for Google Sheets OAuth client.

These tests verify the OAuth 2.0 authentication flow, token management,
and Google Sheets API operations before implementation.
"""

import json
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch, mock_open

from chibi.backup.google_sheets_client import GoogleSheetsClient


class TestOAuthFlow:
    """Test OAuth 2.0 authentication flow."""

    def test_oauth_initialization_with_credentials_file(self):
        """
        Test OAuth client initialization with credentials file.

        Given: A valid credentials JSON file exists
        When: GoogleSheetsClient is initialized
        Then: OAuth flow should be set up with correct scopes
        """

        # Mock credentials file
        credentials_path = "credentials/google_oauth_credentials.json"
        token_path = "credentials/token.json"
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive.file",
        ]

        with patch("pathlib.Path.exists", return_value=True):
            client = GoogleSheetsClient(
                credentials_file=credentials_path,
                token_file=token_path,
                scopes=scopes,
            )

            assert client.credentials_file == credentials_path
            assert client.token_file == token_path
            assert client.scopes == scopes

    def test_oauth_initialization_missing_credentials_file(self):
        """
        Test OAuth client initialization fails with missing credentials.

        Given: Credentials file does not exist
        When: GoogleSheetsClient is initialized
        Then: Should raise FileNotFoundError
        """

        credentials_path = "credentials/missing.json"

        with pytest.raises(FileNotFoundError):
            GoogleSheetsClient(credentials_file=credentials_path)

    @patch("gspread.authorize")
    @patch("google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file")
    @patch("chibi.backup.google_sheets_client.Path.exists")
    def test_oauth_flow_first_time_auth(self, mock_exists, mock_flow, mock_authorize):
        """
        Test OAuth flow for first-time authentication (no token file).

        Given: No token.json file exists
        When: Client attempts authentication
        Then: Should initiate browser-based OAuth flow
        And: Should save token to token.json
        """
        # Mock OAuth flow
        mock_flow_instance = MagicMock()
        mock_credentials = MagicMock()
        mock_credentials.valid = True
        mock_credentials.expired = False
        mock_credentials.to_json.return_value = json.dumps({"token": "test_token"})
        mock_flow_instance.run_local_server.return_value = mock_credentials
        mock_flow.return_value = mock_flow_instance

        # Mock gspread
        mock_gc = MagicMock()
        mock_authorize.return_value = mock_gc

        # Mock path exists: First call checks creds.json (exists), second call checks token.json (doesn't exist)
        mock_exists.side_effect = [True, False]

        client = GoogleSheetsClient(credentials_file="creds.json")
        client.authenticate()

        # Verify OAuth flow was initiated
        mock_flow.assert_called_once()
        mock_flow_instance.run_local_server.assert_called_once()

    @patch("gspread.authorize")
    @patch("google.auth.transport.requests.Request")
    @patch("google.oauth2.credentials.Credentials.from_authorized_user_file")
    @patch("chibi.backup.google_sheets_client.Path.exists", return_value=True)
    def test_oauth_token_refresh(self, mock_exists, mock_from_file, mock_request, mock_authorize):
        """
        Test automatic token refresh when expired.

        Given: An expired token exists in token.json
        When: Client authenticates
        Then: Should automatically refresh the token
        And: Should save refreshed token to token.json
        """
        # Mock expired credentials
        mock_credentials = MagicMock()
        mock_credentials.valid = False
        mock_credentials.expired = True
        mock_credentials.refresh_token = "refresh_token"
        mock_credentials.to_json.return_value = json.dumps({"token": "refreshed_token"})
        mock_from_file.return_value = mock_credentials

        # After refresh, credentials become valid
        def refresh_side_effect(request):
            mock_credentials.valid = True
            mock_credentials.expired = False

        mock_credentials.refresh.side_effect = refresh_side_effect

        # Mock gspread
        mock_gc = MagicMock()
        mock_authorize.return_value = mock_gc

        client = GoogleSheetsClient(credentials_file="creds.json")
        client.authenticate()

        # Verify token refresh was called
        mock_credentials.refresh.assert_called_once()

    @patch("gspread.authorize")
    @patch("google.oauth2.credentials.Credentials.from_authorized_user_file")
    @patch("chibi.backup.google_sheets_client.Path.exists", return_value=True)
    def test_oauth_valid_token_reuse(self, mock_exists, mock_from_file, mock_authorize):
        """
        Test reusing valid token without refresh.

        Given: A valid, non-expired token exists
        When: Client authenticates
        Then: Should reuse existing token without refresh
        """
        # Mock valid credentials
        mock_credentials = MagicMock()
        mock_credentials.valid = True
        mock_credentials.expired = False
        mock_from_file.return_value = mock_credentials

        # Mock gspread
        mock_gc = MagicMock()
        mock_authorize.return_value = mock_gc

        client = GoogleSheetsClient(credentials_file="creds.json")
        client.authenticate()

        # Should not refresh or run OAuth flow
        mock_credentials.refresh.assert_not_called()


class TestSpreadsheetOperations:
    """Test Google Sheets CRUD operations."""

    @patch("gspread.authorize")
    @patch("chibi.backup.google_sheets_client.Path.exists", return_value=True)
    def test_create_spreadsheet(self, mock_exists, mock_authorize):
        """
        Test creating a new spreadsheet.

        Given: An authenticated client
        When: create_spreadsheet is called with a title
        Then: Should create a spreadsheet and return its ID
        """
        # Mock gspread client
        mock_gc = MagicMock()
        mock_spreadsheet = MagicMock()
        mock_spreadsheet.id = "test_spreadsheet_id_123"
        mock_gc.create.return_value = mock_spreadsheet
        mock_authorize.return_value = mock_gc

        client = GoogleSheetsClient(credentials_file="creds.json")
        client.gc = mock_gc  # Set the gspread client directly
        spreadsheet_id = client.create_spreadsheet("Test Spreadsheet")

        assert spreadsheet_id == "test_spreadsheet_id_123"
        mock_gc.create.assert_called_once_with("Test Spreadsheet")

    @patch("gspread.authorize")
    @patch("chibi.backup.google_sheets_client.Path.exists", return_value=True)
    def test_get_spreadsheet(self, mock_exists, mock_authorize):
        """
        Test retrieving an existing spreadsheet.

        Given: A spreadsheet ID exists
        When: get_spreadsheet is called
        Then: Should return spreadsheet object
        """
        # Mock gspread client
        mock_gc = MagicMock()
        mock_spreadsheet = MagicMock()
        mock_spreadsheet.id = "test_id"
        mock_spreadsheet.title = "Test Spreadsheet"
        mock_gc.open_by_key.return_value = mock_spreadsheet
        mock_authorize.return_value = mock_gc

        client = GoogleSheetsClient(credentials_file="creds.json")
        client.gc = mock_gc  # Set the gspread client directly
        spreadsheet = client.get_spreadsheet("test_id")

        assert spreadsheet.id == "test_id"
        mock_gc.open_by_key.assert_called_once_with("test_id")

    @patch("gspread.authorize")
    @patch("chibi.backup.google_sheets_client.Path.exists", return_value=True)
    def test_write_sheet(self, mock_exists, mock_authorize):
        """
        Test writing data to a sheet.

        Given: A spreadsheet exists
        When: write_sheet is called with data
        Then: Should write data to specified sheet
        """
        # Mock gspread client and spreadsheet
        mock_gc = MagicMock()
        mock_spreadsheet = MagicMock()
        mock_worksheet = MagicMock()
        mock_spreadsheet.worksheet.return_value = mock_worksheet
        mock_gc.open_by_key.return_value = mock_spreadsheet
        mock_authorize.return_value = mock_gc

        test_data = [
            ["Name", "Age", "City"],
            ["Alice", "25", "New York"],
            ["Bob", "30", "San Francisco"],
        ]

        client = GoogleSheetsClient(credentials_file="creds.json")
        client.gc = mock_gc  # Set the gspread client directly
        client.write_sheet("test_id", "Sheet1", test_data)

        mock_spreadsheet.worksheet.assert_called_once_with("Sheet1")
        mock_worksheet.update.assert_called_once()

    @patch("gspread.authorize")
    @patch("chibi.backup.google_sheets_client.Path.exists", return_value=True)
    def test_write_sheet_creates_sheet_if_not_exists(self, mock_exists, mock_authorize):
        """
        Test writing to a non-existent sheet creates it.

        Given: A sheet name that doesn't exist
        When: write_sheet is called
        Then: Should create the sheet before writing
        """
        # Mock gspread client
        mock_gc = MagicMock()
        mock_spreadsheet = MagicMock()
        mock_worksheet = MagicMock()

        # First call to worksheet raises exception (sheet doesn't exist)
        mock_spreadsheet.worksheet.side_effect = [
            Exception("Worksheet not found"),
            mock_worksheet,  # After add_worksheet
        ]
        mock_spreadsheet.add_worksheet.return_value = mock_worksheet
        mock_gc.open_by_key.return_value = mock_spreadsheet
        mock_authorize.return_value = mock_gc

        test_data = [["Header"], ["Data"]]

        client = GoogleSheetsClient(credentials_file="creds.json")
        client.gc = mock_gc  # Set the gspread client directly
        client.write_sheet("test_id", "NewSheet", test_data)

        mock_spreadsheet.add_worksheet.assert_called_once()

    @patch("gspread.authorize")
    @patch("chibi.backup.google_sheets_client.Path.exists", return_value=True)
    def test_read_sheet(self, mock_exists, mock_authorize):
        """
        Test reading data from a sheet.

        Given: A spreadsheet with data
        When: read_sheet is called
        Then: Should return data as list of lists
        """
        # Mock gspread client
        mock_gc = MagicMock()
        mock_spreadsheet = MagicMock()
        mock_worksheet = MagicMock()
        mock_worksheet.get_all_values.return_value = [
            ["Name", "Age"],
            ["Alice", "25"],
            ["Bob", "30"],
        ]
        mock_spreadsheet.worksheet.return_value = mock_worksheet
        mock_gc.open_by_key.return_value = mock_spreadsheet
        mock_authorize.return_value = mock_gc

        client = GoogleSheetsClient(credentials_file="creds.json")
        client.gc = mock_gc  # Set the gspread client directly
        data = client.read_sheet("test_id", "Sheet1")

        assert len(data) == 3
        assert data[0] == ["Name", "Age"]
        assert data[1] == ["Alice", "25"]

    @patch("gspread.authorize")
    @patch("chibi.backup.google_sheets_client.Path.exists", return_value=True)
    def test_list_spreadsheets(self, mock_exists, mock_authorize):
        """
        Test listing spreadsheets with search query.

        Given: Multiple spreadsheets exist
        When: list_spreadsheets is called with a query
        Then: Should return matching spreadsheets
        """
        # Mock gspread client
        mock_gc = MagicMock()
        mock_spreadsheet_1 = {"id": "id1", "name": "Backup 2026-01-10"}
        mock_spreadsheet_2 = {"id": "id2", "name": "Backup 2026-01-11"}
        mock_gc.list_spreadsheet_files.return_value = [
            mock_spreadsheet_1,
            mock_spreadsheet_2,
        ]
        mock_authorize.return_value = mock_gc

        client = GoogleSheetsClient(credentials_file="creds.json")
        client.gc = mock_gc  # Set the gspread client directly
        spreadsheets = client.list_spreadsheets(query="Backup")

        assert len(spreadsheets) == 2
        assert spreadsheets[0]["id"] == "id1"


class TestErrorHandling:
    """Test error handling for API failures."""

    @patch("gspread.authorize")
    @patch("chibi.backup.google_sheets_client.Path.exists", return_value=True)
    def test_api_failure_on_create(self, mock_exists, mock_authorize):
        """
        Test handling API failure when creating spreadsheet.

        Given: Google API returns an error
        When: create_spreadsheet is called
        Then: Should raise appropriate exception with error message
        """
        from gspread.exceptions import APIError

        # Mock API error - create a mock response object
        mock_response = MagicMock()
        mock_response.json.return_value = {"error": {"code": 500, "message": "API Error"}}
        mock_response.text = "API Error"

        # Mock gspread client
        mock_gc = MagicMock()
        mock_gc.create.side_effect = APIError(mock_response)
        mock_authorize.return_value = mock_gc

        client = GoogleSheetsClient(credentials_file="creds.json")
        client.gc = mock_gc  # Set the gspread client directly
        with pytest.raises(APIError):
            client.create_spreadsheet("Test")

    @patch("gspread.authorize")
    @patch("chibi.backup.google_sheets_client.Path.exists", return_value=True)
    def test_permission_error_on_read(self, mock_exists, mock_authorize):
        """
        Test handling permission error when reading spreadsheet.

        Given: User lacks permission to access spreadsheet
        When: read_sheet is called
        Then: Should raise permission exception
        """
        from gspread.exceptions import SpreadsheetNotFound

        # Mock permission error
        mock_gc = MagicMock()
        mock_gc.open_by_key.side_effect = SpreadsheetNotFound("Permission denied")
        mock_authorize.return_value = mock_gc

        client = GoogleSheetsClient(credentials_file="creds.json")
        client.gc = mock_gc  # Set the gspread client directly
        with pytest.raises(SpreadsheetNotFound):
            client.read_sheet("forbidden_id", "Sheet1")

    @patch("gspread.authorize")
    @patch("chibi.backup.google_sheets_client.Path.exists", return_value=True)
    def test_network_error_retry(self, mock_exists, mock_authorize):
        """
        Test retry logic for transient network errors.

        Given: Network error occurs on first attempt
        When: Operation is retried
        Then: Should succeed on subsequent attempt
        """
        # Mock network error then success
        mock_gc = MagicMock()
        mock_spreadsheet = MagicMock()
        mock_spreadsheet.id = "test_id"
        mock_gc.create.side_effect = [
            ConnectionError("Network error"),
            mock_spreadsheet,  # Success on retry
        ]
        mock_authorize.return_value = mock_gc

        client = GoogleSheetsClient(credentials_file="creds.json")
        client.gc = mock_gc  # Set the gspread client directly
        # Implementation should have retry logic
        spreadsheet_id = client.create_spreadsheet("Test", retry=True)
        assert spreadsheet_id == "test_id"


class TestBatchOperations:
    """Test batch operations for rate limit compliance."""

    @patch("gspread.authorize")
    @patch("chibi.backup.google_sheets_client.Path.exists", return_value=True)
    def test_write_large_dataset_in_batches(self, mock_exists, mock_authorize):
        """
        Test writing large dataset respects batch size limits.

        Given: A dataset with 2500 rows
        When: write_sheet is called
        Then: Should write in batches of 1000 rows
        """
        # Mock gspread
        mock_gc = MagicMock()
        mock_spreadsheet = MagicMock()
        mock_worksheet = MagicMock()
        mock_spreadsheet.worksheet.return_value = mock_worksheet
        mock_gc.open_by_key.return_value = mock_spreadsheet
        mock_authorize.return_value = mock_gc

        # Generate 2500 rows
        large_data = [["col1", "col2"]] + [[f"row{i}", f"data{i}"] for i in range(2500)]

        client = GoogleSheetsClient(credentials_file="creds.json")
        client.gc = mock_gc  # Set the gspread client directly
        client.write_sheet("test_id", "Sheet1", large_data, batch_size=1000)

        # Should be called multiple times for batching
        assert mock_worksheet.update.call_count >= 3  # 2500 rows in batches of 1000

    @patch("gspread.authorize")
    @patch("chibi.backup.google_sheets_client.Path.exists", return_value=True)
    def test_rate_limit_handling(self, mock_exists, mock_authorize):
        """
        Test handling of rate limit errors with exponential backoff.

        Given: API returns rate limit error
        When: Operation is retried
        Then: Should wait and retry with exponential backoff
        """
        from gspread.exceptions import APIError

        # Mock rate limit error response
        mock_response = MagicMock()
        mock_response.json.return_value = {"error": {"code": 429, "message": "Rate Limit Exceeded"}}
        mock_response.text = "Rate Limit Exceeded"

        # Mock rate limit error then success
        mock_gc = MagicMock()
        mock_spreadsheet = MagicMock()
        mock_spreadsheet.id = "test_id"
        rate_limit_error = APIError(mock_response)
        mock_gc.create.side_effect = [
            rate_limit_error,
            mock_spreadsheet,  # Success after backoff
        ]
        mock_authorize.return_value = mock_gc

        client = GoogleSheetsClient(credentials_file="creds.json")
        client.gc = mock_gc  # Set the gspread client directly

        # Patch _is_rate_limit_error to return True for the rate limit error
        with patch.object(client, "_is_rate_limit_error", return_value=True):
            with patch("time.sleep") as mock_sleep:  # Don't actually sleep in tests
                spreadsheet_id = client.create_spreadsheet("Test", retry=True)
                assert spreadsheet_id == "test_id"
                mock_sleep.assert_called()  # Verify backoff occurred
