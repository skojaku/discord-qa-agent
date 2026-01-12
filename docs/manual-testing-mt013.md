# Manual Testing Guide: MT-013 - Referential Integrity Verification

## Test ID: MT-013
**Title:** Referential integrity verification through export/import
**Priority:** 4 (Data Integrity)
**Category:** Integrity
**Prerequisites:** MT-006 passed (import with replace mode working)

---

## Objective

Verify that foreign key relationships between database tables are correctly preserved through a complete export/import cycle, including parent-child relationships (users → quiz_attempts, users → concept_mastery, users → llm_quiz_attempts, users → attendance). This test validates that no orphaned records are created and that referential integrity constraints remain enforced after import.

---

## Background

The Chibi bot database has a relational structure with the `users` table as the parent and four child tables that reference it via foreign keys:

**Database Relationships:**
```
users (1) ──< (many) quiz_attempts       (FK: user_id → users.id)
users (1) ──< (many) concept_mastery      (FK: user_id → users.id)
users (1) ──< (many) llm_quiz_attempts    (FK: user_id → users.id)
users (1) ──< (many) attendance           (FK: user_id → users.id)
```

**Foreign Key Enforcement:**
- SQLite requires `PRAGMA foreign_keys = ON` to enforce constraints
- Import process must enable foreign keys BEFORE transaction
- Parent records (users) must be imported before child records
- Foreign key violations should cause import to fail with ROLLBACK

**Implementation details:**
- Import order: `chibi/backup/sheets_importer.py:350-364` (Users first, then child tables)
- Foreign key enforcement: `sheets_importer.py:344` (`PRAGMA foreign_keys = ON`)
- Transaction safety: `sheets_importer.py:347-374` (BEGIN, COMMIT, ROLLBACK)
- Schema definition: `chibi/database/connection.py:66-191` (FOREIGN KEY constraints)

**Critical validation points:**
- All user_id values in child tables must reference existing users.id
- No orphaned records (child without parent)
- Foreign key constraints enforced after import
- DELETE cascade behavior works (cannot delete parent with children)

---

## Prerequisites Checklist

Before starting:

- [ ] MT-006 passed (import with replace mode working)
- [ ] Database has users with related quiz attempts and concept mastery records
- [ ] Bot is running (`uv run python main.py`)
- [ ] You have admin permissions in the test Discord server
- [ ] You have access to sqlite3 command-line tool

---

## Part 1: Record Baseline Relationships

### Step 1: Query Current Foreign Key Relationships

Record user-to-quiz-attempt relationships:

```bash
cd /Users/skojaku-admin/Documents/projects/applied-soft-comp/tutor/discord-qa-agent

sqlite3 data/chibi.db <<EOF
.mode column
.headers on
SELECT u.id, u.username, COUNT(q.id) as quiz_count
FROM users u
LEFT JOIN quiz_attempts q ON u.id = q.user_id
GROUP BY u.id
ORDER BY u.id;
EOF
```

**Expected output:**
```
id  username        quiz_count
--  -------------   ----------
1   student_alice   5
2   student_bob     3
3   student_carol   0
```

**Write down:** User IDs and their quiz counts for comparison after import.

---

### Step 2: Query Concept Mastery Relationships

Record user-to-mastery relationships:

```bash
sqlite3 data/chibi.db <<EOF
.mode column
SELECT u.id, u.username, COUNT(c.id) as mastery_count
FROM users u
LEFT JOIN concept_mastery c ON u.id = c.user_id
GROUP BY u.id
ORDER BY u.id;
EOF
```

**Expected:** Each user with their count of concept mastery records.

**Write down:** User IDs and mastery counts.

---

### Step 3: Query LLM Quiz Relationships

Record user-to-LLM-quiz relationships:

```bash
sqlite3 data/chibi.db <<EOF
.mode column
SELECT u.id, u.username, COUNT(l.id) as llm_quiz_count
FROM users u
LEFT JOIN llm_quiz_attempts l ON u.id = l.user_id
GROUP BY u.id
ORDER BY u.id;
EOF
```

**Expected:** Each user with their LLM quiz attempt counts.

**Write down:** User IDs and LLM quiz counts.

---

### Step 4: Query Attendance Relationships

Record user-to-attendance relationships:

