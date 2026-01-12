# Manual E2E Testing: MT-009 - Import Error Handling and Rollback

## Test Objective
Verify that the import functionality properly handles errors during data import, rolls back transactions on failure, and leaves the database in its original state without any partial imports.

## Background
The SheetsImporter (`chibi/backup/sheets_importer.py:342-374`) uses SQLite transactions to ensure atomicity: either ALL data imports successfully, or NO changes are made to the database. The implementation:

1. **Transaction Wrapper** (line 346-367): Wraps all imports in BEGIN...COMMIT
2. **Foreign Key Enforcement** (line 344): Enables PRAGMA foreign_keys = ON before transaction
3. **Error Handling** (line 370-374): Catches exceptions, executes ROLLBACK, raises ImportError
4. **Row-Level Error Detection** (line 293-299): Catches and logs errors during INSERT operations

This test verifies that transaction rollback works correctly when errors occur during import, ensuring data integrity is maintained.

## Prerequisites

Before starting this test, verify:

- [ ] MT-006 passed (import functionality works)
- [ ] You have access to edit Google Spreadsheet (or can create OAuth test)
- [ ] Bot is running and you have admin permissions in Discord
- [ ] Database has existing data to preserve
- [ ] You have exported spreadsheet URL from a successful export

## Part 1: Prepare Baseline

### Step 1: Backup current database
```bash
# Create backup BEFORE any testing
cp data/chibi.db data/chibi.db.backup

# Verify backup exists
ls -lh data/chibi.db.backup
```

**Expected:** Backup file created with same size as chibi.db

### Step 2: Record current database state
```bash
# Record ALL table counts for verification later
echo "=== BASELINE DATABASE STATE ==="
sqlite3 data/chibi.db "SELECT COUNT(*) as user_count FROM users;"
sqlite3 data/chibi.db "SELECT COUNT(*) as quiz_attempt_count FROM quiz_attempts;"
sqlite3 data/chibi.db "SELECT COUNT(*) as concept_mastery_count FROM concept_mastery;"
sqlite3 data/chibi.db "SELECT COUNT(*) as llm_quiz_count FROM llm_quiz_attempts;"
sqlite3 data/chibi.db "SELECT COUNT(*) as attendance_count FROM attendance;"
```

**Record baseline counts:**
- `BASELINE_USERS = _____`
- `BASELINE_QUIZ_ATTEMPTS = _____`
- `BASELINE_CONCEPT_MASTERY = _____`
- `BASELINE_LLM_QUIZ = _____`
- `BASELINE_ATTENDANCE = _____`

### Step 3: Export data to create test spreadsheet
```bash
# In Discord, run export
/export-progress
```

**Expected:** Bot returns spreadsheet URL

**Record the URL:** `TEST_SPREADSHEET_URL = _________________`

**Important:** We'll modify this spreadsheet to inject invalid data for testing.

## Part 2: Test Foreign Key Constraint Violation

### Step 4: Open spreadsheet and inject invalid foreign key
In the spreadsheet browser tab:

