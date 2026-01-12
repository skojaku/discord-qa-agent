# Manual Testing Guide: MT-012 - Data Type Preservation

## Test ID: MT-012
**Title:** Data type preservation through export/import cycle
**Priority:** 4 (Data Integrity)
**Category:** Integrity
**Prerequisites:** MT-003 and MT-006 passed (export and import functionality working)

---

## Objective

Verify that all SQLite data types are correctly preserved through a complete export/import cycle, including NULL values, booleans, timestamps, and long text fields. This test validates that data transformations are reversible and no data corruption or type errors occur.

---

## Background

The backup system transforms SQLite data types for Google Sheets compatibility, then reverses these transformations during import:

**Export Transformations (SQLite → Sheets):**
1. `NULL` → `""` (empty string)
2. `BOOLEAN` (0/1) → `"TRUE"`/`"FALSE"` strings
3. `TIMESTAMP` → ISO string format (preserved)
4. `TEXT` > 50k chars → truncated to 50,000 chars
5. `INTEGER`, `REAL` → preserved as numbers

**Import Transformations (Sheets → SQLite):**
1. `""` (empty string) → `NULL`
2. `"TRUE"`/`"FALSE"` → 1/0 (BOOLEAN)
3. ISO timestamp strings → preserved as TEXT
4. Numeric strings → `int` or `float` (based on column type)
5. Text → preserved

**Implementation details:**
- Exporter transformations: `chibi/backup/sheets_exporter.py:246-279` (`_transform_row()`)
- Importer transformations: `chibi/backup/sheets_importer.py:381-440` (`_convert_sheet_row_to_sqlite()`)
- Column type definitions: `sheets_importer.py:45-65`

**Critical validation points:**
- Booleans: `is_correct`, `student_wins` must remain 0/1 after cycle
- NULLs: `student_id`, `llm_feedback` must remain NULL if originally NULL
- Timestamps: ISO format preserved exactly
- Long text: Question/feedback fields preserved (within 50k limit)

---

## Prerequisites Checklist

Before starting:

- [ ] MT-003 passed (export functionality working)
- [ ] MT-006 passed (import with replace mode working)
- [ ] Database has diverse data including NULL values, booleans, timestamps
- [ ] Bot is running (`uv run python main.py`)
- [ ] You have admin permissions in the test Discord server
- [ ] You have access to sqlite3 command-line tool

---

## Part 1: Prepare Test Data with Diverse Types

### Step 1: Verify Database Has Diverse Data Types

Check that your database contains examples of all data types we need to test:

```bash
cd /Users/skojaku-admin/Documents/projects/applied-soft-comp/tutor/discord-qa-agent

# Check for NULL values in users
sqlite3 data/chibi.db "SELECT COUNT(*) FROM users WHERE student_id IS NULL;"

# Check for boolean values (0 and 1) in quiz_attempts
sqlite3 data/chibi.db "SELECT is_correct, COUNT(*) FROM quiz_attempts GROUP BY is_correct;"

# Check for timestamps
sqlite3 data/chibi.db "SELECT created_at FROM users LIMIT 3;"

# Check for long text (question or llm_feedback fields)
sqlite3 data/chibi.db "SELECT LENGTH(question) as len FROM quiz_attempts ORDER BY len DESC LIMIT 3;"
```

**Expected:**
- At least 1 user with NULL student_id (most users should have this)
- Both 0 and 1 values for is_correct (mix of correct and incorrect answers)
- Timestamps in ISO format (YYYY-MM-DD HH:MM:SS)
- Some questions with varying lengths

**If data is missing:** Create test data by taking quizzes via `/quiz` command or add directly via SQL if needed.

---

### Step 2: Record Baseline Data for Comparison

Sample specific records that represent each data type:

```bash
# Record a user with NULL student_id
sqlite3 data/chibi.db <<EOF
.mode column
SELECT id, discord_id, username, student_id, student_name, created_at
FROM users
WHERE student_id IS NULL
LIMIT 1;
EOF
```

