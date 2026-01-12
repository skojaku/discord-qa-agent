# Manual E2E Testing: MT-008 - Import with Schema Validation

## Test Objective
Verify that the import functionality correctly validates spreadsheet schema and rejects invalid spreadsheets gracefully without modifying the database.

## Background
The SheetsImporter (`chibi/backup/sheets_importer.py:115-164`) performs comprehensive schema validation before importing data. This validation prevents corrupted or incompatible spreadsheets from damaging the database. Schema validation checks for:

1. **Metadata sheet presence** (line 135-136): Rejects if Metadata sheet missing
2. **Required data sheets** (line 139-144): Validates all 5 data sheets exist (Users, QuizAttempts, ConceptMastery, LLMQuizAttempts, Attendance)
3. **Schema version compatibility** (line 156-161): Verifies schema_version = "1.0"
4. **Transaction safety** (line 296-357): Database unchanged if validation fails (no partial imports)

This test ensures the validation logic works correctly and provides clear error messages to users.

## Prerequisites

Before starting this test, verify:

- [ ] MT-003 passed (you have an exported spreadsheet to work with)
- [ ] You have access to edit the exported Google Spreadsheet
- [ ] Bot is running and you have admin permissions in Discord
- [ ] Database backup exists: `cp data/chibi.db data/chibi.db.backup`
- [ ] You have spreadsheet URL from a successful export

## Part 1: Prepare Test Spreadsheet

### Step 1: Create test spreadsheet
```bash
# In Discord, run export to create a fresh spreadsheet
/export-progress
```

**Expected:** Bot returns spreadsheet URL (e.g., `https://docs.google.com/spreadsheets/d/ABC123...`)

**Record the URL:** `TEST_SPREADSHEET_URL = _________________`

### Step 2: Open spreadsheet in browser
Open the spreadsheet URL in your web browser (Google Chrome or Firefox recommended).

**Expected:** Spreadsheet opens with 6 sheets:
- Metadata
- Users
- QuizAttempts
- ConceptMastery
- LLMQuizAttempts
- Attendance

**Note:** If you cannot access the spreadsheet (service account Drive access), this test requires OAuth credentials or spreadsheet sharing. Skip to troubleshooting section.

### Step 3: Record current database state
```bash
# Record counts for comparison after failed imports
sqlite3 data/chibi.db "SELECT COUNT(*) FROM users;"
sqlite3 data/chibi.db "SELECT COUNT(*) FROM quiz_attempts;"
sqlite3 data/chibi.db "SELECT COUNT(*) FROM concept_mastery;"
```

**Record baseline:**
- `BASELINE_USERS = _____`
- `BASELINE_QUIZ_ATTEMPTS = _____`
- `BASELINE_CONCEPT_MASTERY = _____`

## Part 2: Test Missing Metadata Sheet

### Step 4: Delete Metadata sheet
In the spreadsheet browser tab:
1. Right-click the "Metadata" sheet tab at the bottom
2. Select "Delete"
3. Confirm deletion

**Expected:** Only 5 sheets remain (Users, QuizAttempts, ConceptMastery, LLMQuizAttempts, Attendance)

### Step 5: Attempt import without Metadata
```bash
# In Discord, run import with modified spreadsheet
/import-progress <TEST_SPREADSHEET_URL> mode:replace
```

**Expected bot response:**
- ❌ Error embed displayed
- Error message: "Metadata sheet not found in spreadsheet"
- No confirmation dialog shown (validation failed before import started)

**Pass criteria:**
- Bot responds with error within 5 seconds
- Error message explicitly mentions "Metadata sheet"
- No confirmation button appears

### Step 6: Verify database unchanged
```bash
# Check counts are identical to baseline
sqlite3 data/chibi.db "SELECT COUNT(*) FROM users;"
sqlite3 data/chibi.db "SELECT COUNT(*) FROM quiz_attempts;"
sqlite3 data/chibi.db "SELECT COUNT(*) FROM concept_mastery;"
```

**Expected:**
- `CURRENT_USERS = BASELINE_USERS` (unchanged)
- `CURRENT_QUIZ_ATTEMPTS = BASELINE_QUIZ_ATTEMPTS` (unchanged)
- `CURRENT_CONCEPT_MASTERY = BASELINE_CONCEPT_MASTERY` (unchanged)