1. Open the "QuizAttempts" sheet
2. Locate the "user_id" column (should be column B)
3. Find the first data row (row 2, below headers)
4. Change the user_id value to `99999` (a user_id that doesn't exist in Users table)
5. Press Enter to save the change

**Expected:** QuizAttempts sheet now has a quiz attempt with non-existent user_id

**Why this causes error:** Foreign key constraint requires every user_id in quiz_attempts to exist in users table. user_id=99999 doesn't exist.

### Step 5: Attempt import with invalid foreign key
```bash
# In Discord, run import in replace mode
/import-progress <TEST_SPREADSHEET_URL> mode:replace

# Click [Confirm] button when prompted
```

**Expected bot response:**
- ❌ Error embed displayed
- Error message mentions "FOREIGN KEY constraint failed" or similar
- Import fails and transaction rolls back

**Pass criteria:**
- Bot responds with error within 30 seconds
- Error mentions foreign key or constraint violation
- No success message appears

### Step 6: Verify database unchanged after foreign key error
```bash
# Check ALL counts match baseline exactly
echo "=== AFTER FOREIGN KEY ERROR ==="
sqlite3 data/chibi.db "SELECT COUNT(*) FROM users;"
sqlite3 data/chibi.db "SELECT COUNT(*) FROM quiz_attempts;"
sqlite3 data/chibi.db "SELECT COUNT(*) FROM concept_mastery;"
sqlite3 data/chibi.db "SELECT COUNT(*) FROM llm_quiz_attempts;"
sqlite3 data/chibi.db "SELECT COUNT(*) FROM attendance;"
```

**Expected:**
- `USERS = BASELINE_USERS` (unchanged)
- `QUIZ_ATTEMPTS = BASELINE_QUIZ_ATTEMPTS` (unchanged)
- `CONCEPT_MASTERY = BASELINE_CONCEPT_MASTERY` (unchanged)
- `LLM_QUIZ = BASELINE_LLM_QUIZ` (unchanged)
- `ATTENDANCE = BASELINE_ATTENDANCE` (unchanged)

**Critical Pass Criteria:** ALL counts EXACTLY match baseline. If ANY table has different count, rollback FAILED (critical bug).

### Step 7: Check bot logs for rollback confirmation
```bash
# If bot running in terminal, check recent logs
# Look for lines like:
#   "Import failed, transaction rolled back: ..."
#   "ROLLBACK"
```

**Expected log entries:**
- "Import failed, transaction rolled back: [error details]"
- No "Transaction committed successfully" message
- No "Import complete" message

**Pass criteria:** Logs confirm rollback occurred

## Part 3: Test Data Type Constraint Violation

### Step 8: Restore valid spreadsheet and inject type error
In the spreadsheet browser tab:

1. Undo previous change (Ctrl+Z / Cmd+Z) or re-export: `/export-progress`
2. Open the "Users" sheet
3. Find the "id" column (should be column A)
4. Find the first data row (row 2)
5. Change the id value from integer (e.g., `1`) to text (e.g., `ABC`)
6. Press Enter to save

**Expected:** Users sheet now has invalid data type for primary key

**Why this causes error:** id column is INTEGER PRIMARY KEY, cannot be text

### Step 9: Attempt import with type constraint violation
```bash
# In Discord, run import in replace mode
/import-progress <TEST_SPREADSHEET_URL> mode:replace

# Click [Confirm] button when prompted
```

**Expected bot response:**
- ❌ Error embed displayed
- Error may mention "invalid" or "type" or "datatype mismatch"
- Import fails and transaction rolls back

**Note:** SQLite is flexible with types, so this test might succeed with type coercion. That's acceptable behavior. If it succeeds, skip to Step 11.

### Step 10: Verify database unchanged after type error
```bash
# Check counts match baseline
echo "=== AFTER TYPE ERROR ==="
sqlite3 data/chibi.db "SELECT COUNT(*) FROM users;"
sqlite3 data/chibi.db "SELECT COUNT(*) FROM quiz_attempts;"
sqlite3 data/chibi.db "SELECT COUNT(*) FROM concept_mastery;"
```

**Expected:** All counts match baseline exactly

**Pass criteria:** Database unchanged by failed import

## Part 4: Test UNIQUE Constraint Violation

### Step 11: Restore valid spreadsheet and create duplicate
In the spreadsheet browser tab:

1. Undo previous changes or re-export: `/export-progress`
2. Open the "Users" sheet
3. Find the "discord_id" column (should be column B)
4. Note the discord_id value in row 2 (e.g., `123456789012345678`)
5. Scroll down to find another user row (e.g., row 3)
6. Change that row's discord_id to match row 2's discord_id (create duplicate)
7. Press Enter to save

**Expected:** Two users now have the same discord_id (violates UNIQUE constraint)

**Why this causes error:** discord_id column has UNIQUE constraint, duplicates not allowed

**Alternative method (if can't edit):**
1. Add a completely new row at the bottom of Users sheet
2. Copy all column values from row 2
3. This creates duplicate user with same discord_id

### Step 12: Attempt import with duplicate discord_id
```bash
# In Discord, run import in replace mode
/import-progress <TEST_SPREADSHEET_URL> mode:replace

# Click [Confirm] button when prompted
```

**Expected bot response:**
- ❌ Error embed displayed
- Error mentions "UNIQUE constraint failed" or "duplicate"
- Specifically mentions "discord_id" column
- Import fails and transaction rolls back

**Pass criteria:**
- Bot returns error within 30 seconds
- Error message mentions uniqueness violation
- No partial data imported

### Step 13: Verify database unchanged after UNIQUE error
```bash
# Final verification of transaction rollback
echo "=== AFTER UNIQUE CONSTRAINT ERROR ==="
sqlite3 data/chibi.db "SELECT COUNT(*) FROM users;"
sqlite3 data/chibi.db "SELECT COUNT(*) FROM quiz_attempts;"
sqlite3 data/chibi.db "SELECT COUNT(*) FROM concept_mastery;"
sqlite3 data/chibi.db "SELECT COUNT(*) FROM llm_quiz_attempts;"
sqlite3 data/chibi.db "SELECT COUNT(*) FROM attendance;"

# Verify specific discord_id not duplicated
sqlite3 data/chibi.db "SELECT discord_id, COUNT(*) FROM users GROUP BY discord_id HAVING COUNT(*) > 1;"
```

**Expected:**
- All counts match baseline exactly
- Duplicate discord_id query returns empty (no duplicates)

**Critical Pass Criteria:** Database completely unchanged after error

## Part 5: Test Partial Import Detection

### Step 14: Verify no partial imports occurred
This step verifies that the transaction rollback prevented ANY data from being imported, even if some tables processed successfully before the error occurred.

```bash
# Check for any rows that might have been partially imported
# Compare with pre-import counts (should be identical)

echo "=== DETAILED VERIFICATION ==="
echo "Users: Expected ${BASELINE_USERS}, Actual:"
sqlite3 data/chibi.db "SELECT COUNT(*) FROM users;"

echo "Quiz Attempts: Expected ${BASELINE_QUIZ_ATTEMPTS}, Actual:"
sqlite3 data/chibi.db "SELECT COUNT(*) FROM quiz_attempts;"

echo "Concept Mastery: Expected ${BASELINE_CONCEPT_MASTERY}, Actual:"
sqlite3 data/chibi.db "SELECT COUNT(*) FROM concept_mastery;"

echo "LLM Quiz: Expected ${BASELINE_LLM_QUIZ}, Actual:"
sqlite3 data/chibi.db "SELECT COUNT(*) FROM llm_quiz_attempts;"

echo "Attendance: Expected ${BASELINE_ATTENDANCE}, Actual:"
sqlite3 data/chibi.db "SELECT COUNT(*) FROM attendance;"
```

**Expected:** Every single count EXACTLY matches baseline

**Pass criteria:**
- No new rows in ANY table
- No deleted rows in ANY table
- No modified rows in ANY table
- Transaction atomicity preserved

### Step 15: Check specific data integrity
```bash
# Verify specific records haven't changed
# Pick a specific user and verify their data

sqlite3 data/chibi.db "SELECT id, discord_id, username FROM users WHERE id = 1;"

# Verify quiz attempts for that user
sqlite3 data/chibi.db "SELECT COUNT(*) FROM quiz_attempts WHERE user_id = 1;"
```

**Expected:**
- User data identical to before test
- Quiz attempt counts unchanged
- No data corruption

**Pass criteria:** Spot-check confirms data integrity maintained

## Part 6: Test Positive Control (Valid Import)

### Step 16: Import valid spreadsheet to confirm rollback didn't break functionality
```bash
# Create completely fresh export (no modifications)
# In Discord:
/export-progress

# Copy the new URL, then immediately import it
/import-progress <NEW_UNMODIFIED_URL> mode:replace

# Click [Confirm]
```

**Expected bot response:**
- ✅ Success embed displayed
- Shows counts of imported records
- Import completes successfully
- "Transaction committed successfully" in logs

**Pass criteria:**
- Import succeeds without errors
- Confirms rollback mechanism didn't damage database
- Confirms error handling doesn't affect valid imports

### Step 17: Verify successful import worked
```bash
# Check counts after successful import
echo "=== AFTER SUCCESSFUL IMPORT ==="
sqlite3 data/chibi.db "SELECT COUNT(*) FROM users;"
sqlite3 data/chibi.db "SELECT COUNT(*) FROM quiz_attempts;"
```

**Expected:** Counts should match the export (baseline counts if nothing changed)

**Pass criteria:** Valid import processes successfully after previous errors

## Part 7: Cleanup

### Step 18: Restore original database (optional)
```bash
# If you want to restore original state
cp data/chibi.db.backup data/chibi.db

# Verify restoration
sqlite3 data/chibi.db "SELECT COUNT(*) FROM users;"

# Restart bot to clear caches
# (Ctrl+C in bot terminal, then: python main.py)
```

### Step 19: Delete test spreadsheets
Delete test spreadsheets from Google Drive to avoid quota issues.

**Note:** If using service account, spreadsheets are in service account's Drive (may not be visible).

## Pass/Fail Criteria

### Minimum Passing Criteria (Required)
All of the following MUST be true for MT-009 to pass:

1. **Foreign Key Constraint Violation (Steps 4-7):**
   - [ ] Import fails with foreign key error
   - [ ] Database counts EXACTLY match baseline after error
   - [ ] Bot logs show "transaction rolled back"
   - [ ] No partial data imported

2. **Data Type Constraint Violation (Steps 8-10):**
   - [ ] Import fails OR succeeds with type coercion (both acceptable)
   - [ ] If fails: database counts match baseline exactly
   - [ ] If succeeds: that's acceptable SQLite behavior

3. **UNIQUE Constraint Violation (Steps 11-13):**
   - [ ] Import fails with UNIQUE constraint error
   - [ ] Error mentions "discord_id" or "UNIQUE"
   - [ ] Database counts EXACTLY match baseline after error
   - [ ] No duplicate discord_id values created

4. **Transaction Atomicity (Steps 14-15):**
   - [ ] ALL tables unchanged after ANY error
   - [ ] No partial imports (all-or-nothing principle)
   - [ ] Specific data spot-checks confirm integrity
   - [ ] Transaction rollback prevents ANY database changes

5. **Error Messages (Throughout):**
   - [ ] Each error clearly describes the problem
   - [ ] Errors mention specific constraint violated
   - [ ] No stack traces exposed to end users
   - [ ] Logs contain detailed error information for debugging

6. **Positive Control (Steps 16-17):**
   - [ ] Valid import succeeds after errors
   - [ ] Confirms rollback didn't break functionality
   - [ ] Import mechanism still works correctly

### Full Verification (Optional)
If you have spreadsheet access:

7. **Spreadsheet Editing:**
   - [ ] All three constraint violations tested
   - [ ] Each violation triggers appropriate error
   - [ ] Spreadsheet modifications clearly documented

## Common Issues & Solutions

### Issue 1: Cannot edit spreadsheet (service account isolation)
**Symptoms:** Browser shows "You need permission to access this file"

**Causes:**
- Service account creates files in isolated Drive
- Human testers don't have edit access

**Solutions:**
1. **Option A (Recommended):** Create test data directly in SQLite
   - Temporarily modify chibi.db to create invalid state
   - Export invalid data to spreadsheet
   - Then import to test rollback
2. **Option B:** Switch to OAuth credentials temporarily
   - Update config.yaml to use OAuth
   - Restart bot
   - Creates spreadsheets in your personal Drive (editable)
3. **Option C:** Test via bot code modification
   - Temporarily inject errors in import logic
   - Verify rollback works with code-level errors
4. **Option D:** Use Google Sheets API
   - Write script to modify spreadsheet via API
   - Service account can modify its own files

**Code reference:** `chibi/backup/google_sheets_client.py:96-113` (authentication)

### Issue 2: Foreign key constraint NOT enforced
**Symptoms:** Import succeeds despite invalid user_id reference

**Causes:**
- SQLite foreign keys not enabled
- Database created without foreign key support
- PRAGMA foreign_keys = OFF

**Solutions:**
1. Check foreign key status: `sqlite3 data/chibi.db "PRAGMA foreign_keys;"`
2. Should return `1` (enabled). If `0` (disabled), that's a bug
3. Verify code enables foreign keys: `sheets_importer.py:344`
4. Check database schema has FOREIGN KEY constraints: `.schema quiz_attempts`
5. If foreign keys not enabled, report as critical bug

**Code reference:** `chibi/backup/sheets_importer.py:344` (PRAGMA foreign_keys = ON)

### Issue 3: Database modified despite error message
**Symptoms:** Counts change after "failed" import

**Causes:**
- Transaction not rolled back (CRITICAL BUG)
- ROLLBACK command not executed
- COMMIT executed despite error
- Multiple concurrent imports interfering

**Solutions:**
1. **If this happens, it's a CRITICAL BUG** - report immediately
2. Restore from backup: `cp data/chibi.db.backup data/chibi.db`
3. Check logs for transaction flow
4. Verify exception handler executes ROLLBACK: `sheets_importer.py:370-374`
5. Test in isolation (restart bot, single import attempt)
6. Check for concurrent import operations

**Code reference:** `chibi/backup/sheets_importer.py:370-374` (rollback on error)

### Issue 4: Error message doesn't describe specific problem
**Symptoms:** Generic "Import failed" without details

**Causes:**
- Exception details lost in error handling
- ImportError message too generic
- Discord embed truncation

**Solutions:**
1. Check bot logs for full error traceback
2. Look for logger.error() messages with details
3. Verify ImportError includes original exception: `sheets_importer.py:374`
4. Check Discord embed field limits (1024 chars)
5. Error should propagate to Discord command handler

**Code reference:** `chibi/backup/sheets_importer.py:296-299` (row-level error logging)
**Code reference:** `chibi/cogs/backup_cog.py:165-236` (Discord error handling)

### Issue 5: Positive control test fails (Step 16)
**Symptoms:** Valid import fails after rollback tests

**Causes:**
- Database corrupted by previous errors (rollback bug)
- Connection pool exhausted
- Transaction still open from previous import
- Database locked

**Solutions:**
1. Restart bot to reset connection state
2. Check database integrity: `sqlite3 data/chibi.db "PRAGMA integrity_check;"`
3. Restore from backup: `cp data/chibi.db.backup data/chibi.db`
4. Verify no orphaned transactions: check logs for "BEGIN" without "COMMIT"
5. Test fresh export (create completely new spreadsheet)

**Code reference:** `chibi/backup/sheets_importer.py:342-368` (transaction lifecycle)

### Issue 6: Type constraint violation doesn't fail
**Symptoms:** Import succeeds even with ABC as integer id

**Causes:**
- SQLite allows flexible typing (by design)
- Type affinity coerces text to integer if possible
- This is EXPECTED behavior, not a bug

**Solutions:**
1. This is acceptable SQLite behavior
2. Skip to UNIQUE constraint test (Step 11)
3. Focus on foreign key and uniqueness constraints
4. Type safety relies on application logic, not SQLite enforcement
5. If you want strict types, must validate in application layer

**Reference:** SQLite type affinity documentation

### Issue 7: All tests fail with authentication error
**Symptoms:** Cannot read spreadsheet, "Failed to fetch sheets list"

**Causes:**
- Credentials expired
- API quota exceeded
- Service account permissions revoked
- Network connectivity issues

**Solutions:**
1. Verify credentials valid: check expiration dates
2. Test authentication separately: `/list-exports`
3. Check Google Cloud Console for API quotas
4. Verify APIs still enabled (Sheets + Drive)
5. Review MT-002 troubleshooting for auth issues

**Code reference:** `chibi/backup/google_sheets_client.py:62-113` (authentication)

### Issue 8: Baseline counts change between tests
**Symptoms:** Counts don't match baseline even though import failed

**Causes:**
- Concurrent bot operations (other users taking quizzes)
- Background tasks modifying database
- Multiple test runs without restoration

**Solutions:**
1. Run tests in isolated environment (test server)
2. Disable bot commands during testing
3. Record NEW baseline before each test part
4. Use dedicated test database: `cp data/chibi.db data/test.db`
5. Pause bot during critical measurements

**Best practice:** Stop bot, run tests, start bot

## Implementation Details

### Transaction Flow
```
import_from_sheets()
  ↓
_extract_spreadsheet_id()
  ↓
_validate_schema()  // Schema validation BEFORE transaction
  ↓
conn.execute("PRAGMA foreign_keys = ON")  // Enable constraints
  ↓
conn.execute("BEGIN")  // ← START TRANSACTION
  ↓
_import_table("Users", ...)  // Import parent table first
  ↓
_import_table("QuizAttempts", ...)  // Import child tables
  ↓
_import_table("ConceptMastery", ...)
  ↓
_import_table("LLMQuizAttempts", ...)
  ↓
_import_table("Attendance", ...)
  ↓
IF ANY ERROR → conn.execute("ROLLBACK") → ImportError raised
  ↓
IF SUCCESS → conn.commit() → return result dict
```

### Error Handling Code Locations
- **Transaction wrapper:** `chibi/backup/sheets_importer.py:342-374`
- **Foreign key enforcement:** `chibi/backup/sheets_importer.py:344`
- **Begin transaction:** `chibi/backup/sheets_importer.py:347`
- **Row-level error catching:** `chibi/backup/sheets_importer.py:293-299`
- **Rollback on error:** `chibi/backup/sheets_importer.py:370-374`
- **Commit on success:** `chibi/backup/sheets_importer.py:367`
- **Discord error handling:** `chibi/cogs/backup_cog.py:165-236`

### Why Transaction Rollback Matters
1. **Data Integrity:** Prevents partial imports that would corrupt database
2. **Consistency:** Ensures database remains in valid state after errors
3. **Atomicity:** All-or-nothing principle for multi-table imports
4. **Referential Integrity:** Foreign keys maintained across all tables
5. **User Trust:** Users can retry failed imports without cleanup

### SQLite Transaction Guarantees
- BEGIN starts transaction, COMMIT finalizes, ROLLBACK undoes
- All operations between BEGIN and COMMIT are atomic
- ROLLBACK restores database to state before BEGIN
- Foreign keys enforced within transaction when enabled
- Connection must stay open for entire transaction

## Test Completion Checklist

- [ ] All 19 steps completed
- [ ] All 6 minimum passing criteria met
- [ ] Database unchanged after each error (verified 3 times)
- [ ] Transaction rollback confirmed in logs
- [ ] No partial imports detected
- [ ] Positive control test passed
- [ ] Database restored to original state
- [ ] Test spreadsheets deleted

## Notes
- Estimated test duration: 30-45 minutes
- Requires spreadsheet editing access (may need OAuth setup)
- Database backup CRITICAL before starting
- Transaction rollback is most critical feature to verify
- Partial imports would be catastrophic in production

## Test Result

**Date:** _____________
**Tester:** _____________
**Result:** ☐ PASS  ☐ FAIL
**Notes:**

---

**Test Guide Version:** 1.0
**Associated Story:** MT-009
**Dependencies:** MT-006 (import functionality must work)
**Implementation Reference:** `chibi/backup/sheets_importer.py:342-374`
