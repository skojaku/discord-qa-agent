# Manual E2E Testing: MT-011 - Cross-Machine Data Transfer

## Test Objective
Verify that student progress data can be successfully transferred from one bot instance to another using the export/import functionality, simulating the real-world use case of migrating a Discord bot to a new server or recovering from a disaster.

## Background
The backup feature's primary use case is enabling data portability between bot instances. This test validates the complete workflow:

1. **Export** from Machine A: Student data exported to Google Sheets
2. **Transfer** via cloud: Spreadsheet URL is the only transfer medium needed
3. **Import** to Machine B: Data restored from spreadsheet to fresh database
4. **Verification**: Bot functions correctly with restored data

This workflow enables:
- Server migration (moving bot to new hosting environment)
- Disaster recovery (restoring after database loss)
- Development/testing (copying production data to test environment)
- Bot instance replication (multiple servers with synchronized data)

## Prerequisites

Before starting this test, verify:

- [ ] MT-003 passed (export functionality works)
- [ ] MT-006 passed (import to clean database works)
- [ ] Bot is running and you have admin permissions
- [ ] Database has existing student progress data to transfer
- [ ] You have terminal/command-line access to bot server

## Part 1: Prepare Machine A (Source)

### Step 1: Verify Machine A has data to transfer
```bash
# Verify database has student progress data
echo "=== MACHINE A DATABASE STATE ==="#
sqlite3 data/chibi.db "SELECT COUNT(*) as total_users FROM users;"
sqlite3 data/chibi.db "SELECT COUNT(*) as total_quiz_attempts FROM quiz_attempts;"
sqlite3 data/chibi.db "SELECT COUNT(*) as total_concept_mastery FROM concept_mastery;"
sqlite3 data/chibi.db "SELECT COUNT(*) as total_llm_quiz FROM llm_quiz_attempts;"
sqlite3 data/chibi.db "SELECT COUNT(*) as total_attendance FROM attendance;"
```

**Record Machine A counts:**
- `MACHINE_A_USERS = _____`
- `MACHINE_A_QUIZ_ATTEMPTS = _____`
- `MACHINE_A_CONCEPT_MASTERY = _____`
- `MACHINE_A_LLM_QUIZ = _____`
- `MACHINE_A_ATTENDANCE = _____`

**Expected:** At least some data exists (not all zeros)

**Pass criteria:** Database contains student progress to transfer

### Step 2: Sample specific records for verification
```bash
# Record specific records to verify after transfer
echo "=== SAMPLE RECORDS FROM MACHINE A ==="
sqlite3 data/chibi.db "SELECT id, discord_id, username FROM users LIMIT 3;"
sqlite3 data/chibi.db "SELECT id, user_id, module, is_correct FROM quiz_attempts WHERE user_id=1 LIMIT 3;"
```

**Record details:**
- `USER_1_ID = _____`
- `USER_1_DISCORD_ID = _____`
- `USER_1_USERNAME = _____`
- `USER_1_QUIZ_COUNT = _____`

**Purpose:** Verify these specific records exist on Machine B after transfer

### Step 3: Export data from Machine A
```bash
# In Discord:
/export-progress
```

**Expected:** Bot returns success message with spreadsheet URL

**Record the URL:** `TRANSFER_SPREADSHEET_URL = _____________________`

**CRITICAL:** Save this URL - it's the ONLY thing you need to transfer data!

**Pass criteria:** Export succeeds, URL is provided

### Step 4: Backup Machine A database
```bash
# Create backup of original database before simulating Machine B
cp data/chibi.db data/chibi_machine_a.db

# Verify backup exists
ls -lh data/chibi_machine_a.db
```

**Expected:** Backup file created with same size as chibi.db

**Purpose:** Preserve original data for restoration and comparison

## Part 2: Simulate Machine B (Destination)

### Step 5: Simulate moving to Machine B by removing current database
```bash
# Move current database aside (simulates fresh machine)
mv data/chibi.db data/chibi_machine_b_old.db

# Create empty database file (triggers schema initialization on restart)
touch data/chibi.db

# Verify new database exists but is empty/tiny
ls -lh data/chibi.db
```

**Expected:**
- Old database moved to backup filename
- New chibi.db file created (0 bytes or very small)

**Pass criteria:** Fresh database file ready for schema initialization