**Pass criteria:** All counts EXACTLY match baseline (database untouched)

### Step 7: Restore Metadata sheet
In spreadsheet:
1. Click Edit → Undo (or Ctrl+Z / Cmd+Z)
2. Verify Metadata sheet reappears

**Alternative if Undo doesn't work:** Create new export and use that URL for next tests.

## Part 3: Test Missing Data Sheet

### Step 8: Delete Users sheet
In the spreadsheet browser tab:
1. Right-click the "Users" sheet tab
2. Select "Delete"
3. Confirm deletion

**Expected:** Metadata + 4 data sheets remain (missing Users)

### Step 9: Attempt import without Users sheet
```bash
# In Discord, run import with modified spreadsheet
/import-progress <TEST_SPREADSHEET_URL> mode:replace
```

**Expected bot response:**
- ❌ Error embed displayed
- Error message: "Missing required sheet: Users"
- Error message lists expected sheets: "Expected sheets: Metadata, Users, QuizAttempts, ConceptMastery, LLMQuizAttempts, Attendance"
- No confirmation dialog shown

**Pass criteria:**
- Bot responds with error within 5 seconds
- Error explicitly mentions "Users" as missing
- Error lists all expected sheets

### Step 10: Verify database unchanged
```bash
# Check counts are identical to baseline
sqlite3 data/chibi.db "SELECT COUNT(*) FROM users;"
sqlite3 data/chibi.db "SELECT COUNT(*) FROM quiz_attempts;"
```

**Expected:** Counts match baseline exactly (no changes)

**Pass criteria:** Database untouched by failed import attempt

### Step 11: Restore Users sheet
Use Undo (Edit → Undo) or create fresh export for next tests.

## Part 4: Test Invalid Schema Version

### Step 12: Modify schema version in Metadata
In the spreadsheet browser tab:
1. Click the "Metadata" sheet tab
2. Find the row with "schema_version" in column A
3. Change the value in column B from "1.0" to "2.0"
4. Press Enter to save the change

**Expected:** Metadata sheet shows:
```
Key                | Value
schema_version     | 2.0
```

### Step 13: Attempt import with incompatible schema version
```bash
# In Discord, run import with modified spreadsheet
/import-progress <TEST_SPREADSHEET_URL> mode:replace
```

**Expected bot response:**
- ❌ Error embed displayed
- Error message: "Incompatible schema version: 2.0. Expected: 1.0"
- No confirmation dialog shown

**Pass criteria:**
- Bot responds with error within 5 seconds
- Error shows both actual version (2.0) and expected version (1.0)
- Validation fails before import starts

### Step 14: Verify database unchanged
```bash
# Final verification that no validation errors modified database
sqlite3 data/chibi.db "SELECT COUNT(*) FROM users;"
sqlite3 data/chibi.db "SELECT COUNT(*) FROM quiz_attempts;"
sqlite3 data/chibi.db "SELECT COUNT(*) FROM concept_mastery;"
```

**Expected:** All counts match baseline

**Pass criteria:** Database remains in original state after all validation failures

## Part 5: Test Valid Schema (Positive Control)

### Step 15: Restore schema version to 1.0
In Metadata sheet:
1. Change schema_version value back to "1.0"
2. Press Enter to save

### Step 16: Verify import now succeeds
```bash
# In Discord, run import with corrected spreadsheet
/import-progress <TEST_SPREADSHEET_URL> mode:replace
```

**Expected bot response:**
- Confirmation dialog appears (schema validation passed)
- Click [Confirm] button
- ✅ Success embed displayed
- Import completes with summary counts

**Pass criteria:**
- No validation errors
- Import executes successfully
- This confirms validation is not overly strict (allows valid schemas)

## Part 6: Cleanup

### Step 17: Restore original database (optional)
```bash
# If you want to restore original state
cp data/chibi.db.backup data/chibi.db

# Verify restoration
sqlite3 data/chibi.db "SELECT COUNT(*) FROM users;"
```

### Step 18: Delete test spreadsheets
Delete the test spreadsheet from Google Drive to avoid quota issues.

**Note:** If using service account, spreadsheet is in service account's Drive (may not be visible to you).

## Pass/Fail Criteria

### Minimum Passing Criteria (Required)
All of the following MUST be true for MT-008 to pass:

1. **Missing Metadata Sheet (Steps 4-6):**
   - [ ] Bot returns error: "Metadata sheet not found"
   - [ ] No confirmation dialog appears
   - [ ] Database unchanged after error (counts match baseline)

2. **Missing Data Sheet (Steps 8-10):**
   - [ ] Bot returns error: "Missing required sheet: Users"
   - [ ] Error lists expected sheets
   - [ ] No confirmation dialog appears
   - [ ] Database unchanged after error

3. **Invalid Schema Version (Steps 12-14):**
   - [ ] Bot returns error: "Incompatible schema version: 2.0. Expected: 1.0"
   - [ ] Error shows both actual and expected versions
   - [ ] Database unchanged after error

4. **Transaction Safety:**
   - [ ] Database counts EXACTLY match baseline after all failed imports
   - [ ] No partial data imported during validation failures
   - [ ] All validation errors prevent import execution

5. **User-Friendly Error Messages:**
   - [ ] Each error clearly identifies the problem
   - [ ] Errors explain what was expected vs what was found
   - [ ] No stack traces or technical errors exposed to users

### Full Verification (Optional)
If you have spreadsheet access:

6. **Spreadsheet Restoration (Step 16):**
   - [ ] Import succeeds after fixing schema version
   - [ ] Confirms validation allows valid spreadsheets
   - [ ] Validation not overly strict

## Common Issues & Solutions

### Issue 1: Cannot access spreadsheet (403 Forbidden)
**Symptoms:** Browser shows "You need permission to access this file"

**Causes:**
- Service account creates files in its own isolated Drive
- Human testers don't have access to service account's Drive

**Solutions:**
1. **Option A (Recommended):** Test validation using bot logs only
   - Bot logs will show validation errors even if you can't see spreadsheet
   - This is sufficient to verify validation logic works
2. **Option B:** Switch to OAuth user credentials temporarily
   - Update config.yaml to use OAuth credentials
   - Restart bot
   - Creates spreadsheets in your personal Drive
3. **Option C:** Implement sharing functionality (future enhancement)
   - Add sharing via Google Drive API
   - Service account can share files with specific users

**Code reference:** `chibi/backup/google_sheets_client.py:96-113` (credential type detection)

### Issue 2: Spreadsheet appears unchanged after deletion
**Symptoms:** Undo doesn't work, deleted sheets don't reappear

**Causes:**
- Browser caching
- Multiple undo operations needed
- Exceeded undo history

**Solutions:**
1. Create fresh export: `/export-progress` in Discord
2. Use new spreadsheet URL for subsequent tests
3. Close and reopen spreadsheet in new browser tab
4. Check "Version history" in Google Sheets for recovery

**Code reference:** `chibi/backup/sheets_exporter.py:102-139` (export process)

### Issue 3: Database modified despite validation error
**Symptoms:** Counts change after failed import

**Causes:**
- Transaction not rolled back correctly (BUG)
- Validation occurs after import started (BUG)
- Concurrent operations interfering

**Solutions:**
1. **If this happens, it's a critical bug** - report immediately
2. Restore from backup: `cp data/chibi.db.backup data/chibi.db`
3. Check logs for transaction errors
4. Verify foreign key enforcement: `sqlite3 data/chibi.db "PRAGMA foreign_keys;"`
5. Test in isolation (stop bot, restart, try again)

**Code reference:** `chibi/backup/sheets_importer.py:115-164` (validation happens BEFORE import)
**Code reference:** `chibi/backup/sheets_importer.py:296-357` (transaction with rollback)

### Issue 4: Error message unclear or missing details
**Symptoms:** Generic error like "Import failed" without specifics

**Causes:**
- Exception not caught properly
- ValidationError not raised correctly
- Discord embed truncation

**Solutions:**
1. Check bot logs for full error message
2. Look for Python traceback in logs
3. Verify ValidationError raised with descriptive message
4. Check character limits (Discord embeds max 1024 chars per field)

**Code reference:** `chibi/cogs/backup_cog.py:165-236` (error handling in Discord command)
**Code reference:** `chibi/backup/sheets_importer.py:17-26` (ValidationError class)

### Issue 5: Validation passes but should fail
**Symptoms:** Import proceeds despite missing/invalid schema

**Causes:**
- Validation logic bug
- Wrong sheet name checking
- Case sensitivity issues