**Write down:** User ID, discord_id, username, NULL status, timestamp

```bash
# Record quiz attempts with both correct (1) and incorrect (0)
sqlite3 data/chibi.db <<EOF
.mode column
SELECT id, user_id, is_correct, llm_quality_score, LENGTH(question) as question_len, LENGTH(llm_feedback) as feedback_len
FROM quiz_attempts
WHERE is_correct = 1
LIMIT 1;
EOF

sqlite3 data/chibi.db <<EOF
.mode column
SELECT id, user_id, is_correct, llm_quality_score, LENGTH(question) as question_len, LENGTH(llm_feedback) as feedback_len
FROM quiz_attempts
WHERE is_correct = 0
LIMIT 1;
EOF
```

**Write down:** Two quiz attempt records - one with is_correct=1, one with is_correct=0

```bash
# Record LLM quiz with student_wins boolean
sqlite3 data/chibi.db <<EOF
.mode column
SELECT id, user_id, student_wins, LENGTH(question) as q_len
FROM llm_quiz_attempts
LIMIT 2;
EOF
```

**Write down:** LLM quiz records with different student_wins values if available

```bash
# Record exact timestamp formats
sqlite3 data/chibi.db "SELECT created_at FROM quiz_attempts LIMIT 3;"
```

**Write down:** Three timestamp examples to verify exact format preservation

---

### Step 3: Create Comprehensive Data Type Reference

Create a reference document with exact values to compare after import:

```bash
# Export comprehensive data sample
sqlite3 data/chibi.db <<EOF > baseline-data-types-mt012.txt
.mode column
.headers on

-- Sample users with NULL and non-NULL student_id
SELECT 'USERS TABLE' as section;
SELECT id, discord_id, student_id, created_at FROM users LIMIT 5;

-- Sample quiz attempts with boolean variety
SELECT 'QUIZ_ATTEMPTS TABLE' as section;
SELECT id, user_id, is_correct, created_at FROM quiz_attempts LIMIT 5;

-- Sample concept mastery with REAL (float) values
SELECT 'CONCEPT_MASTERY TABLE' as section;
SELECT id, user_id, avg_quality_score, last_attempt_at FROM concept_mastery LIMIT 3;

-- Sample LLM quiz with boolean
SELECT 'LLM_QUIZ_ATTEMPTS TABLE' as section;
SELECT id, user_id, student_wins, created_at FROM llm_quiz_attempts LIMIT 3;

-- Sample attendance with timestamps
SELECT 'ATTENDANCE TABLE' as section;
SELECT id, user_id, timestamp, date_id FROM attendance LIMIT 3;
EOF
```

**Expected:** File `baseline-data-types-mt012.txt` created with sample data from all tables.

**Keep this file** - we'll compare it after import to verify exact preservation.

---

## Part 2: Perform Export

### Step 4: Export Current Database

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

**Record the export time** - this will help identify the correct export in /list-exports.

---

### Step 5: Verify Transformations in Spreadsheet (Optional)

**Note:** If using service account credentials, you may not be able to access the spreadsheet. That's okay - skip to Step 6.

If accessible, open the spreadsheet and verify transformations occurred:

**Users Sheet:**
- Check that NULL `student_id` appears as empty cell (not "NULL" text)
- Check that `created_at` is ISO format string

**QuizAttempts Sheet:**
- Check that `is_correct` column shows "TRUE" or "FALSE" (not 0/1)
- Check that NULL `llm_feedback` appears as empty cell

**ConceptMastery Sheet:**
- Check that `avg_quality_score` shows decimal numbers (e.g., 75.5)

**Expected:** Transformations visible in spreadsheet (empty cells for NULL, TRUE/FALSE for booleans).

---

## Part 3: Clear Database and Import

### Step 6: Backup Current Database

Preserve current data:

```bash
cp data/chibi.db data/chibi.db.backup-mt012
```

**Expected:** Backup created successfully.

---

### Step 7: Clear Database to Simulate Fresh Import

