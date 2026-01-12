# Manual E2E Test: MT-007 - Import to Existing Database (Merge Mode)

## Test Objective

Verify that the import functionality correctly merges data from a Google Sheets export into an existing database without losing existing records. Merge mode should update existing records (by ID match) and insert new records, while preserving all data integrity.

## Background

The backup system supports two import modes:
- **Replace mode**: Deletes all existing data, then inserts from spreadsheet (covered in MT-006)
- **Merge mode**: Uses `INSERT OR REPLACE` to update existing records by ID and insert new records

This test validates merge mode behavior, ensuring it correctly:
- Preserves existing data not present in the import
- Updates existing records when IDs match
- Inserts new records from the spreadsheet
- Maintains foreign key relationships throughout

## Prerequisites

Before starting this test, ensure:

- [ ] MT-006 (Import to clean database) has passed
- [ ] You have an exported spreadsheet URL from MT-003
- [ ] Database has existing data (can use data restored from MT-006)
- [ ] Bot is running with admin permissions
- [ ] You have Discord access to run slash commands
- [ ] You can access sqlite3 command line tool

## Implementation Reference

This test validates the merge mode implementation in:
- `chibi/backup/sheets_importer.py:324-357` - Merge mode implementation using INSERT OR REPLACE
- `chibi/cogs/backup_cog.py:152-235` - /import-progress command with mode parameter
- `chibi/backup/backup_service.py:105-136` - Service orchestration for imports

## Test Procedure

### Part 1: Prepare Initial State (Steps 1-4)

#### Step 1: Ensure database has existing data

First, verify your database has data (from MT-006 import or other source):

```bash
sqlite3 data/chibi.db << 'EOF'
SELECT COUNT(*) as user_count FROM users;
SELECT COUNT(*) as quiz_count FROM quiz_attempts;
SELECT COUNT(*) as mastery_count FROM concept_mastery;
EOF
```

**Expected output:** At least 1 user with some quiz attempts.

If database is empty, restore data first:
```bash
# From MT-006 backup if available
cp data/chibi.db.backup data/chibi.db
# OR run import from previous export using replace mode
```

#### Step 2: Record baseline counts

Record current database state for later comparison:

```bash
sqlite3 data/chibi.db << 'EOF'
.mode column
.headers on
SELECT
  (SELECT COUNT(*) FROM users) as users,
  (SELECT COUNT(*) FROM quiz_attempts) as quiz_attempts,
  (SELECT COUNT(*) FROM concept_mastery) as concept_mastery,
  (SELECT COUNT(*) FROM llm_quiz_attempts) as llm_quiz_attempts,
  (SELECT COUNT(*) FROM attendance) as attendance;
EOF
```

**Record these numbers** (call them BASELINE_USERS, BASELINE_QUIZ, etc.)

#### Step 3: Add a new unique user via Discord

To test merge behavior, add a new user that doesn't exist in your export:

1. In Discord, use a different account or ask someone else to run `/quiz`
2. Answer the quiz question (correctness doesn't matter)
3. This creates a new user record that should survive the merge

**Alternative (if only one Discord account):**
```bash
# Manually insert a test user
sqlite3 data/chibi.db << 'EOF'
INSERT INTO users (discord_id, username, created_at)
VALUES (999999999999999999, 'merge_test_user', datetime('now'));
EOF
```

#### Step 4: Record new baseline after adding user

```bash
sqlite3 data/chibi.db << 'EOF'
.mode column
.headers on
SELECT
  (SELECT COUNT(*) FROM users) as users,
  (SELECT COUNT(*) FROM quiz_attempts) as quiz_attempts,
  (SELECT COUNT(*) FROM concept_mastery) as concept_mastery;
SELECT discord_id, username FROM users ORDER BY created_at DESC LIMIT 5;
EOF
```

**Record these numbers** (call them PREMERGE_USERS, PREMERGE_QUIZ, etc.)

**PREMERGE_USERS should equal BASELINE_USERS + 1** (the new user you added)

### Part 2: Execute Merge Import (Steps 5-8)

#### Step 5: Identify export spreadsheet URL

Get the spreadsheet URL from a previous export (MT-003). It should look like:
```
https://docs.google.com/spreadsheets/d/1abc...xyz/edit
```

If you don't have a URL, run `/export-progress` first and use that URL.

#### Step 6: Run import command with merge mode

In Discord, run:
```
/import-progress <spreadsheet_url> mode:merge
```

Replace `<spreadsheet_url>` with your actual URL.

**Expected:** Bot shows a confirmation dialog with current database counts.

#### Step 7: Confirm merge operation

Click the **[Confirm]** button in Discord.

**Expected:**
- Bot responds: "Starting import with mode: merge..."
- After 10-30 seconds: "Import completed successfully"
- Shows counts: X users imported, Y quiz attempts imported, etc.

#### Step 8: Check bot logs for merge details

Look for these log messages:
```
INFO - Import mode: merge
INFO - Importing users table with mode: merge (INSERT OR REPLACE)
INFO - Importing quiz_attempts table with mode: merge
INFO - Import completed successfully
```

**Pass criteria:** No errors, all tables imported, mode is "merge".

### Part 3: Verify Merge Results (Steps 9-14)

#### Step 9: Query final counts

```bash
sqlite3 data/chibi.db << 'EOF'
.mode column
.headers on
SELECT
  (SELECT COUNT(*) FROM users) as users,
  (SELECT COUNT(*) FROM quiz_attempts) as quiz_attempts,
  (SELECT COUNT(*) FROM concept_mastery) as concept_mastery,
  (SELECT COUNT(*) FROM llm_quiz_attempts) as llm_quiz_attempts,
  (SELECT COUNT(*) FROM attendance) as attendance;
EOF
```

**Record these as POSTMERGE counts.**

#### Step 10: Verify the new user still exists

Check that the user you added in Step 3 still exists:

```bash
sqlite3 data/chibi.db << 'EOF'
.mode column
.headers on
SELECT id, discord_id, username, created_at
FROM users
WHERE username = 'merge_test_user' OR discord_id = 999999999999999999;
EOF
```

**Expected:** The merge_test_user (or the user you added) should still be in the database.

**Critical check:** This user should NOT have been deleted by the merge.

#### Step 11: Check for duplicate records

Verify no duplicate users were created:

```bash
sqlite3 data/chibi.db << 'EOF'
.mode column
.headers on
SELECT discord_id, COUNT(*) as count
FROM users
GROUP BY discord_id
HAVING COUNT(*) > 1;
EOF
```

**Expected:** No results (empty output). If any rows appear, duplicates were created (FAIL).

#### Step 12: Verify foreign key relationships

Check that user IDs still match quiz attempts:

```bash
sqlite3 data/chibi.db << 'EOF'
.mode column
.headers on
SELECT u.id, u.username, COUNT(q.id) as quiz_count
FROM users u
LEFT JOIN quiz_attempts q ON u.id = q.user_id
GROUP BY u.id
ORDER BY u.id
LIMIT 10;
EOF
```

**Expected:** Each user has a count >= 0. No NULL usernames.

Check for orphaned records:
```bash
sqlite3 data/chibi.db << 'EOF'
SELECT COUNT(*) as orphaned_quiz_attempts
FROM quiz_attempts
WHERE user_id NOT IN (SELECT id FROM users);
EOF
```

**Expected:** 0 (no orphaned records)

#### Step 13: Test updated record behavior

If your export had a user with ID=1, check if that user's data was updated (not duplicated):

```bash
sqlite3 data/chibi.db << 'EOF'
.mode column
.headers on
SELECT id, discord_id, username, created_at
FROM users
WHERE id = 1;
EOF
```

**Expected:** Exactly 1 row with ID=1 (not 2 rows). Data should match the export.

#### Step 14: Verify count logic

Calculate expected counts:

**Expected formula:**
- POSTMERGE_USERS should be >= PREMERGE_USERS (includes new user + any from export not already present)
- If export had users already in DB: POSTMERGE_USERS = PREMERGE_USERS (no duplicates)
- If export had NEW users: POSTMERGE_USERS = PREMERGE_USERS + number_of_new_users_from_export

**Example scenario:**
- BASELINE_USERS = 3 (from original export)
- PREMERGE_USERS = 4 (after adding merge_test_user)
- Export has 3 users (the original ones)
- POSTMERGE_USERS = 4 (3 updated from export + 1 merge_test_user)

### Part 4: Verify Bot Functionality (Steps 15-16)

#### Step 15: Test bot commands with merged data

In Discord, run:
```
/status
```

**Expected:** Bot shows data for all users (including merge_test_user if using Discord account).

#### Step 16: Test quiz functionality

Run:
```
/quiz
```

**Expected:** Bot generates quiz, stores attempts in database. New attempts are added, not replacing existing ones.

## Pass/Fail Criteria

### Minimum Passing Criteria (Steps 7-8, 9-12)

The test passes if:
1. ✓ Merge import completes without errors (Step 7)
2. ✓ Bot logs show "mode: merge" and "INSERT OR REPLACE" (Step 8)
3. ✓ Final user count >= pre-merge user count (Step 9)
4. ✓ New user added in Step 3 still exists (Step 10)
5. ✓ No duplicate discord_ids in users table (Step 11)
6. ✓ No orphaned quiz_attempts (Step 12)
7. ✓ Foreign key relationships intact (Step 12)

### Full Verification (Steps 13-16)

For comprehensive validation, also verify:
8. ✓ Existing records updated (not duplicated) by ID match (Step 13)
9. ✓ Count logic correct based on export contents (Step 14)
10. ✓ Bot commands work correctly with merged data (Steps 15-16)

## Common Issues and Troubleshooting

### Issue 1: Merge creates duplicate users

**Symptoms:** Step 11 shows duplicate discord_ids

**Causes:**
- Bug in merge logic (should use ID as primary key, not discord_id)
- INSERT OR REPLACE not working correctly

**Solutions:**
1. Check database schema: `sqlite3 data/chibi.db ".schema users"`
2. Verify ID is PRIMARY KEY
3. Check implementation: chibi/backup/sheets_importer.py:336-348
4. Report as bug with database counts and query results

### Issue 2: New user (merge_test_user) was deleted

**Symptoms:** Step 10 returns no results

**Causes:**
- Merge mode is actually running in replace mode (DELETE + INSERT)
- Mode parameter not passed correctly

**Solutions:**
1. Check bot logs for "Import mode: merge" (not "replace")
2. Check command was `/import-progress ... mode:merge` (not mode:replace)
3. Verify implementation: chibi/backup/sheets_importer.py:324-357
4. Report as bug if logs show "merge" but behavior is "replace"

### Issue 3: Count logic doesn't match expectations

**Symptoms:** POSTMERGE_USERS != expected value

**Causes:**
- Export spreadsheet has different data than expected
- Merge logic updating when should be inserting (or vice versa)
- Primary key conflicts

**Solutions:**
1. Check export Metadata sheet for actual user count
2. Compare export user IDs to database user IDs: `sqlite3 data/chibi.db "SELECT id FROM users ORDER BY id;"`
3. Calculate expected: POSTMERGE = PREMERGE + (new users from export)
4. If mismatch, check logs for "Inserted X rows" vs "Updated Y rows"

### Issue 4: Foreign key relationships broken

**Symptoms:** Step 12 shows orphaned quiz_attempts

**Causes:**
- User IDs changed during merge (shouldn't happen)
- Quiz attempts imported before users (order issue)
- Foreign key constraints not enforced

**Solutions:**
1. Check import order: Users should be imported BEFORE quiz_attempts
2. Verify implementation: chibi/backup/sheets_importer.py:305-307 (import order)
3. Check foreign key enforcement: `sqlite3 data/chibi.db "PRAGMA foreign_keys;"`
4. Report as bug if foreign_keys=1 but orphans exist

### Issue 5: Bot commands show wrong data after merge

**Symptoms:** Step 15-16 show incorrect user data

**Causes:**
- Bot caching old data (not reloading after import)
- Database connection stale

**Solutions:**
1. Restart bot: `Ctrl+C` then `python main.py`
2. Try commands again after restart
3. If still wrong, check database directly: `sqlite3 data/chibi.db "SELECT * FROM users;"`
4. Report as caching bug if DB correct but bot shows wrong data

### Issue 6: Updated records show old timestamps

**Symptoms:** Step 13 shows created_at from original, not from export

**Causes:**
- INSERT OR REPLACE correctly updating all columns
- This is EXPECTED behavior (export preserves timestamps)

**Solutions:**
- This is NOT a bug
- Merge mode preserves all data from export, including timestamps
- Original created_at from export should be restored

### Issue 7: Merge mode runs very slowly

**Symptoms:** Step 7 takes > 60 seconds for small dataset

**Causes:**
- INSERT OR REPLACE slower than bulk INSERT
- Database indexes being rebuilt for each row
- Foreign key checks on every row

**Solutions:**
1. This is expected for merge mode (slower than replace)
2. Check dataset size: Large datasets (>1000 rows) will be slower
3. Consider replace mode for large imports if data loss acceptable
4. Report as performance issue if > 5 seconds per 100 rows

## Test Completion

After completing this test:
1. Document results (PASS/FAIL) with any issues encountered
2. If FAIL, note which steps failed and error messages
3. Database can remain in merged state (or restore backup if needed)
4. Move to next test (MT-008) if PASS

## Notes

- Merge mode uses SQLite `INSERT OR REPLACE` which updates by PRIMARY KEY match
- This is the recommended mode for incremental backups or syncing between servers
- Replace mode (MT-006) is faster but destructive
- Merge mode preserves local-only data (like merge_test_user in this test)
