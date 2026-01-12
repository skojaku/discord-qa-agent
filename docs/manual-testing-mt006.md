# Manual Testing Guide: MT-006 - Import to Clean Database (Replace Mode)

## Test ID: MT-006
**Title:** Import to clean database (replace mode)
**Priority:** 3 (Core Functionality - Import)
**Category:** Import
**Prerequisites:** MT-003 passed (have exported spreadsheet to import from)

---

## Objective

Verify that the `/import-progress` command can successfully restore student progress data from a Google Sheets export to an empty database using replace mode, maintaining data integrity and foreign key relationships.

---

## Background

The import feature reads data from a Google Sheets spreadsheet and restores it to the SQLite database. This test focuses on **replace mode**, which:

1. Deletes all existing data from tables (DELETE FROM)
2. Inserts new rows from the spreadsheet
3. Maintains referential integrity (foreign keys)
4. Preserves data types through reverse transformations

**Implementation details:**
- Importer: `chibi/backup/sheets_importer.py`
- Data transformations: ""→NULL, "TRUE"/"FALSE"→1/0, numeric strings→int/float
- Import modes: replace (DELETE then INSERT) vs merge (INSERT OR REPLACE)
- Transaction safety: ROLLBACK on any error
- Foreign key enforcement: `PRAGMA foreign_keys = ON`

**Use cases:**
- Restoring data after server migration
- Recovering from database corruption
- Setting up test environment with production data
- Disaster recovery

---

## Prerequisites Checklist

Before starting:

- [ ] MT-003 passed (basic export functionality working)
- [ ] You have a Google Sheets export URL from MT-003 or MT-005
- [ ] Bot is running (`uv run python main.py`)
- [ ] You have admin permissions in the test Discord server
- [ ] You have access to sqlite3 command-line tool
- [ ] Database backup created (current data is valuable)

---

## Part 1: Prepare for Import

### Step 1: Create or Identify Export to Import

**Option A: Use existing export from MT-003/MT-005**

If you completed MT-003 or MT-005, locate the Google Sheets URL from those tests.

**Option B: Create fresh export**

If you don't have an export, create one now:

```
# In Discord, as admin:
/export-progress
```

Copy the Google Sheets URL from the bot response.

**Expected:** You have a valid Google Sheets URL starting with `https://docs.google.com/spreadsheets/d/...`

---

### Step 2: Record Pre-Import Baseline

Record current database state for comparison:

```bash
sqlite3 data/chibi.db <<EOF
.mode column
SELECT
  (SELECT COUNT(*) FROM users) as users,
  (SELECT COUNT(*) FROM quiz_attempts) as quiz_attempts,
  (SELECT COUNT(*) FROM concept_mastery) as concept_mastery,
  (SELECT COUNT(*) FROM llm_quiz_attempts) as llm_quiz_attempts,
  (SELECT COUNT(*) FROM attendance) as attendance;
EOF
```

**Write these numbers down** as "PRE-IMPORT COUNTS".

---

### Step 3: Inspect Export Spreadsheet Metadata

Open the Google Sheets URL in your browser (if accessible). Navigate to the **Metadata** sheet.

**Record these values** from the Metadata sheet:

```
export_date: [timestamp]
schema_version: [version]
users_count: [number]
quiz_attempts_count: [number]
concept_mastery_count: [number]
llm_quiz_attempts_count: [number]
attendance_count: [number]
```

**Write these numbers down** as "EXPORT COUNTS". These are the counts we expect to restore.

**Note:** If using service account credentials, you may not have access to view the spreadsheet. That's okay - you can proceed with the test and verify via bot response and database queries.

---

## Part 2: Clear Database and Create Clean State

### Step 4: Backup Current Database

Preserve your current data before clearing:

```bash
cd /Users/skojaku-admin/Documents/projects/applied-soft-comp/tutor/discord-qa-agent
cp data/chibi.db data/chibi.db.backup-mt006
```

**Expected:** Backup file created successfully.

---

### Step 5: Delete Current Database

Remove the database entirely to simulate a clean server:

```bash
rm data/chibi.db
```