```bash
sqlite3 data/chibi.db <<EOF
.mode column
SELECT u.id, u.username, COUNT(a.id) as attendance_count
FROM users u
LEFT JOIN attendance a ON u.id = a.user_id
GROUP BY u.id
ORDER BY u.id;
EOF
```

**Expected:** Each user with their attendance record counts.

**Write down:** User IDs and attendance counts.

---

### Step 5: Export Complete Relationship Reference

Create a comprehensive baseline file:

```bash
sqlite3 data/chibi.db <<EOF > baseline-relationships-mt013.txt
.mode column
.headers on

-- Users with all related counts
SELECT
  u.id,
  u.username,
  (SELECT COUNT(*) FROM quiz_attempts WHERE user_id = u.id) as quiz_count,
  (SELECT COUNT(*) FROM concept_mastery WHERE user_id = u.id) as mastery_count,
  (SELECT COUNT(*) FROM llm_quiz_attempts WHERE user_id = u.id) as llm_quiz_count,
  (SELECT COUNT(*) FROM attendance WHERE user_id = u.id) as attendance_count
FROM users u
ORDER BY u.id;

-- Sample specific quiz attempts with user_id
SELECT 'QUIZ_ATTEMPTS SAMPLE' as section;
SELECT id, user_id, module_id, is_correct FROM quiz_attempts ORDER BY id LIMIT 10;

-- Sample specific concept mastery with user_id
SELECT 'CONCEPT_MASTERY SAMPLE' as section;
SELECT id, user_id, concept_id, total_attempts FROM concept_mastery ORDER BY id LIMIT 10;
EOF
```

**Expected:** File `baseline-relationships-mt013.txt` created with all relationship data.

**Keep this file** - we'll compare after import.

---

## Part 2: Perform Export

### Step 6: Export Current Database

Export the database to Google Sheets:

```bash
# In Discord, as admin:
/export-progress
```

**Expected response:**
```
✅ Export Complete

Exported 5 tables to Google Sheets:
• Users: N rows
• QuizAttempts: N rows
• ConceptMastery: N rows
• LLMQuizAttempts: N rows
• Attendance: N rows

📊 View spreadsheet: [link]
```

**Copy the spreadsheet URL** - you'll need it for import.

---

## Part 3: Clear Database and Import

### Step 7: Backup and Clear Database

Backup current database:

```bash
cp data/chibi.db data/chibi.db.backup-mt013
```

Delete database to simulate fresh import:

```bash
rm data/chibi.db
```

**Verify deletion:**
```bash
ls data/chibi.db
# Should show: No such file or directory
```

---

### Step 8: Restart Bot to Initialize Empty Schema

Stop the bot (Ctrl+C) and restart:

```bash
uv run python main.py
```

**Expected in logs:**
```
INFO - Database initialized at data/chibi.db
INFO - Running migrations...
INFO - BackupService initialized
```

**Verify empty database:**
```bash
sqlite3 data/chibi.db "SELECT COUNT(*) FROM users;"
# Should output: 0
```

---

### Step 9: Import from Spreadsheet

In Discord, run import with the URL from Step 6:

```bash
# In Discord, as admin:
/import-progress <spreadsheet_url> mode:replace
```

**Click [Confirm]** in the confirmation dialog.

**Expected response:**
```
✅ Import Complete (replace mode)

Imported data from spreadsheet:
• Users: N rows
• QuizAttempts: N rows
• ConceptMastery: N rows
• LLMQuizAttempts: N rows
• Attendance: N rows
```

**Verify:** Response shows same counts as export (Step 6).

---

## Part 4: Verify Foreign Key Relationships

### Step 10: Verify No Orphaned Quiz Attempts

Check that all quiz attempts reference existing users:

```bash
sqlite3 data/chibi.db "SELECT COUNT(*) FROM quiz_attempts WHERE user_id NOT IN (SELECT id FROM users);"
```

**Expected output:** `0` (zero orphaned records)

**CRITICAL:** Any non-zero value means orphaned records exist (test FAILS).

**Verification:**
```bash
# List orphaned records if any exist
sqlite3 data/chibi.db <<EOF
SELECT id, user_id, module_id
FROM quiz_attempts
WHERE user_id NOT IN (SELECT id FROM users)
LIMIT 5;
EOF
```