### Step 6: Restart bot to initialize empty schema
```bash
# Stop bot (Ctrl+C in bot terminal)
# Start bot again
python main.py

# OR if using uv:
uv run python main.py
```

**Expected:** Bot logs show:
- "Initializing database schema..."
- "Database initialized successfully"
- No errors during startup
- Bot connects to Discord

**Pass criteria:** Bot starts successfully with empty database

### Step 7: Verify Machine B has empty database with schema
```bash
# Check that tables exist but are empty
echo "=== MACHINE B DATABASE STATE (BEFORE IMPORT) ==="
sqlite3 data/chibi.db "SELECT COUNT(*) FROM users;"
sqlite3 data/chibi.db "SELECT COUNT(*) FROM quiz_attempts;"
sqlite3 data/chibi.db "SELECT COUNT(*) FROM concept_mastery;"
sqlite3 data/chibi.db "SELECT COUNT(*) FROM llm_quiz_attempts;"
sqlite3 data/chibi.db "SELECT COUNT(*) FROM attendance;"
```

**Expected:** All counts are 0 (empty database)

**Pass criteria:** Database has schema (tables exist) but no data (all counts = 0)

## Part 3: Transfer Data to Machine B

### Step 8: Import data on Machine B using saved URL
```bash
# In Discord:
/import-progress <TRANSFER_SPREADSHEET_URL> mode:replace

# Click [Confirm] button when prompted
```

**Expected bot response:**
- Confirmation dialog appears (shows counts from spreadsheet)
- After confirming: ✅ Success embed
- Shows imported counts (should match Machine A counts)
- Import completes within 30 seconds

**Pass criteria:**
- Import succeeds without errors
- Counts shown in success message match Machine A baseline

### Step 9: Verify Machine B database now has data
```bash
# Check counts on Machine B after import
echo "=== MACHINE B DATABASE STATE (AFTER IMPORT) ==="
sqlite3 data/chibi.db "SELECT COUNT(*) as total_users FROM users;"
sqlite3 data/chibi.db "SELECT COUNT(*) as total_quiz_attempts FROM quiz_attempts;"
sqlite3 data/chibi.db "SELECT COUNT(*) as total_concept_mastery FROM concept_mastery;"
sqlite3 data/chibi.db "SELECT COUNT(*) as total_llm_quiz FROM llm_quiz_attempts;"
sqlite3 data/chibi.db "SELECT COUNT(*) as total_attendance FROM attendance;"
```

**Expected:**
- `USERS = MACHINE_A_USERS` (exact match)
- `QUIZ_ATTEMPTS = MACHINE_A_QUIZ_ATTEMPTS` (exact match)
- `CONCEPT_MASTERY = MACHINE_A_CONCEPT_MASTERY` (exact match)
- `LLM_QUIZ = MACHINE_A_LLM_QUIZ` (exact match)
- `ATTENDANCE = MACHINE_A_ATTENDANCE` (exact match)

**CRITICAL Pass Criteria:** ALL counts EXACTLY match Machine A

## Part 4: Verify Data Integrity

### Step 10: Verify specific records transferred correctly
```bash
# Check the same specific records queried in Step 2
echo "=== SAMPLE RECORDS FROM MACHINE B ==="
sqlite3 data/chibi.db "SELECT id, discord_id, username FROM users LIMIT 3;"
sqlite3 data/chibi.db "SELECT id, user_id, module, is_correct FROM quiz_attempts WHERE user_id=1 LIMIT 3;"
```

**Expected:**
- User 1 exists with same id, discord_id, username
- Quiz attempts for user 1 match original records
- IDs, timestamps, and all fields identical

**Pass criteria:** Specific records match Machine A exactly

### Step 11: Verify foreign key relationships intact
```bash
# Check that user → quiz_attempts relationships preserved
sqlite3 data/chibi.db "SELECT u.id, u.username, COUNT(q.id) as quiz_count
FROM users u
LEFT JOIN quiz_attempts q ON u.id=q.user_id
GROUP BY u.id
LIMIT 5;"
```

**Expected:**
- Each user shows correct quiz attempt count
- No users with NULL quiz_count (should be 0 if no attempts, not NULL)
- Counts match Machine A

**Pass criteria:** Foreign key relationships maintained

