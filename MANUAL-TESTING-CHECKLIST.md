# Manual Testing Checklist - Google Sheets Backup Feature

## Overview

This checklist guides manual end-to-end testing of the Google Sheets backup feature using **real Google Sheets API credentials** (not mocks).

## Prerequisites

### ⚠️ CRITICAL: Service Account Support Required

**Status**: ❌ **NOT YET IMPLEMENTED** (See MT-000)

The current implementation only supports OAuth user credentials, but we have a service account credential file (`google-credential.json`). Before any manual testing can proceed:

1. Implement MT-000: Add service account support to GoogleSheetsClient
2. Update `chibi/backup/google_sheets_client.py` to auto-detect credential type
3. Verify all existing unit tests still pass

**Without this change, all manual tests will fail with authentication errors.**

### Environment Setup

- ✅ `google-credential.json` exists in project root (service account)
- ✅ `config.yaml` updated to point to `google-credential.json`
- ✅ Google Sheets API and Drive API enabled in Google Cloud Console
- ✅ Test Discord server with admin permissions
- ✅ Test database: `data/chibi.db` with sample data

## Testing Progress

### Prerequisite (Must Complete First)
- [ ] **MT-000**: Add service account support to GoogleSheetsClient

### Setup Tests
- [ ] **MT-001**: Verify credentials and configuration
- [ ] **MT-002**: Test OAuth authentication with service account

### Export Tests
- [ ] **MT-003**: Basic export with sample data
- [ ] **MT-004**: Export with empty database
- [ ] **MT-005**: Export with large dataset

### Import Tests
- [ ] **MT-006**: Import to clean database (replace mode)
- [ ] **MT-007**: Import to existing database (merge mode)
- [ ] **MT-008**: Import with schema validation
- [ ] **MT-009**: Import error handling and rollback

### List Tests
- [ ] **MT-010**: List recent exports

### Integration Tests
- [ ] **MT-011**: Cross-machine data transfer

### Data Integrity Tests
- [ ] **MT-012**: Data type preservation
- [ ] **MT-013**: Referential integrity verification

## Quick Commands

```bash
# Backup database before testing
cp data/chibi.db data/chibi.db.backup

# Restore database if needed
cp data/chibi.db.backup data/chibi.db

# Start bot
uv run python main.py

# Check database
sqlite3 data/chibi.db "SELECT COUNT(*) FROM users;"
sqlite3 data/chibi.db "SELECT COUNT(*) FROM quiz_attempts;"

# View all table counts
sqlite3 data/chibi.db <<EOF
SELECT 'users' as table_name, COUNT(*) as count FROM users
UNION ALL
SELECT 'quiz_attempts', COUNT(*) FROM quiz_attempts
UNION ALL
SELECT 'concept_mastery', COUNT(*) FROM concept_mastery
UNION ALL
SELECT 'llm_quiz_attempts', COUNT(*) FROM llm_quiz_attempts
UNION ALL
SELECT 'attendance', COUNT(*) FROM attendance;
EOF
```

## Discord Commands

```
/export-progress                          # Export all data to Google Sheets
/import-progress <url> [mode]             # Import from Sheets (replace/merge)
/list-exports [limit]                     # List recent exports (default 10)
```

## Test Spreadsheet

For import testing, use: https://docs.google.com/spreadsheets/d/11dCrdHKUuJS3WuA-ctzFHZfKk0lk20-NGLm16wRPpLs/edit?usp=drive_link

## Next Steps

1. **Implement MT-000** (service account support)
2. Create test data in database (2-3 users, 10+ quiz attempts)
3. Execute MT-001 through MT-013 in order
4. Document all results in `manual-testing-log.md`
5. Update `"passes": true` for each successful test in `manual-testing-prd.json`

## Safety Reminders

- ⚠️ Use test database, not production
- ⚠️ Backup database before destructive tests
- ⚠️ Test in isolated Discord server
- ⚠️ Delete test spreadsheets after testing to avoid quota issues

## Files

- **manual-testing-prd.json**: 14 test scenarios with detailed steps
- **manual-testing-prompt.md**: Complete testing guide with validation queries
- **DATABASE_STRUCTURE.md**: Database schema reference for data verification
