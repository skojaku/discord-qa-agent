# Manual Testing Guide: MT-004 - Export with Empty Database

## Test Objective

Verify that the Google Sheets export functionality handles empty databases gracefully, creating a properly structured spreadsheet with headers but no data rows.

## Background

This test validates edge case handling. An empty database export should:
1. Complete successfully without errors
2. Create all required sheets with proper structure
3. Show zero counts in the Metadata sheet
4. Include header rows but no data rows in all data sheets

This scenario can occur when:
- Setting up Chibi bot on a new server
- Testing the backup feature before any student activity
- Recovering from a database corruption that required clearing all data

**Implementation Reference:** chibi/backup/sheets_exporter.py:167-223

## Prerequisites

Before starting this test, verify:
- [ ] MT-003 passed (basic export functionality works)
- [ ] Bot is running with admin permissions
- [ ] You have backup of current database (if it contains important data)
- [ ] You can execute sqlite3 commands
- [ ] You have admin role in Discord test server

## Part 1: Backup Current Database

### Step 1: Backup existing database

Preserve your current data before clearing:

```bash
cd /Users/skojaku-admin/Documents/projects/applied-soft-comp/tutor/discord-qa-agent
cp data/chibi.db data/chibi.db.backup
```

**Expected:** Backup file created successfully.

### Step 2: Verify backup integrity

Check backup file size matches original:

```bash
ls -lh data/chibi.db data/chibi.db.backup
```

**Expected:** Both files exist with similar file sizes (within a few KB).

## Part 2: Clear Database and Verify Empty State

### Step 3: Clear all user data

Execute SQL commands to delete all student progress:

```bash
sqlite3 data/chibi.db <<EOF
DELETE FROM attendance;
DELETE FROM llm_quiz_attempts;
DELETE FROM concept_mastery;
DELETE FROM quiz_attempts;
DELETE FROM users;
EOF
```

**Expected:** No error messages. If you see errors about foreign key constraints, the tables have dependencies that need to be cleared in the correct order (which the commands above respect).

### Step 4: Verify database is empty

Check that all tables have zero rows:

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

### Step 5: Verify schema still exists

Confirm that tables still exist with proper structure:

```bash
sqlite3 data/chibi.db ".tables"
```

**Expected:** Should list all tables (users, quiz_attempts, concept_mastery, llm_quiz_attempts, attendance, similarity_hashes, conversation_history).

### Step 6: Restart bot with clean state

This ensures the bot recognizes the empty database state:

```bash
# Stop the bot if running (Ctrl+C in bot terminal)
# Then start it again:
uv run python main.py
```

**Expected:** Bot starts successfully. Check logs for:
- "BackupService initialized successfully"
- "Loaded extension: chibi.cogs.backup_cog"
- No errors about missing tables or schema issues

## Part 3: Execute Export Command

### Step 7: Run export command in Discord

In your Discord test server, as a user with admin permissions:

```
/export-progress
```

**Expected Bot Response (within 5-10 seconds):**
- Embed with title "Student Progress Exported"
- Google Sheets link (may not be accessible - see MT-003 learnings)
- Summary showing all zero counts:
  - Users: 0
  - Quiz Attempts: 0
  - Concept Mastery: 0
  - LLM Quiz Attempts: 0
  - Attendance: 0

**Example Response:**
```
Student Progress Exported ✅

Successfully exported student progress data to Google Sheets.

Spreadsheet Link
https://docs.google.com/spreadsheets/d/[spreadsheet-id]

Export Summary
Users: 0
Quiz Attempts: 0
Concept Mastery: 0
LLM Quiz Attempts: 0
Attendance: 0
```

### Step 8: Check bot logs for export details

Look at the bot terminal output for detailed logging:

**Expected Log Messages:**
```
INFO:chibi.backup.backup_service:Starting export of student progress
INFO:chibi.backup.sheets_exporter:Exporting 0 records from users table
INFO:chibi.backup.sheets_exporter:Exporting 0 records from quiz_attempts table
INFO:chibi.backup.sheets_exporter:Exporting 0 records from concept_mastery table
INFO:chibi.backup.sheets_exporter:Exporting 0 records from llm_quiz_attempts table
INFO:chibi.backup.sheets_exporter:Exporting 0 records from attendance table
INFO:chibi.backup.backup_service:Export completed successfully
```

**Red Flags (Should NOT appear):**
- ERROR messages
- "Failed to export"
- Python exceptions or stack traces
- "No such table" errors

## Part 4: Verify Spreadsheet Contents (If Accessible)

**Note:** Due to service account limitations, you may not be able to open the spreadsheet link. If the link is not accessible, this test PASSES based on bot response and logs alone (Steps 7-8). The remaining steps are optional verification if you have access.

### Step 9: Open exported spreadsheet

Click the Google Sheets link from bot response.

**Expected:**
- Spreadsheet opens in browser (if accessible)
- Title: "Chibi Student Progress - [current date/time]"
- 6 sheets visible at bottom: Metadata, Users, QuizAttempts, ConceptMastery, LLMQuizAttempts, Attendance

**If Link Not Accessible:** Skip to Pass/Fail Criteria. Test passes based on bot response.

### Step 10: Verify Metadata sheet structure

Open the Metadata sheet.

**Expected Content:**
```
export_date          | [timestamp]
schema_version       | 1.0
users_count          | 0
quiz_attempts_count  | 0
concept_mastery_count| 0
llm_quiz_attempts_count | 0
attendance_count     | 0
```

**Verification:**
- All count fields show 0
- export_date is valid ISO timestamp
- schema_version is "1.0"

### Step 11: Verify data sheets have headers only

Check each data sheet (Users, QuizAttempts, ConceptMastery, LLMQuizAttempts, Attendance):

**Expected for Users sheet:**
- Row 1: Headers (id, discord_id, username, display_name, created_at, student_id, review_status)
- Row 2: Empty (no data)

**Expected for QuizAttempts sheet:**
- Row 1: Headers (id, user_id, question, options, correct_answer, user_answer, is_correct, module_name, concept, timestamp, llm_feedback, time_to_answer)
- Row 2: Empty (no data)

**Expected for ConceptMastery sheet:**
- Row 1: Headers (id, user_id, concept, module_name, correct_count, incorrect_count, last_attempted, mastery_score)
- Row 2: Empty (no data)

**Expected for LLMQuizAttempts sheet:**
- Row 1: Headers (id, user_id, question, llm_answer, student_answer, student_wins, timestamp)
- Row 2: Empty (no data)

**Expected for Attendance sheet:**
- Row 1: Headers (id, user_id, event_type, timestamp)
- Row 2: Empty (no data)

## Part 5: Restore Original Database

### Step 12: Restore backup

Replace empty database with your backup:

```bash
cd /Users/skojaku-admin/Documents/projects/applied-soft-comp/tutor/discord-qa-agent
cp data/chibi.db.backup data/chibi.db
```

### Step 13: Verify restoration

Check that data is restored:

```bash
sqlite3 data/chibi.db <<EOF
SELECT
  (SELECT COUNT(*) FROM users) as users,
  (SELECT COUNT(*) FROM quiz_attempts) as quiz_attempts;
EOF
```

**Expected:** Non-zero counts matching your backup.

### Step 14: Restart bot

```bash
# Stop bot (Ctrl+C)
# Start bot
uv run python main.py
```

**Expected:** Bot starts successfully and operates normally.

## Pass/Fail Criteria

### Minimum Passing Requirements (Steps 7-8)
This test PASSES if:
1. ✅ Export command completes without error
2. ✅ Bot response shows success message with spreadsheet link
3. ✅ All counts in bot response show 0
4. ✅ Bot logs show "Export completed successfully"
5. ✅ No ERROR messages in logs