**Expected:** No rows returned (empty result set).

---

### Step 11: Verify No Orphaned Concept Mastery

Check concept mastery records:

```bash
sqlite3 data/chibi.db "SELECT COUNT(*) FROM concept_mastery WHERE user_id NOT IN (SELECT id FROM users);"
```

**Expected output:** `0` (zero orphaned records)

---

### Step 12: Verify No Orphaned LLM Quiz Attempts

Check LLM quiz attempts:

```bash
sqlite3 data/chibi.db "SELECT COUNT(*) FROM llm_quiz_attempts WHERE user_id NOT IN (SELECT id FROM users);"
```

**Expected output:** `0` (zero orphaned records)

---

### Step 13: Verify No Orphaned Attendance Records

Check attendance records:

```bash
sqlite3 data/chibi.db "SELECT COUNT(*) FROM attendance WHERE user_id NOT IN (SELECT id FROM users);"
```

**Expected output:** `0` (zero orphaned records)

**Pass criteria:** All four child tables have zero orphaned records.

---

## Part 5: Verify Relationship Counts Match

### Step 14: Verify Quiz Attempt Relationships

Query user-to-quiz-attempt relationships after import:

```bash
sqlite3 data/chibi.db <<EOF
.mode column
SELECT u.id, u.username, COUNT(q.id) as quiz_count
FROM users u
LEFT JOIN quiz_attempts q ON u.id = q.user_id
GROUP BY u.id
ORDER BY u.id;
EOF
```

**Compare to baseline (Step 1):** Counts should match exactly for each user.

**Expected:** Identical output to Step 1 query.

---

### Step 15: Verify All Relationship Counts

Re-export comprehensive relationship reference after import:

```bash
sqlite3 data/chibi.db <<EOF > postimport-relationships-mt013.txt
.mode column
.headers on

-- Users with all related counts
SELECT
  u.id,
  u.username,
  (SELECT COUNT(*) FROM quiz_attempts WHERE user_id = u.id) as quiz_count,
  (SELECT COUNT(*) FROM concept_mastery WHERE user_id = u.id) as mastery_count,
  (SELECT COUNT(*) FROM llm_quiz_attempts WHERE user_id = u.id) as llm_quiz_count,
  (SELECT COUNT(*) FROM attendance WHERE user_id = u.id) as attendance_count
FROM users u
ORDER BY u.id;

-- Sample specific quiz attempts with user_id
SELECT 'QUIZ_ATTEMPTS SAMPLE' as section;
SELECT id, user_id, module_id, is_correct FROM quiz_attempts ORDER BY id LIMIT 10;

-- Sample specific concept mastery with user_id
SELECT 'CONCEPT_MASTERY SAMPLE' as section;
SELECT id, user_id, concept_id, total_attempts FROM concept_mastery ORDER BY id LIMIT 10;
EOF
```

**Compare files:**
```bash
diff baseline-relationships-mt013.txt postimport-relationships-mt013.txt
```

**Expected:** Files are identical (diff shows no differences).

**Pass criteria:** Zero differences in relationship counts and structure.

---

## Part 6: Verify Foreign Key Constraints Enforced

### Step 16: Test Foreign Key Constraint (DELETE)

Verify that foreign key constraints are actively enforced:

```bash
# Attempt to delete a user who has quiz attempts (should FAIL)
sqlite3 data/chibi.db "DELETE FROM users WHERE id = 1;" 2>&1
```

**Expected output:**
```
Error: FOREIGN KEY constraint failed
```

**CRITICAL:** If DELETE succeeds (no error), foreign keys are NOT enforced (test FAILS).

---

### Step 17: Verify Constraint Enforcement with Query

Check that foreign key pragma is enabled:

```bash
sqlite3 data/chibi.db "PRAGMA foreign_keys;"
```

**Expected output:** `1` (foreign keys enabled)

**If output is 0:** Foreign keys not enabled (constraint enforcement missing).

**Note:** Pragma state is per-connection, not persisted in database. The test in Step 16 is more definitive.

---

### Step 18: Test Foreign Key Check Pragma

Run SQLite's built-in foreign key integrity check:

```bash
sqlite3 data/chibi.db "PRAGMA foreign_key_check;"
```

**Expected output:** Empty (no rows) - all foreign keys valid