Delete database to test complete restoration:

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
INFO - BackupCog loaded
```

**Verify empty database:**
```bash
sqlite3 data/chibi.db "SELECT COUNT(*) FROM users;"
# Should output: 0
```

---

### Step 9: Import from Spreadsheet

In Discord, run import with the URL from Step 4:

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

Database has been restored to the exported state.
```

**Verify:** Response shows same counts as export (Step 4).

---

## Part 4: Verify Data Type Preservation

### Step 10: Verify Boolean Type Preservation

Check that boolean values are 0/1 (not "TRUE"/"FALSE" strings):

```bash
# Check is_correct column type and values
sqlite3 data/chibi.db <<EOF
.mode column
SELECT DISTINCT is_correct, typeof(is_correct) as type FROM quiz_attempts;
EOF
```

**Expected output:**
```
is_correct  type
----------  -------
0           integer
1           integer
```

**CRITICAL:** Type must be `integer`, values must be 0 or 1 (not text "TRUE"/"FALSE").

```bash
# Check student_wins column
sqlite3 data/chibi.db <<EOF
SELECT DISTINCT student_wins, typeof(student_wins) as type FROM llm_quiz_attempts;
EOF
```

**Expected:** Values 0 or 1 with type `integer`.

**Pass criteria:** All boolean columns are integers (0/1), not text.

---

### Step 11: Verify NULL Type Preservation

Check that NULL values were restored (not empty strings):

```bash
# Check for NULL student_id
sqlite3 data/chibi.db "SELECT COUNT(*) FROM users WHERE student_id IS NULL;"
```

**Compare to baseline (Step 2):** Count should match exactly.

```bash
# Verify specific user has NULL (not empty string)
sqlite3 data/chibi.db <<EOF
.mode column
SELECT id, discord_id, student_id, typeof(student_id) as type
FROM users
WHERE student_id IS NULL
LIMIT 1;
EOF
```

**Expected output:**
```
id  discord_id  student_id  type
--  ----------  ----------  ----
N   123456789   <NULL>      null
```

**CRITICAL:** Type must be `null`, not `text` with empty value.

```bash
# Check NULL in other columns
sqlite3 data/chibi.db "SELECT COUNT(*) FROM quiz_attempts WHERE correct_answer IS NULL;"
sqlite3 data/chibi.db "SELECT COUNT(*) FROM quiz_attempts WHERE llm_feedback IS NULL;"
```

**Pass criteria:** NULL values preserved, not converted to empty strings.

---

### Step 12: Verify Timestamp Preservation

Check that timestamps remain in exact ISO format:

```bash
# Check timestamp format
sqlite3 data/chibi.db "SELECT created_at FROM quiz_attempts LIMIT 3;"
```

**Compare to baseline (Step 2):** Timestamps should match exactly, character for character.

**Expected format:** `YYYY-MM-DD HH:MM:SS` (e.g., `2026-01-12 14:35:22`)

```bash
# Verify timestamp type
sqlite3 data/chibi.db <<EOF
SELECT created_at, typeof(created_at) as type FROM users LIMIT 1;
EOF
```

**Expected:** Type is `text` (SQLite stores timestamps as text in ISO format).

**Pass criteria:** All timestamps match baseline exactly (no timezone conversion, no format changes).

---

### Step 13: Verify Numeric Type Preservation

Check that integers and floats are preserved correctly:

```bash
# Check INTEGER columns
sqlite3 data/chibi.db <<EOF
SELECT id, user_id, typeof(id) as id_type, typeof(user_id) as user_id_type
FROM quiz_attempts
LIMIT 1;
EOF
```

**Expected:** Both types are `integer`.

```bash
# Check REAL (float) columns
sqlite3 data/chibi.db <<EOF
SELECT avg_quality_score, typeof(avg_quality_score) as type
FROM concept_mastery
WHERE avg_quality_score > 0
LIMIT 1;
EOF
```

**Expected:** Type is `real`, value has decimal places (e.g., 75.5).

**Pass criteria:** Numeric types preserved (integers as integer, floats as real).

---

### Step 14: Verify Long Text Field Preservation