### Full Verification (Steps 9-11, if accessible)
Additional passing criteria if spreadsheet is accessible:
6. ✅ Spreadsheet created with all 6 sheets
7. ✅ Metadata sheet shows 0 for all table counts
8. ✅ All data sheets have header row present
9. ✅ All data sheets have no data rows (only headers)
10. ✅ No extra sheets or malformed content

### This test FAILS if:
- ❌ Export command returns error message
- ❌ Bot crashes or throws exception
- ❌ Bot response shows non-zero counts
- ❌ Logs show ERROR messages
- ❌ No spreadsheet link provided
- ❌ Metadata sheet shows incorrect schema (if accessible)
- ❌ Any data sheet is missing headers (if accessible)
- ❌ Any required sheet is missing (if accessible)

## Common Issues and Solutions

### Issue 1: "DELETE FROM users" fails with foreign key constraint error

**Symptom:** Error message about foreign key constraint when deleting users.

**Cause:** Child tables (quiz_attempts, concept_mastery) still have references to users.

**Solution:** Delete in correct order (children first):
```bash
sqlite3 data/chibi.db <<EOF
DELETE FROM attendance;
DELETE FROM llm_quiz_attempts;
DELETE FROM concept_mastery;
DELETE FROM quiz_attempts;
DELETE FROM users;
EOF
```

### Issue 2: Bot response shows empty embed

**Symptom:** Bot responds but embed has no content or missing fields.

**Cause:** Possible Discord API timeout or embed formatting issue.

**Solution:**
1. Check bot logs for detailed error messages
2. Verify bot has proper Discord permissions (Send Messages, Embed Links)
3. Check if spreadsheet was still created (logs will show)
4. Try export command again

### Issue 3: Export takes longer than expected

**Symptom:** Export command takes more than 15 seconds to respond.

**Cause:** Google Sheets API might be slow or rate limited.

**Solution:**
- Wait up to 30 seconds before assuming failure
- Check bot logs for progress messages
- Verify Google Sheets API quota not exceeded
- This is acceptable as long as export completes

### Issue 4: Cannot restore backup

**Symptom:** "cp: cannot stat 'data/chibi.db.backup': No such file or directory"

**Cause:** Backup file wasn't created or was created in wrong location.

**Solution:**
```bash
# Check if backup exists
ls -la data/chibi.db*

# If backup exists but bot is locking database:
# Stop bot first, then restore
cp data/chibi.db.backup data/chibi.db
```

### Issue 5: Spreadsheet shows unexpected data

**Symptom:** Data sheets have rows when they should be empty.

**Cause:** Database wasn't actually empty, or export used stale cache.

**Solution:**
1. Verify database is empty (Step 4)
2. Ensure bot was restarted after clearing data (Step 6)
3. Try export again
4. Check if you cleared ALL tables (not just some)

## Technical Notes

**Why This Test Matters:**
- Validates error handling for edge case (empty database)
- Ensures export doesn't fail when no data exists
- Verifies spreadsheet structure is independent of data presence
- Tests that metadata counts are accurate (zero is valid)

**Implementation Details:**
- Exporter queries each table separately: chibi/backup/sheets_exporter.py:167-223
- Empty result sets should be handled gracefully (no exceptions)
- Metadata generation should work with zero counts
- Sheet creation happens regardless of data presence
- Header rows are written even when no data rows follow

**Related Code:**
- Export orchestration: chibi/backup/backup_service.py:50-75
- Table export methods: chibi/backup/sheets_exporter.py:167-223
- Metadata generation: chibi/backup/sheets_exporter.py:115-135
- Discord command handler: chibi/cogs/backup_cog.py:43-87

## Test Completion

Record your test results:
- Test Date: ___________
- Tester: ___________
- Bot Version/Commit: ___________
- Result: [ ] PASS [ ] FAIL
- Notes: ___________