### Step 12: Check for orphaned records
```bash
# Verify no quiz attempts without corresponding user
sqlite3 data/chibi.db "SELECT COUNT(*) FROM quiz_attempts
WHERE user_id NOT IN (SELECT id FROM users);"

# Verify no concept mastery without corresponding user
sqlite3 data/chibi.db "SELECT COUNT(*) FROM concept_mastery
WHERE user_id NOT IN (SELECT id FROM users);"
```

**Expected:** Both queries return 0 (no orphaned records)

**Pass criteria:** All child records have valid parent references

## Part 5: Verify Bot Functionality

### Step 13: Test bot commands work with transferred data
```bash
# In Discord, test key commands:
/status
# Should show your user's progress (if you have data)

/modules
# Should list available modules

# Try answering a quiz question (if bot responds)
# Verify it works with imported data
```

**Expected:**
- `/status` command works and shows student data
- `/modules` command works
- Bot can create quiz questions using imported data
- No errors about missing data or database issues

**Pass criteria:** All bot functionality works normally with transferred data

### Step 14: Test creating new data on Machine B
```bash
# In Discord, take a quiz to create new data
# This verifies database is fully functional, not just readable

# After taking quiz, check database
sqlite3 data/chibi.db "SELECT COUNT(*) FROM quiz_attempts;"
```

**Expected:**
- Quiz attempt count increases by 1
- New record successfully inserted
- Database is read-write, not corrupted

**Pass criteria:** Bot can write new data to transferred database

## Part 6: Compare Machines A and B

### Step 15: Direct database comparison (optional but recommended)
```bash
# Compare Machine A backup with Machine B current state
# Export schemas
sqlite3 data/chibi_machine_a.db ".schema" > /tmp/schema_a.txt
sqlite3 data/chibi.db ".schema" > /tmp/schema_b.txt

# Compare schemas
diff /tmp/schema_a.txt /tmp/schema_b.txt
```

**Expected:** Schemas are identical (diff shows no differences)

**Pass criteria:** Database schemas match perfectly

### Step 16: Compare row counts for all tables
```bash
echo "=== FINAL COMPARISON ==="
echo "Machine A (original):"
sqlite3 data/chibi_machine_a.db "SELECT COUNT(*) FROM users;" | tr '\n' ' ' && echo "users"
sqlite3 data/chibi_machine_a.db "SELECT COUNT(*) FROM quiz_attempts;" | tr '\n' ' ' && echo "quiz_attempts"

echo "Machine B (transferred):"
sqlite3 data/chibi.db "SELECT COUNT(*) FROM users;" | tr '\n' ' ' && echo "users"
sqlite3 data/chibi.db "SELECT COUNT(*) FROM quiz_attempts;" | tr '\n' ' ' && echo "quiz_attempts"
```

**Expected:** Every table has identical counts

**Pass criteria:** Complete data transfer with no loss

## Part 7: Cleanup

### Step 17: Restore original database
```bash
# If you want to restore Machine A state:
mv data/chibi.db data/chibi_machine_b_final.db
cp data/chibi_machine_a.db data/chibi.db

# Restart bot to use restored database
# (Ctrl+C and restart)

# Verify restoration
sqlite3 data/chibi.db "SELECT COUNT(*) FROM users;"
```

**Purpose:** Return to original state for continued bot operation

**Note:** You can keep both databases for comparison:
- `data/chibi_machine_a.db` - Original Machine A data
- `data/chibi_machine_b_final.db` - Transferred Machine B data (with any new records from testing)
- `data/chibi.db` - Active database (restored to Machine A)

### Step 18: Delete test export (optional)
Delete the transfer spreadsheet from Google Drive to avoid quota issues.

## Pass/Fail Criteria

### Minimum Passing Criteria (Required)
All of the following MUST be true for MT-011 to pass:

1. **Export from Machine A (Steps 1-4):**
   - [ ] Machine A has student data to export
   - [ ] Export succeeds and returns spreadsheet URL
   - [ ] Backup created successfully

2. **Machine B Preparation (Steps 5-7):**
   - [ ] Fresh database created (simulates new machine)
   - [ ] Bot initializes empty schema successfully
   - [ ] Empty database has correct schema (tables exist, counts = 0)

3. **Data Transfer (Steps 8-9):**
   - [ ] Import succeeds using only the spreadsheet URL
   - [ ] All table counts on Machine B match Machine A exactly
   - [ ] No errors during import

4. **Data Integrity (Steps 10-12):**
   - [ ] Specific records identical between machines
   - [ ] Foreign key relationships maintained
   - [ ] No orphaned records (all foreign keys valid)

