#!/usr/bin/env python3
"""Check what's using storage in the service account's Google Drive."""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from chibi.backup.google_sheets_client import GoogleSheetsClient
from chibi.config import load_config


def main():
    # Load config
    config = load_config()
    credentials_file = config.backup.credentials_file

    # Verify credentials file exists
    if not Path(credentials_file).exists():
        print(f"Error: Credentials file not found: {credentials_file}")
        sys.exit(1)

    # Initialize Google Sheets client
    print(f"Authenticating with {credentials_file}...\n")
    client = GoogleSheetsClient(credentials_file=credentials_file)
    client.authenticate()

    # List ALL spreadsheets (no query filter)
    print("Fetching ALL files in Drive...\n")
    all_files = client.list_spreadsheets()

    if not all_files:
        print("No files found in Drive.")
        print("\nThis is strange - you're getting a quota error but no files are visible.")
        print("Possible causes:")
        print("1. Files might be in Trash (not visible via API)")
        print("2. Storage consumed by file revisions")
        print("3. Different file types (not spreadsheets)")
        return

    print(f"Found {len(all_files)} file(s):\n")
    for i, file_info in enumerate(all_files, 1):
        name = file_info.get("name", "Untitled")
        file_id = file_info.get("id", "Unknown")
        created = file_info.get("createdTime", "Unknown")
        print(f"{i}. {name}")
        print(f"   ID: {file_id}")
        print(f"   Created: {created}")
        print()

    print(f"\nTotal: {len(all_files)} file(s)")
    print("\nTo delete all files, run:")
    print("  python scripts/cleanup_old_exports.py --delete-all")


if __name__ == "__main__":
    main()