**Expected:** Database file deleted.

**Verify:**
```bash
ls data/chibi.db
# Should show: No such file or directory
```

---

### Step 6: Restart Bot to Create Empty Schema

Stop and restart the bot to trigger schema initialization:

```bash
# Stop the running bot (Ctrl+C or kill process)
# Then start it again:
uv run python main.py
```

**Expected:**
- Bot starts successfully
- Log messages show: "Initializing database schema"
- No errors during startup
- BackupService initialized

---

### Step 7: Verify Empty Database with Schema

Check that tables exist but are empty:

```bash
sqlite3 data/chibi.db <<EOF
.tables
EOF
```

**Expected:** You should see all tables listed:
```
attendance         llm_quiz_attempts  users
concept_mastery    quiz_attempts
```

Now verify they're empty:

```bash
sqlite3 data/chibi.db <<EOF
.mode column
SELECT
  (SELECT COUNT(*) FROM users) as users,
  (SELECT COUNT(*) FROM quiz_attempts) as quiz_attempts,
  (SELECT COUNT(*) FROM concept_mastery) as concept_mastery,
  (SELECT COUNT(*) FROM llm_quiz_attempts) as llm_quiz_attempts,
  (SELECT COUNT(*) FROM attendance) as attendance;
EOF
```

**Expected Output:**
```
users  quiz_attempts  concept_mastery  llm_quiz_attempts  attendance
-----  -------------  ---------------  -----------------  ----------
0      0              0                0                  0
```

**Pass Criterion #1:** Database has schema but zero rows in all tables.

---

## Part 3: Execute Import with Replace Mode

### Step 8: Run Import Command

In Discord, run the import command with your spreadsheet URL:

```
/import-progress url:<PASTE_SPREADSHEET_URL_HERE> mode:replace
```

**Important:** Replace `<PASTE_SPREADSHEET_URL_HERE>` with actual URL from Step 1.

**Expected:** Bot responds with confirmation prompt.

---

### Step 9: Confirm Import Operation

The bot will show a confirmation message:

```
⚠️ Confirm Import (Replace Mode)

This will DELETE all existing student progress data and replace it with data from the spreadsheet.

Current database counts:
• Users: 0
• Quiz Attempts: 0
• Concept Mastery: 0
• LLM Quiz Attempts: 0
• Attendance: 0

Are you sure you want to proceed?

[Confirm] [Cancel]
```

Click the **[Confirm]** button.

---

### Step 10: Wait for Import Completion

The bot will process the import. This may take 10-30 seconds depending on data size.

**Expected Response Format:**
```
✅ Import Complete

Successfully imported student progress data from Google Sheets.

📊 Import Summary:
Mode: replace
• Users: 15 imported
• Quiz Attempts: 75 imported
• Concept Mastery: 30 imported
• LLM Quiz Attempts: 0 imported
• Attendance: 0 imported

✅ All data imported successfully.

Import completed at: 2026-01-12 11:15:30
```

**Pass Criterion #2:** Import completes without errors.

**Pass Criterion #3:** Import counts match EXPORT COUNTS from Step 3.

---

### Step 11: Check Bot Logs for Import Details

Check bot logs for detailed import operations:

```bash
# If running in terminal, scroll up to see logs
# Look for messages like:
# "Starting import from spreadsheet: ..."
# "Validating schema..."
# "Schema validation passed"
# "Starting import with mode: replace"
# "Importing users table: X rows"
# "Importing quiz_attempts table: X rows"
# "Import completed successfully"
```

**Expected Log Entries:**
- "Validating schema..."
- "Schema validation passed"
- "Starting import with mode: replace"
- "PRAGMA foreign_keys = ON" (foreign key enforcement)
- "Deleting existing data from [table]" for each table
- "Importing [table]: X rows"
- "Import completed successfully"
- No error messages or rollback messages

**Pass Criterion #4:** Logs show successful import with no errors.

---

## Part 4: Verify Data Restoration

### Step 12: Query Database Counts

Verify data was restored correctly:

```bash
sqlite3 data/chibi.db <<EOF
.mode column
SELECT
  (SELECT COUNT(*) FROM users) as users,
  (SELECT COUNT(*) FROM quiz_attempts) as quiz_attempts,
  (SELECT COUNT(*) FROM concept_mastery) as concept_mastery,
  (SELECT COUNT(*) FROM llm_quiz_attempts) as llm_quiz_attempts,
  (SELECT COUNT(*) FROM attendance) as attendance;
EOF
```

**Expected:** Counts match EXPORT COUNTS from Step 3 and bot response from Step 10.

**Pass Criterion #5:** Database counts match expected values.

---

### Step 13: Verify Data Types and Conversions

Check that data types were converted correctly:

**Test 1: Boolean conversion (TRUE/FALSE → 1/0)**

```bash
sqlite3 data/chibi.db "SELECT is_correct FROM quiz_attempts LIMIT 5;"
```

**Expected:** Should see 0 or 1 values (not "TRUE" or "FALSE" strings).

**Test 2: NULL handling (empty → NULL)**

```bash
sqlite3 data/chibi.db "SELECT COUNT(*) FROM users WHERE student_id IS NULL;"
```

**Expected:** Should see count > 0 if any users don't have student IDs.

**Test 3: Timestamp preservation**

```bash
sqlite3 data/chibi.db "SELECT created_at FROM users LIMIT 3;"
```

**Expected:** Should see ISO format timestamps like `2025-12-15T10:30:45`.

**Pass Criterion #6:** All data types converted correctly.

---

### Step 14: Verify Foreign Key Relationships

Check that foreign key relationships are intact:

```bash
sqlite3 data/chibi.db <<EOF
.mode column
SELECT u.id, u.username, COUNT(q.id) as quiz_count
FROM users u
LEFT JOIN quiz_attempts q ON u.id = q.user_id
GROUP BY u.id
LIMIT 5;
EOF
```

**Expected:** Should see users with their quiz attempt counts.

**Verify no orphaned records:**

```bash
sqlite3 data/chibi.db "SELECT COUNT(*) FROM quiz_attempts WHERE user_id NOT IN (SELECT id FROM users);"
```

**Expected:** Should return `0` (no orphaned quiz attempts).

**Pass Criterion #7:** Foreign key relationships maintained, no orphaned records.

---

### Step 15: Test Foreign Key Constraints

Attempt to delete a user with quiz attempts (should fail due to foreign key constraint):

```bash
sqlite3 data/chibi.db "DELETE FROM users WHERE id = (SELECT user_id FROM quiz_attempts LIMIT 1);"
```

**Expected:** Error message like:
```
Error: FOREIGN KEY constraint failed
```

This confirms foreign key constraints are enforced.

**Pass Criterion #8:** Foreign key constraints enforced.

---

## Part 5: Verify Bot Functionality with Restored Data

### Step 16: Test /status Command

In Discord, run:

```
/status
```

**Expected:**
- Bot responds with your progress summary
- Shows modules and concept mastery
- Data reflects restored state
- No errors

**Pass Criterion #9:** Bot commands work with restored data.

---

### Step 17: Test /modules Command

In Discord, run:

```
/modules
```

**Expected:**
- Bot lists all course modules
- Shows student progress (if any)
- No errors

---

### Step 18: Query Specific User Data

Check that a specific user's data is complete:

```bash
sqlite3 data/chibi.db <<EOF
.mode column
SELECT username, discord_id, created_at, review_status FROM users LIMIT 3;
EOF
```

**Expected:** User records with complete data (no missing fields).

```bash
sqlite3 data/chibi.db <<EOF
.mode column
SELECT u.username, q.question, q.is_correct, q.quiz_timestamp
FROM quiz_attempts q
JOIN users u ON q.user_id = u.id
LIMIT 5;
EOF
```

**Expected:** Quiz attempts properly linked to users with complete data.

**Pass Criterion #10:** All restored data is complete and accessible.

---

## Part 6: Cleanup (Optional)

### Step 19: Keep Restored Data or Restore Original

**Option A: Keep restored data**

If you want to keep the restored data, you're done! The database now has the imported data.

**Option B: Restore original database**

