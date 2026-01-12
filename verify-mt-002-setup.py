#!/usr/bin/env python3
"""
Verification script for MT-002 manual test setup.

This script checks that all prerequisites for MT-002 are met before
attempting manual testing with real Google Sheets API.
"""

import json
import sys
from pathlib import Path

import yaml


def check_file_exists(path: str, name: str) -> bool:
    """Check if a file exists and print status."""
    file_path = Path(path)
    if file_path.exists():
        print(f"✓ {name} exists at: {path}")
        return True
    else:
        print(f"✗ {name} NOT FOUND at: {path}")
        return False


def check_credentials_file() -> bool:
    """Verify google credentials file exists and is valid."""
    print("\n=== Checking Google Credentials ===")

    cred_path = "google-credential.json"
    if not check_file_exists(cred_path, "google-credential.json"):
        return False

    try:
        with open(cred_path) as f:
            creds = json.load(f)

        # Check required fields
        cred_type = creds.get("type")
        project_id = creds.get("project_id")
        client_email = creds.get("client_email")
        private_key = creds.get("private_key")

        if cred_type != "service_account":
            print(f"✗ Expected type='service_account', got '{cred_type}'")
            return False
        print(f"✓ type: {cred_type}")

        if not project_id:
            print("✗ Missing project_id")
            return False
        print(f"✓ project_id: {project_id}")

        if not client_email:
            print("✗ Missing client_email")
            return False
        print(f"✓ client_email: {client_email}")

        if not private_key:
            print("✗ Missing private_key")
            return False
        print("✓ private_key: [REDACTED] (present)")

        return True

    except json.JSONDecodeError as e:
        print(f"✗ Invalid JSON in credentials file: {e}")
        return False
    except Exception as e:
        print(f"✗ Error reading credentials: {e}")
        return False


def check_config_file() -> bool:
    """Verify config.yaml has correct backup configuration."""
    print("\n=== Checking Config File ===")

    config_path = "config.yaml"
    if not check_file_exists(config_path, "config.yaml"):
        return False

    try:
        with open(config_path) as f:
            config = yaml.safe_load(f)

        backup_config = config.get("backup", {})
        if not backup_config:
            print("✗ Missing 'backup' section in config.yaml")
            return False
        print("✓ 'backup' section present")

        sheets_config = backup_config.get("google_sheets", {})
        if not sheets_config:
            print("✗ Missing 'backup.google_sheets' section")
            return False
        print("✓ 'backup.google_sheets' section present")

        credentials_file = sheets_config.get("credentials_file")
        if not credentials_file:
            print("✗ Missing 'credentials_file' in backup.google_sheets")
            return False
        print(f"✓ credentials_file: {credentials_file}")

        # Verify credentials_file points to existing file
        if not Path(credentials_file).exists():
            print(f"✗ credentials_file '{credentials_file}' does not exist")
            return False
        print(f"✓ credentials_file exists")

        token_file = sheets_config.get("token_file")
        if token_file:
            print(f"✓ token_file: {token_file} (not needed for service account)")

        return True

    except yaml.YAMLError as e:
        print(f"✗ Invalid YAML in config file: {e}")
        return False
    except Exception as e:
        print(f"✗ Error reading config: {e}")
        return False


def check_imports() -> bool:
    """Verify all backup modules can be imported."""
    print("\n=== Checking Python Imports ===")

    try:
        # Add current directory to path
        sys.path.insert(0, ".")

        from chibi.backup import BackupService, GoogleSheetsClient
        print("✓ BackupService and GoogleSheetsClient imported")

        from chibi.backup import SheetsExporter, SheetsImporter
        print("✓ SheetsExporter and SheetsImporter imported")

        # Test service account detection
        client = GoogleSheetsClient("google-credential.json")
        cred_type = client._detect_credential_type()

        if cred_type != "service_account":
            print(f"✗ Expected service_account, got {cred_type}")
            return False
        print(f"✓ Credential type detected: {cred_type}")

        return True

    except ImportError as e:
        print(f"✗ Import error: {e}")
        return False
    except Exception as e:
        print(f"✗ Error during import check: {e}")
        return False


def check_database() -> bool:
    """Check if database exists (optional for MT-002)."""
    print("\n=== Checking Database ===")

    db_path = "data/chibi.db"
    if Path(db_path).exists():
        print(f"✓ Database exists at: {db_path}")
        print("  (Note: Empty database is OK for MT-002)")
        return True
    else:
        print(f"⚠ Database not found at: {db_path}")
        print("  (Database will be created when bot starts)")
        return True  # Not a failure for MT-002


def print_next_steps():
    """Print next steps for manual testing."""
    print("\n" + "=" * 60)
    print("=== MT-002 Setup Complete ===")
    print("=" * 60)
    print("\n✅ All prerequisites are met!")
    print("\nNext steps:")
    print("1. Ensure Google Sheets API is enabled:")
    print("   https://console.cloud.google.com/apis/library/sheets.googleapis.com")
    print("\n2. Ensure Google Drive API is enabled:")
    print("   https://console.cloud.google.com/apis/library/drive.googleapis.com")
    print("\n3. Start the bot:")
    print("   uv run python main.py")
    print("\n4. In Discord, run as admin:")
    print("   /export-progress")
    print("\n5. Verify:")
    print("   - No browser popup (service account = silent auth)")
    print("   - Bot responds within 30 seconds")
    print("   - Success or clear error message")
    print("\nSee MT-002-MANUAL-TEST-GUIDE.md for detailed instructions.")
    print("=" * 60)


def main():
    """Run all verification checks."""
    print("=" * 60)
    print("MT-002 Manual Test Setup Verification")
    print("=" * 60)

    checks = [
        ("Credentials File", check_credentials_file),
        ("Config File", check_config_file),
        ("Python Imports", check_imports),
        ("Database", check_database),
    ]

    all_passed = True
    for check_name, check_func in checks:
        try:
            if not check_func():
                all_passed = False
        except Exception as e:
            print(f"\n✗ {check_name} check failed with exception: {e}")
            all_passed = False

    if all_passed:
        print_next_steps()
        sys.exit(0)
    else:
        print("\n" + "=" * 60)
        print("❌ Some checks failed. Please fix the issues above.")
        print("=" * 60)
        sys.exit(1)


if __name__ == "__main__":
    main()