5. **Bot Functionality (Steps 13-14):**
   - [ ] `/status` and `/modules` commands work
   - [ ] Bot can read imported data
   - [ ] Bot can write new data to transferred database
   - [ ] No functionality degradation

6. **Data Completeness (Step 16):**
   - [ ] ALL tables have identical counts
   - [ ] No data loss during transfer
   - [ ] Transfer is 100% complete

### Full Verification (Optional)
If you want thorough validation:

7. **Schema Comparison (Step 15):**
   - [ ] Database schemas identical
   - [ ] All constraints preserved

8. **Real-World Scenario:**
   - [ ] Demonstrates actual server migration workflow
   - [ ] Only spreadsheet URL needed (no database file transfer)
   - [ ] Use case validated: bot can move to new server

## Common Issues & Solutions

### Issue 1: Machine A export fails
**Symptoms:** Step 3 export returns error

**Causes:**
- Google API issues (see MT-003 troubleshooting)
- No data to export (all tables empty)
- Credentials expired

**Solutions:**
1. Review MT-003 troubleshooting for export errors
2. Verify Machine A has data (Step 1 shows non-zero counts)
3. Check Google Sheets API enabled and credentials valid
4. Try creating some test data (take quizzes) before exporting

**Code reference:** `chibi/backup/sheets_exporter.py:102-139`

### Issue 2: Schema not initialized on Machine B
**Symptoms:** Step 7 shows "no such table" errors

**Causes:**
- Bot didn't restart after creating empty database
- Schema initialization failed
- Database file permissions issue

**Solutions:**
1. Ensure bot fully restarted (not just reloaded)
2. Check bot logs for "Initializing database schema"
3. Delete data/chibi.db and restart again
4. Check file permissions: `ls -l data/chibi.db`
5. Verify schema initialization code runs: `chibi/database/connection.py:_init_schema()`

**Code reference:** `chibi/database/connection.py` (_init_schema method)

### Issue 3: Import to Machine B fails
**Symptoms:** Step 8 import returns error

**Causes:**
- Spreadsheet URL incorrect or inaccessible
- Schema validation fails (different schema versions)
- Network/API issues

**Solutions:**
1. Verify spreadsheet URL copied correctly (full URL)
2. Check Machine B bot has same credentials as Machine A
3. Review MT-006 troubleshooting for import errors
4. Verify Machine B schema initialized (Step 7)
5. Check bot logs for specific error details

**Code reference:** `chibi/backup/sheets_importer.py:304-410`

### Issue 4: Count mismatch between machines
**Symptoms:** Step 9 shows different counts than Machine A

**Causes:**
- Machine A data changed between export and verification
- Partial import due to error (should not happen with transaction)
- Concurrent bot operations modifying Machine A during test

**Solutions:**
1. Export again from Machine A (data may have changed)
2. Stop Machine A bot during test to prevent concurrent modifications
3. Verify Machine A counts again: `sqlite3 data/chibi_machine_a.db "SELECT COUNT(*) FROM users;"`
4. Check for transaction rollback in import logs (should not occur)
5. If mismatch persists, critical bug (partial import despite transaction)

**Code reference:** `chibi/backup/sheets_importer.py:342-374` (transaction handling)

### Issue 5: Foreign keys broken after transfer
**Symptoms:** Step 11-12 show orphaned records or NULL relationships

**Causes:**
- Foreign key constraints not enforced during import (bug)
- Import order incorrect (child tables before parent)
- Transaction rollback didn't occur on foreign key violation

**Solutions:**
1. Check foreign key enforcement: `sqlite3 data/chibi.db "PRAGMA foreign_keys;"`
2. Should return 1 (enabled) - if 0, critical bug
3. Verify import order: Users → QuizAttempts → others (line 350-364)
4. Check for foreign key errors in logs
5. If broken, report as critical bug

**Code reference:** `chibi/backup/sheets_importer.py:344` (PRAGMA foreign_keys = ON)
**Code reference:** `chibi/backup/sheets_importer.py:350-364` (import order)

### Issue 6: Bot commands don't work on Machine B
**Symptoms:** Step 13 commands fail or return errors

**Causes:**
- Bot caching old database state
- Database corruption during transfer
- Bot not fully restarted after import
- Missing data expected by bot logic