If you want to restore your pre-test database:

```bash
cd /Users/skojaku-admin/Documents/projects/applied-soft-comp/tutor/discord-qa-agent
cp data/chibi.db.backup-mt006 data/chibi.db
```

**Expected:** Original database restored.

**Verify restoration:**

```bash
sqlite3 data/chibi.db "SELECT COUNT(*) FROM users; SELECT COUNT(*) FROM quiz_attempts;"
```

**Expected:** Counts match PRE-IMPORT COUNTS from Step 2.

---

## Pass/Fail Criteria

### Minimum Passing Criteria (Steps 1-15)

This test **PASSES** if ALL of the following are true:

1. ✅ Database created with empty schema (Step 7)
2. ✅ Import completes without errors (Step 10)
3. ✅ Import counts match export counts (Step 10)
4. ✅ Logs show successful import with no errors (Step 11)
5. ✅ Database counts match expected values (Step 12)
6. ✅ Data types converted correctly (Step 13)
7. ✅ Foreign key relationships maintained (Step 14)
8. ✅ Foreign key constraints enforced (Step 15)
9. ✅ Bot commands work with restored data (Steps 16-17)
10. ✅ All restored data is complete and accessible (Step 18)

### Full Verification (Optional Step 19)

If you restored original database, additionally verify:

11. ✅ Original database restored successfully
12. ✅ Bot continues to work after restoration

**Note:** The test can pass based on criteria 1-10 alone.

---

## Common Issues and Troubleshooting

### Issue 1: "Spreadsheet not found or access denied"

**Symptoms:** Bot responds with error about spreadsheet access.

**Possible Causes:**
- Invalid spreadsheet URL
- Service account doesn't have access to the spreadsheet
- Spreadsheet was deleted
- Network connectivity issues

**Solutions:**
1. Verify URL is correct (starts with `https://docs.google.com/spreadsheets/d/`)
2. Check spreadsheet still exists by opening in browser
3. If using service account: Ensure spreadsheet was created by same service account
4. Try exporting again (/export-progress) and use the new URL
5. Check bot logs for detailed error message

**Code Reference:** `chibi/backup/sheets_importer.py:296-310` (import_from_sheets method)

---

### Issue 2: "Schema validation failed: Missing Metadata sheet"

**Symptoms:** Import fails with schema validation error.

**Possible Causes:**
- Spreadsheet format is incorrect
- Metadata sheet was deleted or renamed
- Using wrong spreadsheet (not a Chibi export)

**Solutions:**
1. Open spreadsheet and verify Metadata sheet exists
2. Check Metadata sheet has required fields (export_date, schema_version, etc.)
3. Re-export data to create valid spreadsheet
4. Use a different export URL from a valid export

**Code Reference:** `chibi/backup/sheets_importer.py:90-124` (_validate_schema method)

---

### Issue 3: Import completes but counts don't match

**Symptoms:** Bot says "import complete" but database counts differ from export counts.

**Possible Causes:**
- Empty rows in spreadsheet (skipped during import)
- Data filtering logic excluding some records
- Concurrent database modifications during import
- Bug in import logic

**Solutions:**
1. Re-run count queries (Step 12) to confirm mismatch
2. Check for empty rows in spreadsheet that would be skipped
3. Ensure no other processes writing to database during import
4. Check bot logs for "Skipped X empty rows" messages
5. If persistent, report as bug with specific counts

**Code Reference:** `chibi/backup/sheets_importer.py:210-268` (_import_table method)

---

### Issue 4: Foreign key constraint errors during import

**Symptoms:** Import fails with "FOREIGN KEY constraint failed" error.

**Possible Causes:**
- Parent records missing (users deleted but quiz_attempts reference them)
- Import order incorrect (child tables before parent tables)
- Data corruption in export
- IDs don't match between tables

**Solutions:**
1. Verify export spreadsheet has all required parent records
2. Check import order in logs (users should be imported before quiz_attempts)
3. Inspect spreadsheet for orphaned references
4. Re-export from a known-good database state
5. Check Users sheet has all user IDs referenced in QuizAttempts sheet