**If any rows returned:**
```
table          rowid  parent  fkid
-------------  -----  ------  ----
quiz_attempts  123    users   0
```

This indicates a foreign key violation (orphaned record).

**Pass criteria:** No rows returned from foreign_key_check.

---

## Part 7: Verify Specific Relationship Integrity

### Step 19: Sample Specific User Relationships

Verify a specific user's complete relationship tree:

```bash
# Pick user with ID 1 (or any user from baseline)
sqlite3 data/chibi.db <<EOF
.mode column

-- User details
SELECT 'USER 1 DETAILS' as section;
SELECT id, discord_id, username FROM users WHERE id = 1;

-- Quiz attempts for User 1
SELECT 'USER 1 QUIZ ATTEMPTS' as section;
SELECT id, module_id, concept_id, is_correct FROM quiz_attempts WHERE user_id = 1 LIMIT 5;

-- Concept mastery for User 1
SELECT 'USER 1 CONCEPT MASTERY' as section;
SELECT id, concept_id, total_attempts, mastery_level FROM concept_mastery WHERE user_id = 1 LIMIT 5;

-- LLM quiz attempts for User 1
SELECT 'USER 1 LLM QUIZ' as section;
SELECT id, module_id, student_wins FROM llm_quiz_attempts WHERE user_id = 1 LIMIT 5;

-- Attendance for User 1
SELECT 'USER 1 ATTENDANCE' as section;
SELECT id, session_id, status FROM attendance WHERE user_id = 1 LIMIT 5;
EOF
```

**Expected:** All queries return records (User 1 exists with related data).

**Verify:** user_id = 1 in all child tables correctly references users.id = 1.

---

## Part 8: Cleanup

### Step 20: Verify Test Completion

Check that all foreign key relationships are preserved:

**Checklist:**
- [ ] Zero orphaned records in quiz_attempts (Step 10)
- [ ] Zero orphaned records in concept_mastery (Step 11)
- [ ] Zero orphaned records in llm_quiz_attempts (Step 12)
- [ ] Zero orphaned records in attendance (Step 13)
- [ ] Relationship counts match baseline exactly (Step 15)
- [ ] Foreign key constraints enforced (DELETE fails, Step 16)
- [ ] PRAGMA foreign_key_check shows no violations (Step 18)
- [ ] Specific user relationships intact (Step 19)

---

### Step 21: Cleanup Files and Restore (Optional)

You can keep the imported data or restore the original:

**Option A: Keep imported data (data matches original)**
```bash
# Remove backup and test files
rm data/chibi.db.backup-mt013
rm baseline-relationships-mt013.txt postimport-relationships-mt013.txt
```

**Option B: Restore original database**
```bash
# Restore backup, keep test files for review
cp data/chibi.db.backup-mt013 data/chibi.db
```

---

## Pass/Fail Criteria

### Minimum Passing Criteria

The test PASSES if ALL of the following are true:

1. **No orphaned records (Steps 10-13):**
   - [ ] Zero orphaned quiz_attempts (user_id references non-existent user)
   - [ ] Zero orphaned concept_mastery
   - [ ] Zero orphaned llm_quiz_attempts
   - [ ] Zero orphaned attendance records

2. **Relationship counts preserved (Steps 14-15):**
   - [ ] User-to-quiz-attempt counts match baseline exactly
   - [ ] All relationship counts in baseline file match post-import file
   - [ ] diff shows zero differences

3. **Foreign key constraints enforced (Steps 16-18):**
   - [ ] DELETE user with children fails with "FOREIGN KEY constraint failed"
   - [ ] PRAGMA foreign_key_check returns no violations
   - [ ] Constraints actively preventing invalid operations

4. **Specific relationships verified (Step 19):**
   - [ ] Sample user has all related records present
   - [ ] All user_id values correctly reference parent users.id

### Test FAILS if:

- ❌ Any child table has orphaned records (user_id references non-existent user)
- ❌ Relationship counts differ from baseline (data loss or corruption)
- ❌ diff shows any differences (relationship structure changed)
- ❌ DELETE user with children succeeds (constraints not enforced)
- ❌ PRAGMA foreign_key_check returns violations
- ❌ Sample user relationships broken or incomplete

---

## Common Issues and Troubleshooting