Check that long text fields (question, llm_feedback) are preserved:

```bash
# Check question field lengths
sqlite3 data/chibi.db <<EOF
SELECT id, LENGTH(question) as question_len, SUBSTR(question, 1, 50) as preview
FROM quiz_attempts
WHERE LENGTH(question) > 100
LIMIT 2;
EOF
```

**Compare to baseline (Step 2):** Lengths should match (or be capped at 50,000 if originally longer).

```bash
# Check llm_feedback preservation
sqlite3 data/chibi.db <<EOF
SELECT id, LENGTH(llm_feedback) as feedback_len
FROM quiz_attempts
WHERE llm_feedback IS NOT NULL
LIMIT 3;
EOF
```

**Expected:** Lengths match baseline, no truncation (unless original > 50k chars).

**Pass criteria:** Text fields preserved with correct content and length.

---

### Step 15: Verify Complete Data Type Reference

Compare imported data to baseline reference:

```bash
# Export post-import data sample
sqlite3 data/chibi.db <<EOF > postimport-data-types-mt012.txt
.mode column
.headers on

-- Sample users with NULL and non-NULL student_id
SELECT 'USERS TABLE' as section;
SELECT id, discord_id, student_id, created_at FROM users LIMIT 5;

-- Sample quiz attempts with boolean variety
SELECT 'QUIZ_ATTEMPTS TABLE' as section;
SELECT id, user_id, is_correct, created_at FROM quiz_attempts LIMIT 5;

-- Sample concept mastery with REAL (float) values
SELECT 'CONCEPT_MASTERY TABLE' as section;
SELECT id, user_id, avg_quality_score, last_attempt_at FROM concept_mastery LIMIT 3;

-- Sample LLM quiz with boolean
SELECT 'LLM_QUIZ_ATTEMPTS TABLE' as section;
SELECT id, user_id, student_wins, created_at FROM llm_quiz_attempts LIMIT 3;

-- Sample attendance with timestamps
SELECT 'ATTENDANCE TABLE' as section;
SELECT id, user_id, timestamp, date_id FROM attendance LIMIT 3;
EOF
```

**Compare files:**
```bash
diff baseline-data-types-mt012.txt postimport-data-types-mt012.txt
```

**Expected:** Files are identical (diff shows no differences).

**Pass criteria:** All data matches exactly - no type corruption, no data loss.

---

## Part 5: Verify Bot Functionality with Restored Data

### Step 16: Test Bot Commands with Restored Types

Verify that the bot can use restored data correctly:

```bash
# In Discord:
/status
```

**Expected:** Status command works, shows correct user data.

```bash
# Check if bot handles booleans correctly
# Review recent quiz history - should show correct/incorrect properly
```

**Expected:** Bot interprets boolean values correctly (not confused by type).

```bash
# Test creating new data to verify schema integrity
/quiz
# Take a quiz, submit an answer
```

**Expected:** New quiz attempt created successfully, database not corrupted.

**Pass criteria:** Bot functions normally with restored data, no type-related errors.

---

## Part 6: Cleanup

### Step 17: Verify Test Completion

Check that all data types are preserved:

**Checklist:**
- [ ] Booleans are 0/1 integers (not "TRUE"/"FALSE" text)
- [ ] NULLs are NULL (not empty strings)
- [ ] Timestamps are ISO format text (exact match to baseline)
- [ ] Integers are integer type
- [ ] Floats are real type with decimals
- [ ] Long text fields preserved (within 50k limit)
- [ ] Bot functions normally with restored data

---

### Step 18: Cleanup Files and Restore (Optional)

You can keep the imported data or restore the original:

**Option A: Keep imported data (data matches original)**
```bash
# Keep current database, remove backup
rm data/chibi.db.backup-mt012
rm baseline-data-types-mt012.txt postimport-data-types-mt012.txt
```

**Option B: Restore original database**
```bash
# Restore backup, keep test files for review
cp data/chibi.db.backup-mt012 data/chibi.db
```

---

## Pass/Fail Criteria