**Solutions:**
1. Restart bot completely (full shutdown and restart)
2. Check database integrity: `sqlite3 data/chibi.db "PRAGMA integrity_check;"`
3. Verify specific tables have data: `/status` needs users table
4. Check bot logs for errors about missing data
5. Test with user that has data (may need to be logged in Discord)

**Code reference:** Bot services query database directly, should work with any valid data

### Issue 7: Cannot write new data on Machine B
**Symptoms:** Step 14 quiz attempt doesn't create new record

**Causes:**
- Database file read-only permissions
- SQLite database locked
- Foreign key constraint (user doesn't exist)

**Solutions:**
1. Check file permissions: `ls -l data/chibi.db`
2. Ensure bot has write access: `chmod 644 data/chibi.db`
3. Verify no other process has database locked
4. Check if your Discord user exists in transferred data
5. Try with user known to be in database

**Code reference:** QuizService, database write operations

### Issue 8: Schemas don't match (Step 15)
**Symptoms:** diff shows differences in schemas

**Causes:**
- Machine A and Machine B running different bot versions
- Schema migrations applied on one machine but not other
- Manual schema changes

**Solutions:**
1. Ensure both machines run same bot version (same git commit)
2. Check for pending migrations: review database connection.py
3. Schema differences may prevent proper import (validation should catch)
4. Update both machines to same version before testing
5. If unavoidable: This test may not be valid, skip

**Best practice:** Always use same bot version for export/import

## Implementation Details

### Transfer Workflow
```
Machine A (Source):
  ↓
1. Export data to Google Sheets
   chibi/backup/sheets_exporter.py:export_to_sheets()
  ↓
2. Spreadsheet created in Google Drive
   Returns URL
  ↓
[TRANSFER MEDIUM: JUST THE URL - No database files moved]
  ↓
Machine B (Destination):
  ↓
3. Fresh database with empty schema
   chibi/database/connection.py:_init_schema()
  ↓
4. Import from spreadsheet using URL
   chibi/backup/sheets_importer.py:import_from_sheets()
  ↓
5. Data written to Machine B database
   All tables populated via transaction
  ↓
6. Bot functions with imported data
   Normal operation resumes
```

### Code Locations
- **Schema initialization:** `chibi/database/connection.py:_init_schema()`
- **Export process:** `chibi/backup/sheets_exporter.py:102-139`
- **Import process:** `chibi/backup/sheets_importer.py:304-410`
- **Transaction handling:** `chibi/backup/sheets_importer.py:342-374`
- **Foreign key order:** `chibi/backup/sheets_importer.py:350-364`

### Why Cross-Machine Transfer Matters
1. **Server Migration:** Move bot to new hosting (VPS, cloud provider, etc.)
2. **Disaster Recovery:** Restore after server failure or data loss
3. **Development:** Copy production data to test environment safely
4. **Scaling:** Replicate bot across multiple servers (with caution)
5. **Portability:** Cloud-based transfer (no direct file access needed)

### Transfer Advantages Over Direct Database Copy
- **Cloud-based:** No need for SSH or file transfer tools
- **Version-agnostic:** Spreadsheet format more stable than SQLite binary
- **Human-readable:** Can inspect/edit data in Google Sheets if needed
- **Platform-independent:** Works across different OS (Windows → Linux, etc.)
- **Audit trail:** Spreadsheet preserved as backup snapshot

## Test Completion Checklist

- [ ] All 18 steps completed
- [ ] All 6 minimum passing criteria met
- [ ] Machine A data exported successfully
- [ ] Machine B initialized with empty schema
- [ ] Data transferred using only spreadsheet URL
- [ ] All counts match exactly between machines
- [ ] Foreign keys and relationships intact
- [ ] Bot functionality verified on Machine B
- [ ] New data can be created on Machine B
- [ ] Original database restored (if desired)

## Notes
- Estimated test duration: 30-45 minutes
- Simulates real-world server migration scenario
- Only spreadsheet URL needed for transfer (cloud-based)
- Validates complete backup/restore cycle
- Critical for production bot deployments

## Test Result

**Date:** _____________
**Tester:** _____________
**Result:** ☐ PASS  ☐ FAIL
**Notes:**

---

**Test Guide Version:** 1.0
**Associated Story:** MT-011
**Dependencies:** MT-003 (export) and MT-006 (import to clean database)
**Implementation Reference:** Full backup/restore workflow using export and import commands