### Issue 1: Orphaned records found in child tables

**Symptoms:**
```bash
sqlite3 data/chibi.db "SELECT COUNT(*) FROM quiz_attempts WHERE user_id NOT IN (SELECT id FROM users);"
# Shows: 5 (WRONG - should be 0)
```

**Cause:** Import order violated (child tables imported before parent) or foreign keys not enforced during import.

**Solution:**
- Check import order: `sheets_importer.py:350-364` (Users must be first)
- Verify PRAGMA foreign_keys = ON before import: `sheets_importer.py:344`
- Check logs for import errors that were silently ignored
- Critical bug if orphaned records present after successful import

**Code reference:** `sheets_importer.py:350-364` - import order (Users, QuizAttempts, ConceptMastery, LLMQuizAttempts, Attendance)

---

### Issue 2: Relationship counts don't match baseline

**Symptoms:**
```bash
diff baseline-relationships-mt013.txt postimport-relationships-mt013.txt
# Shows differences in counts
```

**Cause:** Partial import, data loss during export/import, or concurrent modifications to database.

**Solution:**
- Verify export and import counts match (same number of rows exported and imported)
- Check bot logs for partial import or rollback messages
- Ensure database not modified between export and baseline recording
- Re-run test from Step 1 to ensure clean baseline

**Critical:** Any count mismatch indicates data integrity failure.

---

### Issue 3: DELETE user succeeds when should fail

**Symptoms:**
```bash
sqlite3 data/chibi.db "DELETE FROM users WHERE id = 1;"
# Succeeds with no error (WRONG - should fail with FOREIGN KEY constraint failed)
```

**Cause:** Foreign key constraints not enabled in SQLite connection.

**Solution:**
- Check schema definition: `connection.py:66-191` - FOREIGN KEY clauses present
- Verify PRAGMA foreign_keys = ON is set: `sqlite3 data/chibi.db "PRAGMA foreign_keys;"`
- SQLite disables foreign keys by default - must be enabled per connection
- Importer should enable: `sheets_importer.py:344`

**Testing note:** The pragma is per-connection, so test with direct sqlite3 command.

**Restore user if deleted:**
```bash
# Restore from backup
cp data/chibi.db.backup-mt013 data/chibi.db
```

---

### Issue 4: PRAGMA foreign_key_check shows violations

**Symptoms:**
```bash
sqlite3 data/chibi.db "PRAGMA foreign_key_check;"
# Returns rows showing violations (WRONG - should be empty)
```

**Cause:** Database corrupted during import, orphaned records exist, or import order violated.

**Solution:**
- Identify specific violations from output (table, rowid, parent)
- Query specific orphaned records: `SELECT * FROM [table] WHERE rowid = [rowid];`
- Check if import completed successfully (no rollback)
- Critical bug if violations exist after successful import

**Prevention:** Import order must be parent-first (Users before child tables).

---

### Issue 5: Baseline and post-import files show differences

**Symptoms:**
```bash
diff baseline-relationships-mt013.txt postimport-relationships-mt013.txt
# Shows differences in user_id or counts
```

**Cause:** Data corruption during export/import, type conversion issues, or partial import.

**Solution:**
- Review diff output to identify specific differences
- Check if user IDs changed (should be preserved as integers)
- Verify counts per user match (no data loss)
- Re-run test with fresh baseline if database modified during test

**Critical:** Any difference indicates referential integrity failure.

---

### Issue 6: Sample user relationships incomplete

**Symptoms:**
```bash
# User 1 exists, but no quiz attempts found
SELECT * FROM quiz_attempts WHERE user_id = 1;
# Returns 0 rows (WRONG - baseline showed 5 quiz attempts)
```

**Cause:** Child table import failed or filtered out records.

**Solution:**
- Check import logs for errors during QuizAttempts import
- Verify quiz_attempts count in import summary matches export
- Query specific quiz attempt IDs from baseline to see if they exist
- Partial import would trigger rollback, so complete failure more likely

**Critical:** Missing relationships indicate data loss (test FAILS).

---

### Issue 7: Foreign key constraints defined but not enforced

**Symptoms:**
- Schema has FOREIGN KEY clauses
- PRAGMA foreign_keys returns 1
- But DELETE user succeeds anyway