### Minimum Passing Criteria

The test PASSES if ALL of the following are true:

1. **Boolean preservation (Step 10):**
   - [ ] `is_correct` values are 0 or 1 (integer type)
   - [ ] `student_wins` values are 0 or 1 (integer type)
   - [ ] No "TRUE" or "FALSE" text strings in database

2. **NULL preservation (Step 11):**
   - [ ] NULL `student_id` values remain NULL (not empty string "")
   - [ ] Count of NULL values matches baseline exactly
   - [ ] `typeof()` returns 'null' for NULL values

3. **Timestamp preservation (Step 12):**
   - [ ] All timestamps in exact ISO format (YYYY-MM-DD HH:MM:SS)
   - [ ] Timestamps match baseline character-for-character
   - [ ] No timezone conversion or format changes

4. **Numeric preservation (Step 13):**
   - [ ] INTEGER columns have 'integer' type
   - [ ] REAL columns have 'real' type with decimal precision
   - [ ] No type coercion or precision loss

5. **Text preservation (Step 14):**
   - [ ] Long text fields preserved completely (or capped at 50k)
   - [ ] No truncation or corruption
   - [ ] Content matches baseline

6. **Complete data integrity (Step 15):**
   - [ ] Baseline and post-import files match (diff shows no differences)

7. **Bot functionality (Step 16):**
   - [ ] /status command works correctly
   - [ ] Bot can create new quiz attempts
   - [ ] No type-related errors in logs

### Test FAILS if:

- ❌ Any boolean appears as "TRUE"/"FALSE" text (type corruption)
- ❌ Any NULL appears as empty string "" (type loss)
- ❌ Any timestamp format changed or lost precision
- ❌ Any numeric value lost type or precision
- ❌ Any text field truncated unexpectedly (< 50k limit)
- ❌ Baseline and post-import files show differences (data corruption)
- ❌ Bot commands fail or show incorrect data (functional regression)

---

## Common Issues and Troubleshooting

### Issue 1: Boolean columns show "TRUE"/"FALSE" text instead of 0/1

**Symptoms:**
```bash
sqlite3 data/chibi.db "SELECT DISTINCT is_correct, typeof(is_correct) FROM quiz_attempts;"
# Shows: TRUE, text (WRONG)
```

**Cause:** Importer failed to convert "TRUE"/"FALSE" strings back to 0/1 integers.

**Solution:**
- Check importer conversion logic: `chibi/backup/sheets_importer.py:381-440`
- Verify BOOLEAN_COLUMNS definition includes all boolean fields: `sheets_importer.py:45-50`
- Check logs for conversion errors during import

**Code reference:** `sheets_importer.py:393-397` - boolean conversion

---

### Issue 2: NULL values imported as empty strings

**Symptoms:**
```bash
sqlite3 data/chibi.db "SELECT COUNT(*) FROM users WHERE student_id IS NULL;"
# Shows: 0 (WRONG - should have NULL values)

sqlite3 data/chibi.db "SELECT COUNT(*) FROM users WHERE student_id = '';"
# Shows: N (empty strings instead of NULL)
```

**Cause:** Importer failed to convert empty strings back to NULL.

**Solution:**
- Check importer conversion: `sheets_importer.py:384-388`
- Verify empty string → None conversion happens first
- Check that database schema allows NULL for these columns

**Code reference:** `sheets_importer.py:384-388` - empty string to None conversion

---

### Issue 3: Timestamp format changed or lost precision

**Symptoms:**
```bash
# Baseline shows: 2026-01-12 14:35:22
# Post-import shows: 2026-01-12T14:35:22.000Z (WRONG - format changed)
```

**Cause:** Exporter or importer applied timezone conversion or reformatting.

**Solution:**
- Timestamps should be preserved as-is (no conversion)
- Check exporter: `sheets_exporter.py:246-279` - timestamps should pass through unchanged
- Check importer: `sheets_importer.py:381-440` - timestamps should not be reformatted

**Code reference:** Timestamps are TEXT type, should be preserved exactly as stored.

