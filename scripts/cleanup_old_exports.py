#!/usr/bin/env python3
"""
Script to clean up old Google Sheets exports from the service account's Drive.

This helps free up storage quota when the service account's Drive is full.

Usage:
    python scripts/cleanup_old_exports.py --dry-run  # Preview what would be deleted
    python scripts/cleanup_old_exports.py --keep 5   # Keep only the 5 most recent exports
    python scripts/cleanup_old_exports.py --delete-all  # Delete ALL exports
"""

import argparse
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from chibi.backup.google_sheets_client import GoogleSheetsClient
from chibi.config import load_config


def main():
    parser = argparse.ArgumentParser(
        description="Clean up old Google Sheets exports to free storage quota"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be deleted without actually deleting",
    )
    parser.add_argument(
        "--keep",
        type=int,
        default=5,
        help="Number of most recent exports to keep (default: 5)",
    )
    parser.add_argument(
        "--delete-all",
        action="store_true",
        help="Delete ALL exports (use with caution!)",
    )
    args = parser.parse_args()

    # Load config
    config = load_config()
    credentials_file = config.backup.google_sheets.credentials_file

    # Initialize Google Sheets client
    print(f"Authenticating with {credentials_file}...")
    client = GoogleSheetsClient(credentials_file=credentials_file)
    client.authenticate()

    # List all spreadsheets
    print("\nFetching list of exports...")
    exports = client.list_spreadsheets(query="Chibi Student Progress")

    if not exports:
        print("No exports found. Nothing to delete.")
        return

    print(f"\nFound {len(exports)} export(s):")
    for i, export in enumerate(exports, 1):
        name = export.get("name", "Untitled")
        created = export.get("createdTime", "Unknown")
        file_id = export.get("id", "Unknown")
        print(f"  {i}. {name} (Created: {created}, ID: {file_id})")

    # Determine what to delete
    if args.delete_all:
        to_delete = exports
        to_keep = []
    else:
        # Sort by creation time (newest first)
        exports_sorted = sorted(
            exports,
            key=lambda x: x.get("createdTime", ""),
            reverse=True,
        )
        to_keep = exports_sorted[: args.keep]
        to_delete = exports_sorted[args.keep :]

    if not to_delete:
        print(f"\n✓ Only {len(exports)} export(s) found. Nothing to delete.")
        return

    print(f"\n{'[DRY RUN] ' if args.dry_run else ''}Will delete {len(to_delete)} export(s):")
    for export in to_delete:
        name = export.get("name", "Untitled")
        created = export.get("createdTime", "Unknown")
        print(f"  - {name} (Created: {created})")

    if to_keep:
        print(f"\nWill keep {len(to_keep)} most recent export(s):")
        for export in to_keep:
            name = export.get("name", "Untitled")
            created = export.get("createdTime", "Unknown")
            print(f"  - {name} (Created: {created})")

    if args.dry_run:
        print("\n[DRY RUN] No files were actually deleted. Run without --dry-run to delete.")
        return

    # Confirm deletion
    if not args.delete_all:
        response = input(f"\nDelete {len(to_delete)} file(s)? [y/N]: ")
        if response.lower() not in ["y", "yes"]:
            print("Cancelled.")
            return

    # Delete files
    print("\nDeleting files...")
    for export in to_delete:
        file_id = export.get("id")
        name = export.get("name", "Untitled")
        try:
            client.delete_spreadsheet(file_id)
            print(f"  ✓ Deleted: {name}")
        except Exception as e:
            print(f"  ✗ Failed to delete {name}: {e}")

    print(f"\n✓ Cleanup complete. Deleted {len(to_delete)} file(s).")


if __name__ == "__main__":
    main()
