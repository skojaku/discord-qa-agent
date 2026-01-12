# Manual Testing Guide: MT-005 - Export with Large Dataset

## Test ID: MT-005
**Title:** Export with large dataset
**Priority:** 2 (Core Functionality - Export)
**Category:** Export
**Prerequisites:** MT-003 passed (basic export functionality verified)

---

## Objective

Verify that the Google Sheets export feature can handle large datasets efficiently through proper batching, completing within 60 seconds without API timeouts or rate limit errors.

---

## Background

The export feature implements batching to handle large datasets:
- **Batch size:** 1000 rows per API call (configurable in `GoogleSheetsClient.write_sheet()`)
- **Rate limiting:** Exponential backoff if 429 (rate limit) errors occur
- **Implementation:** `chibi/backup/google_sheets_client.py:171-193` (write_sheet with batching)
- **Expected performance:** < 60 seconds for datasets with 10+ users and 50+ quiz attempts

**Why batching matters:**
- Google Sheets API has per-request limits (max rows per write operation)
- Rate limits prevent overwhelming the API with too many requests
- Proper batching ensures reliability and performance at scale

**Implementation Reference:**
- Batching logic: `chibi/backup/google_sheets_client.py:171-193`
- Export orchestration: `chibi/backup/sheets_exporter.py:167-223`

---

## Prerequisites Checklist

Before starting:

- [ ] MT-003 passed (basic export functionality working)
- [ ] Bot is running (`uv run python main.py`)
- [ ] You have admin permissions in the test Discord server
- [ ] You have access to sqlite3 command-line tool
- [ ] You have Python installed for running data generation scripts
- [ ] Database backup created (if existing data is valuable)

---

## Part 1: Prepare Large Dataset

### Step 1: Backup Current Database

Preserve your current data before populating with test data:

```bash
cd /Users/skojaku-admin/Documents/projects/applied-soft-comp/tutor/discord-qa-agent
cp data/chibi.db data/chibi.db.backup
```

**Expected:** Backup file created successfully.

---

### Step 2: Check Current Database State

Record baseline counts:

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

**Expected:** See current counts (may be 0 or have existing data).

---

### Step 3: Populate Database with Test Data

Use the following SQL script to generate large test dataset:

```bash
sqlite3 data/chibi.db <<'EOF'
BEGIN TRANSACTION;

-- Create 15 test users
INSERT INTO users (discord_id, username, created_at, review_status, student_id)
VALUES
  (100000000000000001, 'test_user_01', datetime('now', '-30 days'), 'active', 'STU001'),
  (100000000000000002, 'test_user_02', datetime('now', '-29 days'), 'active', 'STU002'),
  (100000000000000003, 'test_user_03', datetime('now', '-28 days'), 'active', 'STU003'),
  (100000000000000004, 'test_user_04', datetime('now', '-27 days'), 'active', 'STU004'),
  (100000000000000005, 'test_user_05', datetime('now', '-26 days'), 'active', 'STU005'),
  (100000000000000006, 'test_user_06', datetime('now', '-25 days'), 'active', 'STU006'),
  (100000000000000007, 'test_user_07', datetime('now', '-24 days'), 'active', 'STU007'),
  (100000000000000008, 'test_user_08', datetime('now', '-23 days'), 'active', 'STU008'),
  (100000000000000009, 'test_user_09', datetime('now', '-22 days'), 'active', 'STU009'),
  (100000000000000010, 'test_user_10', datetime('now', '-21 days'), 'active', 'STU010'),
  (100000000000000011, 'test_user_11', datetime('now', '-20 days'), 'active', 'STU011'),
  (100000000000000012, 'test_user_12', datetime('now', '-19 days'), 'active', 'STU012'),
  (100000000000000013, 'test_user_13', datetime('now', '-18 days'), 'active', 'STU013'),
  (100000000000000014, 'test_user_14', datetime('now', '-17 days'), 'active', 'STU014'),
  (100000000000000015, 'test_user_15', datetime('now', '-16 days'), 'active', 'STU015');

COMMIT;
EOF
```

Now generate quiz attempts for each user (5 attempts per user = 75 total):