---

### Issue 4: Floating point precision lost

**Symptoms:**
```bash
# Baseline shows: avg_quality_score = 75.555555
# Post-import shows: avg_quality_score = 75.56 (rounded)
```

**Cause:** Google Sheets may round floats, or importer converts to wrong type.

**Solution:**
- Google Sheets has ~15 digit precision (should be sufficient)
- Check that FLOAT_COLUMNS includes all REAL columns: `sheets_importer.py:58-65`
- Verify conversion uses float(), not int(): `sheets_importer.py:405-408`

**Code reference:** `sheets_importer.py:405-408` - float conversion

---

### Issue 5: Long text fields truncated unexpectedly

**Symptoms:**
```bash
# Question length baseline: 5000 chars
# Question length post-import: 1000 chars (WRONG - truncated)
```

**Cause:** Exporter truncates to 50k, but shouldn't truncate shorter text.

**Solution:**
- Check exporter truncation logic: `sheets_exporter.py:267-279`
- Should only truncate if length > 50,000
- Verify Google Sheets didn't impose additional limits
- Check importer doesn't truncate: `sheets_importer.py:381-440`

**Code reference:** `sheets_exporter.py:267-279` - truncation at 50k char limit

---

### Issue 6: Diff shows differences between baseline and post-import

**Symptoms:**
```bash
diff baseline-data-types-mt012.txt postimport-data-types-mt012.txt
# Shows differences (any non-empty output is WRONG)
```

**Cause:** Data corruption, type conversion errors, or data loss during export/import.

**Solution:**
- Review diff output to identify which fields differ
- Check exporter and importer logic for those specific fields
- Verify transformations are reversible
- Re-run test from Step 1 to ensure baseline is correct

**Critical:** Any difference indicates data integrity failure (test FAILS).

---

### Issue 7: Bot commands fail after import

**Symptoms:**
- /status command shows error
- /quiz command fails to create new attempts
- Logs show type errors or SQL errors

**Cause:** Database corruption from type mismatches.

**Solution:**
- Check logs for specific error messages
- Verify foreign key relationships intact: `sqlite3 data/chibi.db "PRAGMA foreign_key_check;"`
- Restart bot to clear caches
- If corruption severe, restore backup and investigate importer

**Prevention:** Run all previous verification steps (10-15) to catch issues early.

---

## Success Validation

After completing all steps, you should have:

1. ✅ Database with all original data types preserved
2. ✅ Booleans as 0/1 integers
3. ✅ NULLs as actual NULL values
4. ✅ Timestamps in exact ISO format
5. ✅ Numeric types (integer/real) preserved
6. ✅ Text fields complete and uncorrupted
7. ✅ Bot functioning normally with restored data
8. ✅ Complete confidence in data type preservation for production use

---

## Additional Notes

### Why Data Type Preservation Matters

**Production Impact:**
- Type corruption can cause bot commands to fail
- Boolean logic may break if stored as text ("TRUE" != true)
- NULL vs empty string has different semantics in queries
- Timestamp format affects sorting and date calculations
- Precision loss in floats affects statistics and progress tracking

**Data Integrity:**
- SQLite schema defines expected types
- Type mismatches can cause INSERT failures
- Foreign key constraints depend on integer types
- Application code expects specific types

**Reversibility:**
- Export/import should be lossless (within 50k text limit)
- Multiple export/import cycles should preserve data
- Data transformations must be reversible
- Critical for disaster recovery and data migration

### Future Enhancements

If type preservation issues are discovered:
- Add unit tests for each data type conversion
- Consider using JSON format instead of Sheets (no type coercion)
- Add validation checks during import to detect type mismatches
- Provide detailed import report showing type conversions
- Add warnings for potential precision loss (floats, long text)

---

## Test Complete

Mark MT-012 as **passing** in `prd.json` if all pass criteria met.

If any failures occur:
1. Document specific failures in test notes
2. Create bug report with reproduction steps
3. Reference this guide in bug report
4. Mark MT-012 as **failing** until fixed