**Cause:** SQLite bug (unlikely), schema not properly created, or ON DELETE CASCADE defined.

**Solution:**
- Check schema definition: `.schema users` and `.schema quiz_attempts`
- Look for ON DELETE CASCADE clause (allows deletion)
- Verify foreign key clause syntax: `FOREIGN KEY (user_id) REFERENCES users(id)`
- Re-create database from scratch if schema corrupted

**Note:** Chibi schema does NOT use ON DELETE CASCADE, so deletion should fail.

---

### Issue 8: Import fails with foreign key violation error

**Symptoms:**
```
❌ Import failed: FOREIGN KEY constraint failed at row 123 in QuizAttempts
```

**Cause:** Spreadsheet data corrupted (orphaned record in export) or import order issue.

**Solution:**
- Good news: Foreign key enforcement is working (import correctly rejected bad data)
- Bad news: Exported data had orphaned record (shouldn't happen)
- Check spreadsheet QuizAttempts sheet row 123 for invalid user_id
- Verify Users sheet has user with that ID
- If orphaned record in export, this indicates a bug in exporter or database was already corrupted

**Prevention:** Run PRAGMA foreign_key_check before export to detect existing issues.

---

## Success Validation

After completing all steps, you should have:

1. ✅ Zero orphaned records in all child tables
2. ✅ Relationship counts exactly match baseline
3. ✅ Foreign key constraints actively enforced
4. ✅ No foreign key violations detected by pragma
5. ✅ Specific user relationships intact and complete
6. ✅ Complete confidence in referential integrity for production use

---

## Additional Notes

### Why Referential Integrity Matters

**Production Impact:**
- Orphaned records cause data inconsistency
- Bot queries can fail with missing user references
- Statistics and progress tracking become inaccurate
- Cannot trust relationship data for grading or reports

**Data Consistency:**
- Foreign keys ensure every child has a valid parent
- Cascading deletes prevent orphaned records (if configured)
- Application logic relies on referential integrity
- Database constraints are last line of defense

**Import/Export Safety:**
- Import order critical: parent before child (Users before QuizAttempts)
- Foreign key enforcement during import prevents bad data
- Transaction rollback protects against partial imports
- Validation after import ensures no corruption

### Database Relationships in Chibi

**Parent Table: users**
- Primary key: id (INTEGER)
- All child tables reference users.id via user_id foreign key

**Child Tables:**
1. **quiz_attempts**: Student quiz answers and LLM feedback
2. **concept_mastery**: Learning progress tracking per concept
3. **llm_quiz_attempts**: "Stump the AI" challenge game records
4. **attendance**: Class attendance records

**Foreign Key Configuration:**
- Constraint: `FOREIGN KEY (user_id) REFERENCES users(id)`
- No ON DELETE CASCADE (deletions fail if children exist)
- Enforced via PRAGMA foreign_keys = ON during import

### Import Order Importance

**Correct order (parent first):**
```python
# sheets_importer.py:350-364
await self._import_users_table(...)          # Parent first
await self._import_quiz_attempts_table(...)  # Child second
await self._import_concept_mastery_table(...) # Child
await self._import_llm_quiz_attempts_table(...) # Child
await self._import_attendance_table(...)     # Child
```

**Why order matters:**
- SQLite checks foreign keys on INSERT
- Child INSERT fails if parent doesn't exist yet
- Import would rollback if order violated
- Parent-first guarantees all references valid

### Testing Best Practices

**Baseline recording:**
- Record relationships BEFORE export (not after)
- Export to file for automated diff comparison
- Sample specific users for detailed verification
- Record counts for all relationship types

**Validation methods:**
- Orphaned record queries (user_id NOT IN ...)
- JOIN queries to verify relationships
- PRAGMA foreign_key_check for comprehensive scan
- DELETE test to verify constraint enforcement

**Pass/fail clarity:**
- Zero orphaned records is absolute requirement
- Relationship counts must match exactly (no approximations)
- Foreign key constraints must be enforced (DELETE fails)
- Any failure indicates critical data integrity issue

---

## Test Complete

Mark MT-013 as **passing** in `prd.json` if all pass criteria met.

If any failures occur:
1. Document specific failures in test notes
2. Create bug report with reproduction steps
3. Reference this guide in bug report
4. Mark MT-013 as **failing** until fixed