**Code Reference:** `chibi/backup/sheets_importer.py:221-223` (foreign key enforcement)

---

### Issue 5: Transaction rollback after partial import

**Symptoms:** Import starts but rolls back, no data imported.

**Possible Causes:**
- Database constraint violation (unique, not null, foreign key)
- Data type mismatch (string where integer expected)
- Disk space full
- Database locked by another process

**Solutions:**
1. Check bot logs for specific error message before rollback
2. Verify database is not locked: `lsof data/chibi.db`
3. Check disk space: `df -h`
4. Inspect spreadsheet data for invalid values (malformed dates, non-numeric IDs)
5. Verify schema version matches (Metadata sheet vs database)
6. Try with smaller dataset to isolate issue

**Code Reference:** `chibi/backup/sheets_importer.py:315-322` (exception handling and rollback)

---

### Issue 6: Bot doesn't restart after database deletion

**Symptoms:** Bot fails to start after `rm data/chibi.db`.

**Possible Causes:**
- Database initialization error
- Migration issues
- File permissions

**Solutions:**
1. Check bot logs for startup errors
2. Verify data/ directory exists and is writable
3. Try manually creating empty database: `touch data/chibi.db`
4. Check schema initialization in: `chibi/database/connection.py:_init_schema()`
5. Ensure bot has write permissions to data/ directory

---

### Issue 7: Data restored but bot commands don't work

**Symptoms:** Database has data but /status shows no progress.

**Possible Causes:**
- Discord user IDs don't match (test data vs real users)
- Cache not cleared after import
- Bot needs restart
- User repository query issues

**Solutions:**
1. Restart bot to clear caches
2. Check discord_id values in users table match real Discord user IDs
3. Test with admin commands that don't depend on user context
4. Verify user exists in database: `sqlite3 data/chibi.db "SELECT * FROM users WHERE discord_id='YOUR_DISCORD_ID';"`
5. If using test data, discord_id values may not match real users

---

## Expected Results Summary

**Import Performance:**
- Import duration: 10-30 seconds for typical datasets
- No errors or rollback operations
- Transaction completes successfully

**Data Integrity:**
- All counts match export baseline
- No data loss or corruption
- Foreign key relationships maintained
- Data type conversions correct (TRUE/FALSE→1/0, empty→NULL)

**System State:**
- Bot commands work with restored data
- Foreign key constraints enforced
- Database in consistent state
- Original functionality preserved

**Use Case Validation:**
- Data successfully transferred between servers
- Disaster recovery scenario validated
- Test environment setup validated

---

## Additional Notes

**Replace Mode Behavior:**
- Deletes ALL existing data from each table
- Inserts new rows from spreadsheet
- Uses DELETE + INSERT (not TRUNCATE)
- Maintains table structure and constraints
- Resets auto-increment counters (IDs preserved from export)

**Data Ordering:**
- Import order: Users → QuizAttempts → ConceptMastery → LLMQuizAttempts → Attendance
- Parent tables imported before child tables (respects foreign keys)
- Rows imported in spreadsheet order

**Transaction Safety:**
- All imports wrapped in single transaction
- ROLLBACK on any error (no partial imports)
- Foreign keys enforced during import
- Database unchanged if import fails

**ID Preservation:**
- User IDs from export are preserved in import
- Foreign key references remain valid
- Auto-increment counters adjusted accordingly

**Future Enhancements:**
- Progress bar for long imports
- Dry-run mode to preview import without committing
- Partial import (selected tables only)
- Conflict resolution strategies for merge mode

---

## Test Complete

If all pass criteria met, mark **MT-006 as PASSED** in `prd.json`.

Document any issues encountered in `docs/manual-testing-log.md` (if it exists) or create a GitHub issue for tracking.

---

## Related Tests

- **MT-003:** Basic export (creates the export to import)
- **MT-007:** Import with merge mode (alternative to replace mode)
- **MT-008:** Import schema validation (tests invalid inputs)
- **MT-009:** Import error handling (tests transaction rollback)
- **MT-011:** Cross-machine data transfer (uses replace mode for migration)
