"""Google Sheets OAuth client for backup operations.

This module provides OAuth 2.0 authentication and CRUD operations
for Google Sheets API using the gspread library.
"""

import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import gspread
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google.oauth2.service_account import Credentials as ServiceAccountCredentials
from google_auth_oauthlib.flow import InstalledAppFlow
from gspread.exceptions import APIError, SpreadsheetNotFound

logger = logging.getLogger(__name__)


class GoogleSheetsClient:
    """Client for Google Sheets API with OAuth 2.0 and service account authentication."""

    def __init__(
        self,
        credentials_file: str,
        token_file: str = "credentials/token.json",
        scopes: Optional[List[str]] = None,
    ):
        """
        Initialize Google Sheets client.

        Supports both OAuth 2.0 user credentials and service account credentials.
        The credential type is automatically detected from the JSON file.

        Args:
            credentials_file: Path to OAuth or service account credentials JSON file
            token_file: Path to store/retrieve access token (OAuth only)
            scopes: OAuth scopes (defaults to spreadsheets and drive.file)

        Raises:
            FileNotFoundError: If credentials file does not exist
        """
        self.credentials_file = credentials_file
        self.token_file = token_file
        self.scopes = scopes or [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive.file",
        ]

        # Verify credentials file exists
        if not Path(credentials_file).exists():
            raise FileNotFoundError(
                f"Credentials file not found: {credentials_file}"
            )

        self.credentials: Optional[Credentials] = None
        self.gc: Optional[gspread.Client] = None

    def _detect_credential_type(self) -> str:
        """
        Detect credential type from JSON file.

        Returns:
            'service_account' or 'oauth'

        Raises:
            ValueError: If credential type cannot be determined
        """
        try:
            with open(self.credentials_file, "r") as f:
                cred_data = json.load(f)
                cred_type = cred_data.get("type", "")

                if cred_type == "service_account":
                    return "service_account"
                elif "installed" in cred_data or "web" in cred_data:
                    return "oauth"
                else:
                    raise ValueError(
                        f"Unknown credential type in {self.credentials_file}. "
                        "Expected 'type': 'service_account' or OAuth client config."
                    )
        except json.JSONDecodeError as e:
            raise ValueError(
                f"Invalid JSON in credentials file {self.credentials_file}: {e}"
            )

    def authenticate(self) -> None:
        """
        Authenticate with Google using OAuth 2.0 or service account.

        For OAuth (user credentials):
        1. Valid token exists: Reuse it
        2. Expired token: Refresh it
        3. No token: Run OAuth flow and save token

        For service account:
        - Authenticates directly using credentials file (no browser flow)
        """
        # Detect credential type
        cred_type = self._detect_credential_type()

        if cred_type == "service_account":
            # Service account authentication (no browser/token required)
            logger.info("Authenticating with service account")
            self.credentials = ServiceAccountCredentials.from_service_account_file(
                self.credentials_file, scopes=self.scopes
            )
            self._authorize_gspread()
            return

        # OAuth user credentials authentication
        # Try to load existing token
        token_path = Path(self.token_file)
        if token_path.exists():
            self.credentials = Credentials.from_authorized_user_file(
                str(token_path), self.scopes
            )

        # Check if credentials are valid
        if self.credentials and self.credentials.valid:
            logger.info("Using existing valid OAuth token")
            self._authorize_gspread()
            return

        # Refresh expired token if possible
        if (
            self.credentials
            and self.credentials.expired
            and self.credentials.refresh_token
        ):
            logger.info("Refreshing expired OAuth token")
            self.credentials.refresh(Request())
            self._save_token()
            self._authorize_gspread()
            return

        # Run OAuth flow for first-time or invalid credentials
        logger.info("Starting OAuth flow (browser authentication required)")
        flow = InstalledAppFlow.from_client_secrets_file(
            self.credentials_file, self.scopes
        )
        self.credentials = flow.run_local_server(port=0)
        self._save_token()
        self._authorize_gspread()

    def _save_token(self) -> None:
        """Save credentials to token file."""
        token_path = Path(self.token_file)
        token_path.parent.mkdir(parents=True, exist_ok=True)

        with open(token_path, "w") as token:
            token.write(self.credentials.to_json())

        logger.info(f"Token saved to {self.token_file}")

    def _authorize_gspread(self) -> None:
        """Authorize gspread client with current credentials."""
        self.gc = gspread.authorize(self.credentials)
        logger.debug("gspread client authorized")

    def create_spreadsheet(self, title: str, retry: bool = True) -> str:
        """
        Create a new spreadsheet.

        Args:
            title: Title for the new spreadsheet
            retry: Whether to retry on transient errors

        Returns:
            Spreadsheet ID

        Raises:
            APIError: If API call fails
            ConnectionError: If network error occurs (without retry)
        """
        if not self.gc:
            self.authenticate()

        try:
            spreadsheet = self.gc.create(title)
            logger.info(f"Created spreadsheet: {title} (ID: {spreadsheet.id})")
            return spreadsheet.id
        except ConnectionError as e:
            if retry:
                logger.warning(f"Network error, retrying: {e}")
                time.sleep(1)
                return self.create_spreadsheet(title, retry=False)
            raise
        except APIError as e:
            # Handle rate limiting with exponential backoff
            if self._is_rate_limit_error(e):
                if retry:
                    logger.warning("Rate limit exceeded, waiting and retrying...")
                    time.sleep(2)  # Wait before retry
                    return self.create_spreadsheet(title, retry=False)
            raise

    def get_spreadsheet(self, spreadsheet_id: str) -> gspread.Spreadsheet:
        """
        Get an existing spreadsheet by ID.

        Args:
            spreadsheet_id: The spreadsheet ID

        Returns:
            gspread.Spreadsheet object

        Raises:
            SpreadsheetNotFound: If spreadsheet doesn't exist or no access
        """
        if not self.gc:
            self.authenticate()

        spreadsheet = self.gc.open_by_key(spreadsheet_id)
        logger.debug(f"Retrieved spreadsheet: {spreadsheet_id}")
        return spreadsheet

    def write_sheet(
        self,
        spreadsheet_id: str,
        sheet_name: str,
        data: List[List[Any]],
        batch_size: int = 1000,
    ) -> None:
        """
        Write data to a sheet, creating it if it doesn't exist.

        Args:
            spreadsheet_id: The spreadsheet ID
            sheet_name: Name of the sheet to write to
            data: Data as list of lists (rows)
            batch_size: Number of rows to write per batch

        Raises:
            APIError: If write operation fails
        """
        if not self.gc:
            self.authenticate()

        spreadsheet = self.get_spreadsheet(spreadsheet_id)

        # Try to get worksheet, create if it doesn't exist
        try:
            worksheet = spreadsheet.worksheet(sheet_name)
            logger.debug(f"Using existing sheet: {sheet_name}")
        except Exception:
            logger.info(f"Creating new sheet: {sheet_name}")
            worksheet = spreadsheet.add_worksheet(
                title=sheet_name, rows=len(data), cols=len(data[0]) if data else 1
            )

        # Write data in batches
        if len(data) <= batch_size:
            # Write all at once if small enough
            worksheet.update(data, value_input_option="USER_ENTERED")
            logger.info(f"Wrote {len(data)} rows to {sheet_name}")
        else:
            # Write in batches for large datasets
            for i in range(0, len(data), batch_size):
                batch = data[i : i + batch_size]
                start_row = i + 1
                end_row = start_row + len(batch) - 1
                range_name = f"A{start_row}:ZZ{end_row}"
                worksheet.update(range_name, batch, value_input_option="USER_ENTERED")
                logger.debug(
                    f"Wrote batch {i // batch_size + 1}: rows {start_row}-{end_row}"
                )

            logger.info(f"Wrote {len(data)} rows to {sheet_name} in batches")

    def read_sheet(
        self, spreadsheet_id: str, sheet_name: str
    ) -> List[List[str]]:
        """
        Read data from a sheet.

        Args:
            spreadsheet_id: The spreadsheet ID
            sheet_name: Name of the sheet to read

        Returns:
            Data as list of lists (rows)

        Raises:
            SpreadsheetNotFound: If spreadsheet or sheet doesn't exist
        """
        if not self.gc:
            self.authenticate()

        spreadsheet = self.get_spreadsheet(spreadsheet_id)
        worksheet = spreadsheet.worksheet(sheet_name)
        data = worksheet.get_all_values()

        logger.debug(f"Read {len(data)} rows from {sheet_name}")
        return data

    def list_spreadsheets(
        self, query: Optional[str] = None
    ) -> List[Dict[str, str]]:
        """
        List spreadsheets accessible to the user.

        Args:
            query: Optional search query to filter results

        Returns:
            List of dicts with 'id' and 'name' keys
        """
        if not self.gc:
            self.authenticate()

        # Get all spreadsheet files
        spreadsheet_files = self.gc.list_spreadsheet_files()

        # Filter by query if provided
        if query:
            spreadsheet_files = [
                f for f in spreadsheet_files if query in f.get("name", "")
            ]

        logger.info(f"Found {len(spreadsheet_files)} spreadsheets")
        return spreadsheet_files

    def delete_spreadsheet(self, spreadsheet_id: str) -> None:
        """
        Delete a spreadsheet from Google Drive.

        Args:
            spreadsheet_id: The spreadsheet ID to delete

        Raises:
            APIError: If deletion fails
        """
        if not self.gc:
            self.authenticate()

        try:
            self.gc.del_spreadsheet(spreadsheet_id)
            logger.info(f"Deleted spreadsheet: {spreadsheet_id}")
        except APIError as e:
            logger.error(f"Failed to delete spreadsheet {spreadsheet_id}: {e}")
            raise

    def find_or_create_folder(self, folder_name: str) -> str:
        """
        Find an existing folder by name or create it if it doesn't exist.

        Args:
            folder_name: Name of the folder to find or create

        Returns:
            Folder ID

        Raises:
            APIError: If folder operations fail
        """
        if not self.gc:
            self.authenticate()

        try:
            # Search for existing folder
            # Use Drive API v3 to search for folders
            from googleapiclient.discovery import build

            drive_service = build('drive', 'v3', credentials=self.credentials)

            # Query for folders with the specified name
            query = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
            results = drive_service.files().list(
                q=query,
                spaces='drive',
                fields='files(id, name)'
            ).execute()

            folders = results.get('files', [])

            if folders:
                folder_id = folders[0]['id']
                logger.info(f"Found existing folder '{folder_name}' with ID: {folder_id}")
                return folder_id

            # Create new folder if not found
            file_metadata = {
                'name': folder_name,
                'mimeType': 'application/vnd.google-apps.folder'
            }
            folder = drive_service.files().create(
                body=file_metadata,
                fields='id'
            ).execute()

            folder_id = folder.get('id')
            logger.info(f"Created new folder '{folder_name}' with ID: {folder_id}")
            return folder_id

        except Exception as e:
            logger.error(f"Failed to find or create folder '{folder_name}': {e}")
            raise

    def move_spreadsheet_to_folder(self, spreadsheet_id: str, folder_id: str) -> None:
        """
        Move a spreadsheet into a specific folder.

        Args:
            spreadsheet_id: The spreadsheet ID to move
            folder_id: The destination folder ID

        Raises:
            APIError: If move operation fails
        """
        if not self.gc:
            self.authenticate()

        try:
            from googleapiclient.discovery import build

            drive_service = build('drive', 'v3', credentials=self.credentials)

            # Retrieve the existing parents to remove
            file = drive_service.files().get(
                fileId=spreadsheet_id,
                fields='parents'
            ).execute()
            previous_parents = ",".join(file.get('parents', []))

            # Move the file to the new folder
            drive_service.files().update(
                fileId=spreadsheet_id,
                addParents=folder_id,
                removeParents=previous_parents,
                fields='id, parents'
            ).execute()

            logger.info(f"Moved spreadsheet {spreadsheet_id} to folder {folder_id}")

        except Exception as e:
            logger.error(f"Failed to move spreadsheet {spreadsheet_id} to folder {folder_id}: {e}")
            raise

    @staticmethod
    def _is_rate_limit_error(error: APIError) -> bool:
        """
        Check if error is a rate limit error.

        Args:
            error: The API error

        Returns:
            True if rate limit error
        """
        try:
            error_dict = error.args[0] if error.args else {}
            if isinstance(error_dict, dict):
                code = error_dict.get("error", {}).get("code")
                return code == 429
        except (IndexError, AttributeError, TypeError):
            pass
        return False