**Solutions:**
1. **Report as bug** - validation should be strict
2. Check sheet names are exact matches (case-sensitive)
3. Verify REQUIRED_SHEETS constant: `chibi/backup/sheets_importer.py:36-43`
4. Check EXPECTED_SCHEMA_VERSION: `chibi/backup/sheets_importer.py:33`
5. Review validation logic: `chibi/backup/sheets_importer.py:115-164`

**Code reference:** `chibi/backup/sheets_importer.py:36-43` (REQUIRED_SHEETS list)

### Issue 6: Cannot create test spreadsheet
**Symptoms:** `/export-progress` fails, no URL returned

**Causes:**
- Google API not enabled
- Service account permissions insufficient
- Credentials file missing or invalid

**Solutions:**
1. Verify APIs enabled: Google Sheets API + Drive API
2. Check service account has Editor/Owner role
3. Verify credentials file: `ls -l google-credential.json`
4. Check bot logs for authentication errors
5. Review MT-002 manual testing guide for auth setup

**Code reference:** `chibi/backup/google_sheets_client.py:62-113` (authentication)

### Issue 7: Positive control test (Step 16) fails
**Symptoms:** Import fails even after restoring valid schema

**Causes:**
- Other modifications to spreadsheet during testing
- Data corrupted during sheet deletion/restoration
- Headers missing or modified

**Solutions:**
1. Create completely fresh export: `/export-progress`
2. Use new URL without any modifications
3. Verify this fresh export imports successfully
4. If fresh export fails, check MT-006 troubleshooting
5. Ensure all required columns present in each sheet

**Code reference:** `chibi/backup/sheets_importer.py:218-265` (table import logic)

## Implementation Details

### Validation Flow
```
import_from_sheets()
  ↓
_extract_spreadsheet_id()  // Parse URL to get spreadsheet ID
  ↓
_validate_schema()  // ← VALIDATION HAPPENS HERE (line 115-164)
  ├─ Check sheets list for "Metadata" (line 135-136)
  ├─ Check sheets list for all REQUIRED_SHEETS (line 139-144)
  ├─ Read Metadata sheet
  ├─ Parse metadata rows into dict
  └─ Check schema_version == "1.0" (line 156-161)
  ↓
IF VALIDATION FAILS → ValidationError raised → Transaction not started
  ↓
IF VALIDATION PASSES → Continue to import
  ↓
BEGIN TRANSACTION (line 296)
  ↓
Import data tables...
  ↓
COMMIT (line 350) or ROLLBACK on error
```

### Validation Code Location
- **Validation method:** `chibi/backup/sheets_importer.py:115-164`
- **Required sheets constant:** `chibi/backup/sheets_importer.py:36-43`
- **Schema version constant:** `chibi/backup/sheets_importer.py:33`
- **ValidationError class:** `chibi/backup/sheets_importer.py:17-26`
- **Error handling in Discord command:** `chibi/cogs/backup_cog.py:165-236`

### Why Schema Validation Matters
1. **Data Integrity:** Prevents importing malformed or incomplete data
2. **Database Safety:** Ensures transaction not started if schema invalid
3. **User Experience:** Provides clear error messages instead of cryptic SQL errors
4. **Version Compatibility:** Allows future schema migrations with backward compatibility checks
5. **Defensive Programming:** Validates external data before trusting it

## Test Completion Checklist

- [ ] All 18 steps completed
- [ ] All 5 minimum passing criteria met
- [ ] Database unchanged after validation errors (verified 3 times)
- [ ] Error messages are clear and actionable
- [ ] Positive control test passed (valid schema imports successfully)
- [ ] Database restored to original state (if desired)
- [ ] Test spreadsheet deleted to avoid quota issues

## Notes
- Estimated test duration: 20-30 minutes
- Requires spreadsheet editing access (may not be possible with service account)
- Can partially validate via bot logs even without spreadsheet access
- Database backup CRITICAL before starting destructive tests
- This test validates defensive programming practices

## Test Result

**Date:** _____________
**Tester:** _____________
**Result:** ☐ PASS  ☐ FAIL
**Notes:**

---

**Test Guide Version:** 1.0
**Associated Story:** MT-008
**Dependencies:** MT-003 (must have exported spreadsheet to test)
**Implementation Reference:** `chibi/backup/sheets_importer.py:115-164`