```bash
sqlite3 data/chibi.db <<'EOF'
BEGIN TRANSACTION;

-- Generate quiz attempts for each user
INSERT INTO quiz_attempts (user_id, module, concept, question, user_answer, correct_answer, is_correct, llm_feedback, quiz_timestamp)
SELECT
  u.id as user_id,
  'module_' || (ABS(RANDOM()) % 5 + 1) as module,
  'concept_' || (ABS(RANDOM()) % 10 + 1) as concept,
  'What is the definition of concept ' || (ABS(RANDOM()) % 10 + 1) || '? This is a test question with id ' || u.id || '-' || (n.value) || ' for testing large dataset export.' as question,
  'Test answer ' || (n.value) || ' from user ' || u.username as user_answer,
  'Correct answer ' || (n.value) as correct_answer,
  (ABS(RANDOM()) % 2) as is_correct,
  'This is LLM feedback for quiz attempt. The student provided a reasonable answer that demonstrates understanding of the concept. Score: ' || (ABS(RANDOM()) % 5 + 6) || '/10.' as llm_feedback,
  datetime('now', '-' || (ABS(RANDOM()) % 30) || ' days', '-' || (ABS(RANDOM()) % 24) || ' hours') as quiz_timestamp
FROM users u
CROSS JOIN (
  SELECT 1 as value UNION ALL SELECT 2 UNION ALL SELECT 3 UNION ALL SELECT 4 UNION ALL SELECT 5
) n
WHERE u.discord_id >= 100000000000000001;

COMMIT;
EOF
```

Generate concept mastery records (30 records):

```bash
sqlite3 data/chibi.db <<'EOF'
BEGIN TRANSACTION;

INSERT INTO concept_mastery (user_id, concept, mastery_score, last_updated)
SELECT
  u.id as user_id,
  'concept_' || (n.value) as concept,
  (ABS(RANDOM()) % 100) / 100.0 as mastery_score,
  datetime('now', '-' || (ABS(RANDOM()) % 15) || ' days') as last_updated
FROM users u
CROSS JOIN (
  SELECT 1 as value UNION ALL SELECT 2 UNION ALL SELECT 3
) n
WHERE u.discord_id >= 100000000000000001
LIMIT 30;

COMMIT;
EOF
```

---

### Step 4: Verify Test Data Creation

Check the new counts:

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
15     75             30               0                  0
```

(Note: Actual counts may be higher if you had existing data)

**Pass Criteria:**
- Users count >= 10
- Quiz attempts count >= 50

---

### Step 5: Record Baseline for Verification

Record detailed baseline counts:

```bash
sqlite3 data/chibi.db <<EOF
SELECT 'Total Users: ' || COUNT(*) FROM users;
SELECT 'Total Quiz Attempts: ' || COUNT(*) FROM quiz_attempts;
SELECT 'Total Concept Mastery: ' || COUNT(*) FROM concept_mastery;
SELECT 'Total LLM Quiz Attempts: ' || COUNT(*) FROM llm_quiz_attempts;
SELECT 'Total Attendance: ' || COUNT(*) FROM attendance;
EOF
```

**Write these numbers down** for comparison after export.

---

## Part 2: Execute Export and Measure Performance

### Step 6: Restart Bot

Restart the bot to ensure clean state:

```bash
# Stop the running bot (Ctrl+C or kill process)
# Then start it again:
uv run python main.py
```

**Expected:** Bot starts successfully with BackupService initialized.

---

### Step 7: Start Timer and Execute Export

Open Discord and run the export command. **Record the start time** (check your watch or phone):

```
/export-progress
```

**Important:** Note the exact time when you press Enter.

---

### Step 8: Observe Bot Response

Wait for the bot to respond. **Record the end time** when response appears.

**Expected Response Format:**
```
✅ Export Complete

Successfully exported student progress data to Google Sheets.

📊 Export Summary:
• Users: 15
• Quiz Attempts: 75
• Concept Mastery: 30
• LLM Quiz Attempts: 0
• Attendance: 0

📄 Spreadsheet:
[Link to Google Sheets]

