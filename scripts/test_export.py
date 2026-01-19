#!/usr/bin/env python3
"""Test creating a spreadsheet to diagnose quota issues."""

import sys
from pathlib import Path
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from chibi.backup.google_sheets_client import GoogleSheetsClient
from chibi.config import load_config


def main():
    # Load config
    config = load_config()
    credentials_file = config.backup.credentials_file

    print(f"Testing with credentials: {credentials_file}\n")

    # Initialize Google Sheets client
    print("Authenticating...")
    client = GoogleSheetsClient(credentials_file=credentials_file)
    client.authenticate()
    print("✓ Authentication successful\n")

    # Try to create a test spreadsheet
    test_title = f"Test Export - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    print(f"Attempting to create test spreadsheet: '{test_title}'")
    print("This will help us diagnose the quota issue...\n")

    try:
        spreadsheet_id = client.create_spreadsheet(test_title)
        print(f"✓ SUCCESS! Created spreadsheet with ID: {spreadsheet_id}")
        print(f"\nThe quota issue appears to be resolved!")
        print(f"You can now use /export-progress in Discord.")

        # Clean up test file
        print(f"\nCleaning up test file...")
        client.delete_spreadsheet(spreadsheet_id)
        print("✓ Test file deleted")

    except Exception as e:
        print(f"✗ FAILED: {e}\n")
        print("Diagnosis:")

        if "quota has been exceeded" in str(e).lower():
            print("- The service account's Drive storage is still full")
            print("- Possible causes:")
            print("  1. You're using the same old service account")
            print("  2. Project-level quota restrictions")
            print("  3. Organization-level restrictions")
            print("\nSuggestions:")
            print("1. Verify you created a NEW service account (not reused old one)")
            print("2. Check Google Cloud Console > IAM & Admin > Quotas")
            print("3. Try creating the service account in a different Google Cloud project")

        elif "api not enabled" in str(e).lower():
            print("- Google Drive API or Sheets API not enabled")
            print("- Enable at: https://console.cloud.google.com/apis/")

        else:
            print(f"- Unexpected error: {e}")

        sys.exit(1)


if __name__ == "__main__":
    main()
