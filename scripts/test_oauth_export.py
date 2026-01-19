#!/usr/bin/env python3
"""Test OAuth authentication and export functionality."""

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

    print("=" * 60)
    print("Testing OAuth Export Setup")
    print("=" * 60)
    print(f"\nCredentials file: {credentials_file}")

    # Check if credentials file exists
    if not Path(credentials_file).exists():
        print(f"\n❌ Credentials file not found!")
        print(f"\nPlease download OAuth credentials from Google Cloud Console:")
        print("1. Go to: https://console.cloud.google.com/apis/credentials")
        print("2. Create OAuth client ID (Desktop app)")
        print("3. Download the JSON file")
        print(f"4. Save it as: {credentials_file}")
        sys.exit(1)

    print(f"✓ Credentials file found\n")

    # Initialize Google Sheets client
    print("Authenticating with OAuth...")
    print("📢 A browser window will open for authorization (first time only)")
    print("   Please sign in with your Google account and grant permissions.\n")

    client = GoogleSheetsClient(credentials_file=credentials_file)

    try:
        client.authenticate()
        print("✓ Authentication successful!\n")
    except Exception as e:
        print(f"❌ Authentication failed: {e}\n")
        sys.exit(1)

    # Try to create a test spreadsheet
    test_title = f"Chibi Test Export - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    print(f"Creating test spreadsheet: '{test_title}'...")

    try:
        spreadsheet_id = client.create_spreadsheet(test_title)
        spreadsheet_url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}"

        print(f"✓ SUCCESS!\n")
        print("=" * 60)
        print("✅ OAuth export is working correctly!")
        print("=" * 60)
        print(f"\nTest spreadsheet created:")
        print(f"  {spreadsheet_url}")
        print(f"\nThis file is in YOUR Google Drive (where you have space).")
        print(f"\nYou can now use /export-progress in Discord!")
        print(f"All exports will be saved to your personal Google Drive.\n")

        # Ask if user wants to clean up
        response = input("Delete test spreadsheet? [Y/n]: ")
        if response.lower() in ['', 'y', 'yes']:
            client.delete_spreadsheet(spreadsheet_id)
            print("✓ Test file deleted")

    except Exception as e:
        print(f"❌ FAILED: {e}\n")

        if "quota" in str(e).lower():
            print("Your personal Google Drive might be full.")
            print("Please free up space and try again.")
        else:
            print(f"Unexpected error: {e}")

        sys.exit(1)


if __name__ == "__main__":
    main()