Export completed at: 2026-01-12 10:30:45
```

**Calculate duration:** End time - Start time = Export duration

**Pass Criterion #1:** Export completes within 60 seconds.

---

### Step 9: Check Bot Logs for Batching

Check bot logs for evidence of batching operations:

```bash
# If running in terminal, scroll up to see logs
# Look for messages like:
# "Writing batch 1/1 (75 rows) to sheet QuizAttempts"
# or
# "Writing batch 1/2 (1000 rows) to sheet QuizAttempts"
# "Writing batch 2/2 (234 rows) to sheet QuizAttempts"
```

**Expected Log Entries:**
- "Authenticating with service account" or "Authenticated with cached token"
- "Creating spreadsheet: Chibi Student Progress - [timestamp]"
- "Exporting X records from [table_name]"
- "Writing batch X/Y (Z rows) to sheet [SheetName]" for each table
- "Successfully wrote X rows to [SheetName]"
- "Export completed successfully"

**Pass Criterion #2:** No error messages in logs (no API timeouts, no rate limit errors).

---

### Step 10: Verify Response Data

Check that the bot response matches baseline counts from Step 5:

- [ ] Users count matches baseline
- [ ] Quiz Attempts count matches baseline
- [ ] Concept Mastery count matches baseline
- [ ] LLM Quiz Attempts count matches baseline (likely 0)
- [ ] Attendance count matches baseline (likely 0)

**Pass Criterion #3:** All counts in bot response match database baseline.

---

## Part 3: Verify Spreadsheet Contents (Optional)

**Note:** If using service account credentials, the exported spreadsheet may not be accessible in your personal Google Drive. This is expected behavior. The test can pass based on bot response and logs alone (Steps 8-10).

If you have access to the spreadsheet link, perform these additional verification steps:

### Step 11: Open Spreadsheet Link

Click the Google Sheets link from the bot response.

**Expected:** Spreadsheet opens in browser with title "Chibi Student Progress - [timestamp]".

---

### Step 12: Check Sheet Structure

Verify all 6 sheets exist:
- [ ] Metadata
- [ ] Users
- [ ] QuizAttempts
- [ ] ConceptMastery
- [ ] LLMQuizAttempts
- [ ] Attendance

**Expected:** All 6 sheets present at bottom of spreadsheet.

---

### Step 13: Verify Metadata Sheet

Open the Metadata sheet. Check the counts:

| Key | Value |
|-----|-------|
| export_date | 2026-01-12T10:30:45 |
| schema_version | 1.0 |
| users_count | 15 |
| quiz_attempts_count | 75 |
| concept_mastery_count | 30 |
| llm_quiz_attempts_count | 0 |
| attendance_count | 0 |

**Pass Criterion #4 (Optional):** Metadata counts match baseline from Step 5.

---

### Step 14: Verify Data Sheet Row Counts

Count rows in each data sheet (exclude header row):

```
Users sheet: Should have 15 data rows + 1 header row = 16 total rows
QuizAttempts sheet: Should have 75 data rows + 1 header row = 76 total rows
ConceptMastery sheet: Should have 30 data rows + 1 header row = 31 total rows
```

**Pass Criterion #5 (Optional):** Data sheet row counts match baseline.

---

### Step 15: Check for Data Integrity

Open the QuizAttempts sheet and verify:
- [ ] Question text is complete (not truncated unless > 50k chars)
- [ ] LLM feedback is present and readable
- [ ] Boolean values appear as TRUE/FALSE (not 0/1)
- [ ] No obvious data corruption or garbled text

**Pass Criterion #6 (Optional):** Data appears correct and complete.

---

## Part 4: Cleanup and Restore

### Step 16: Delete Test Spreadsheet (Optional)

To avoid quota issues and clutter:

1. If you have access to service account's Drive, delete the test spreadsheet
2. Or simply leave it (service account has its own quota)

---

### Step 17: Restore Original Database

If you want to restore your original data:

```bash
cd /Users/skojaku-admin/Documents/projects/applied-soft-comp/tutor/discord-qa-agent
cp data/chibi.db.backup data/chibi.db
```

**Expected:** Original database restored.

---

### Step 18: Verify Restoration

Check counts match original:

```bash
sqlite3 data/chibi.db <<EOF
SELECT COUNT(*) as users FROM users;
SELECT COUNT(*) as quiz_attempts FROM quiz_attempts;
EOF
```

**Expected:** Counts match your pre-test baseline.

---

## Pass/Fail Criteria

### Minimum Passing Criteria (Steps 8-10)

This test **PASSES** if ALL of the following are true:

1. ✅ Export completes within 60 seconds (Step 8)
2. ✅ No error messages in bot logs - no API timeouts, no rate limit errors (Step 9)
3. ✅ Bot response counts match database baseline (Step 10)
4. ✅ Bot logs show batching operations (Step 9)

### Full Verification (Optional Steps 11-15)

If you have access to the spreadsheet, additionally verify:

5. ✅ Metadata sheet counts match baseline
6. ✅ Data sheet row counts match baseline
7. ✅ Data integrity maintained (no corruption, proper formatting)

**Note:** The test can pass based on minimum criteria alone (Steps 1-10) without spreadsheet access.

---

## Common Issues and Troubleshooting

### Issue 1: Export Takes Longer Than 60 Seconds

**Symptoms:** Export completes but takes 70+ seconds.

**Possible Causes:**
- Network latency to Google Sheets API
- System under heavy load
- Batching inefficient (batch size too small)

**Solutions:**
1. Check bot logs for batch sizes: should be writing 1000 rows per batch
2. Increase batch size in `chibi/backup/google_sheets_client.py:171` if needed
3. Run test again when network/system load is lower
4. If consistently slow, consider optimization (parallel writes, larger batches)

**Code Reference:** `chibi/backup/google_sheets_client.py:171-193` (write_sheet method)

---

### Issue 2: Rate Limit Errors (429)

**Symptoms:** Bot logs show "Rate limit exceeded" or "429 error".

**Possible Causes:**
- Too many API requests in short time window
- Batch size too small (more batches = more API calls)
- Multiple concurrent exports

**Solutions:**
1. Check logs for exponential backoff (should show retry attempts with delays)
2. Verify batch size is 1000 (not smaller)
3. Ensure only one export running at a time
4. If persistent, increase delay between batches

**Code Reference:** `chibi/backup/google_sheets_client.py:231-250` (rate limit handling)

---

### Issue 3: API Timeout Errors

**Symptoms:** "Request timeout" or "Connection timed out" errors.

**Possible Causes:**
- Network connectivity issues
- Google Sheets API temporarily unavailable
- Request payload too large (batch size too big)

**Solutions:**
1. Check internet connectivity
2. Retry export after a few minutes
3. Check Google Cloud Console for API status
4. If payload too large, reduce batch size (but keep >= 500)

---

### Issue 4: Data Counts Don't Match

**Symptoms:** Bot response shows different counts than database baseline.

**Possible Causes:**
- Data modified during export (new quiz attempts added)
- Filtering logic excluding some records
- Bug in query logic

**Solutions:**
1. Verify no other processes writing to database during export
2. Re-run baseline queries (Step 5) and compare again
3. Check export queries in `chibi/backup/sheets_exporter.py:167-223`
4. If persistent mismatch, report as bug with specific counts

**Code Reference:** `chibi/backup/sheets_exporter.py:167-223` (export table methods)

---

### Issue 5: Test Data Creation Fails

**Symptoms:** SQL script errors, foreign key violations, or zero rows created.

**Possible Causes:**
- Foreign key constraints blocking inserts
- Database locked by another process
- Schema mismatch (wrong column names)

**Solutions:**
1. Check that database is not locked: `lsof data/chibi.db`
2. Verify schema matches DATABASE_STRUCTURE.md
3. Run SQL scripts separately (users first, then quiz_attempts)
4. Use `PRAGMA foreign_keys = OFF;` before inserts if needed (not recommended)

---

## Expected Results Summary

**Performance:**
- Export duration: < 60 seconds for 15 users, 75 quiz attempts
- Batching: 1000 rows per batch (visible in logs)
- No rate limit errors or timeouts

**Data Integrity:**
- All counts match baseline
- No data loss or corruption
- Proper type conversions (0/1 → TRUE/FALSE, NULL → empty)

**Scalability:**
- System handles 10+ users and 50+ records smoothly
- Batching prevents API timeouts
- Performance acceptable for production use

---

## Additional Notes

**Performance Expectations:**
- Small datasets (< 100 rows): 5-10 seconds
- Medium datasets (100-1000 rows): 10-30 seconds
- Large datasets (1000+ rows): 30-60 seconds

**Batching Behavior:**
- Tables with < 1000 rows: Written in single batch
- Tables with >= 1000 rows: Split into multiple batches of 1000 rows each
- Last batch may be smaller (e.g., 234 rows)

**Rate Limiting:**
- Google Sheets API allows 100 requests per 100 seconds per user
- With batching, 1000 rows = 1 request
- Export of 5000 rows (across 5 tables) = 5 requests = well within limits

**Future Enhancements:**
- Parallel writes to different sheets (reduce total time)
- Progress bars for long exports
- Configurable batch size via config.yaml
- Compression for large text fields

---

## Test Complete

If all pass criteria met, mark **MT-005 as PASSED** in `prd.json`.

Document any issues encountered in `docs/manual-testing-log.md` (if it exists) or create a GitHub issue for tracking.
