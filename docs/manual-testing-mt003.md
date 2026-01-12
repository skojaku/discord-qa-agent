# Manual Testing Guide: MT-003 - Basic Export with Sample Data

## Test ID: MT-003
**Title:** Basic export with sample data
**Priority:** 2 (Core Functionality - Export)
**Category:** Export
**Prerequisites:** MT-002 passed (service account authentication verified)

---

## Objective

Verify that the `/export-progress` command successfully exports student progress data from the SQLite database to Google Sheets with proper formatting, correct data types, and accurate counts.

---

## Background

The export feature creates a Google Spreadsheet with 6 sheets:
1. **Metadata** - Export metadata (date, schema version, table counts)
2. **Users** - User account information
3. **QuizAttempts** - Quiz question attempts and results
4. **ConceptMastery** - Learning progress tracking per concept
5. **LLMQuizAttempts** - "Stump the AI" challenge attempts
6. **Attendance** - Class attendance records

**Implementation details:**
- Exporter: `chibi/backup/sheets_exporter.py`
- Data transformations: NULL→"", 0/1→"TRUE"/"FALSE", text truncation to 50k chars
- Spreadsheet naming: "Chibi Student Progress - YYYY-MM-DD HH:MM"
- See `DATABASE_STRUCTURE.md` for complete schema

---

## Prerequisites Checklist

Before starting:

- [ ] MT-002 passed (service account authentication working)
- [ ] Bot is running (`uv run python main.py`)
- [ ] You have admin permissions in the test Discord server
- [ ] Database has sample data (at least 1 user with quiz attempts)
- [ ] You have access to sqlite3 command-line tool for verification

---

## Part 1: Prepare Sample Data

### Step 1: Check Existing Data

Check if the database already has sample data:

```bash
sqlite3 data/chibi.db "SELECT COUNT(*) as user_count FROM users;"
sqlite3 data/chibi.db "SELECT COUNT(*) as quiz_count FROM quiz_attempts;"
```

**Expected:**
- If counts are > 0, you can proceed to Part 2
- If counts are 0, follow Step 2 to create sample data

---

### Step 2: Create Sample Data (if needed)

If database is empty, create sample data by taking quizzes in Discord:

1. In Discord, interact with the bot via DM or mention
2. Request a quiz:
   ```
   @ChibiBot I'd like to take a quiz
   ```

3. Complete 2-3 quiz questions, providing answers

4. (Optional) Take quizzes as multiple different users for richer test data

5. Verify data was created:
   ```bash
   sqlite3 data/chibi.db "SELECT id, username, discord_id FROM users;"
   sqlite3 data/chibi.db "SELECT id, user_id, question, is_correct FROM quiz_attempts LIMIT 5;"
   ```

**Expected output:**
- At least 1 user record
- At least 2-3 quiz attempt records linked to that user

---

### Step 3: Record Baseline Counts

Before export, record the current database counts for later verification:

```bash
sqlite3 data/chibi.db <<EOF
SELECT 'Users: ' || COUNT(*) FROM users;
SELECT 'Quiz Attempts: ' || COUNT(*) FROM quiz_attempts;
SELECT 'Concept Mastery: ' || COUNT(*) FROM concept_mastery;
SELECT 'LLM Quiz Attempts: ' || COUNT(*) FROM llm_quiz_attempts;
SELECT 'Attendance: ' || COUNT(*) FROM attendance;
EOF
```

**Save these counts** - you'll compare them to the Metadata sheet later.

Example output:
```
Users: 3
Quiz Attempts: 15
Concept Mastery: 8
LLM Quiz Attempts: 2
Attendance: 0
```

---

## Part 2: Execute Export

### Step 4: Run Export Command

1. Open Discord and navigate to your test server
2. In any channel where you have admin permissions, type:
   ```
   /export-progress
   ```

3. The bot will show "Thinking..." indicator

4. Wait for the export to complete (typically 5-30 seconds depending on data size)

---

### Step 5: Analyze Bot Response

**Success Response Should Include:**

✅ Embed with title "📊 Export Successful" or similar
✅ Spreadsheet name: "Chibi Student Progress - YYYY-MM-DD HH:MM"
✅ Clickable Google Sheets link
✅ Summary showing counts for each table

**Example successful response:**
```
📊 Export Successful

Spreadsheet: Chibi Student Progress - 2026-01-12 15:45
🔗 Open Spreadsheet

Summary:
• Users: 3
• Quiz Attempts: 15
• Concept Mastery: 8
• LLM Quiz Attempts: 2
• Attendance: 0
```

**If you see an error:**
- Check bot logs for detailed error message
- Common issues: API quota exceeded, permissions error, database locked
- See Troubleshooting section below

---

### Step 6: Check Bot Logs

While the export was running, the bot terminal should have logged:

```
INFO - Authenticating with service account
INFO - Created spreadsheet: Chibi Student Progress - 2026-01-12 15:45 (ID: 1abc...)
INFO - Wrote 8 rows to Metadata
INFO - Wrote 4 rows to Users (3 data + 1 header)
INFO - Wrote 16 rows to QuizAttempts (15 data + 1 header)
INFO - Wrote 9 rows to ConceptMastery (8 data + 1 header)
INFO - Wrote 3 rows to LLMQuizAttempts (2 data + 1 header)
INFO - Wrote 1 rows to Attendance (0 data + 1 header)
```

**Verify:**
- ✅ No authentication errors
- ✅ Spreadsheet creation logged
- ✅ All 6 sheets written
- ✅ Row counts match your baseline + 1 for headers

---

## Part 3: Verify Spreadsheet Contents

**Note:** Service accounts create files in their own Google Drive space. You may not be able to access the spreadsheet directly through the link unless the bot implementation shares it with you. For this test, we'll verify based on the bot's response and logs. Future enhancements may add automatic sharing.

If you have access to the service account's Drive (via impersonation or shared access):

### Step 7: Open the Spreadsheet

1. Click the Google Sheets link from the bot's response
2. The spreadsheet should open in your browser

**If you get "Permission denied":**
- This is expected for service accounts (they have their own isolated Drive)
- The export itself succeeded - verification via logs is sufficient for this test
- See "Service Account Drive Access" in Troubleshooting section

---

### Step 8: Verify Sheet Structure (if accessible)

Check that all 6 sheets exist with correct names:

1. **Metadata** - First sheet, 8 rows with export info
2. **Users** - User data with columns: id, discord_id, username, student_id, student_name, created_at, last_active
3. **QuizAttempts** - Quiz data with columns: id, user_id, module_id, concept_id, quiz_format, question, user_answer, correct_answer, is_correct, llm_feedback, llm_quality_score, created_at
4. **ConceptMastery** - Mastery tracking: id, user_id, concept_id, total_attempts, correct_attempts, avg_quality_score, mastery_level, last_attempt_at, updated_at
5. **LLMQuizAttempts** - LLM challenges: id, user_id, module_id, question, student_answer, llm_answer, student_wins, student_answer_correctness, evaluation_explanation, review_status, reviewed_at, reviewed_by, discord_user_id, created_at
6. **Attendance** - Attendance records: id, user_id, username, timestamp, date_id, session_id, status

---

### Step 9: Verify Metadata Sheet (if accessible)

The Metadata sheet should have 8 rows:

| Key | Value |
|-----|-------|
| export_date | 2026-01-12 15:45:23 |
| schema_version | 1.0 |
| users_count | 3 |
| quiz_attempts_count | 15 |
| concept_mastery_count | 8 |
| llm_quiz_attempts_count | 2 |
| attendance_count | 0 |
| notes | Exported by Chibi backup system |

**Verify:**
- ✅ export_date matches current date/time
- ✅ Counts match your baseline from Step 3
- ✅ schema_version is present

---

### Step 10: Verify Data Types (if accessible)

Check that data transformations were applied correctly:

**Boolean columns (is_correct, student_wins):**
- Should display as "TRUE" or "FALSE" (not 1/0)

**NULL values:**
- Should display as empty cells (not the text "NULL")

**Timestamps:**
- Should be ISO format: "2026-01-12 15:45:23"

**Long text fields:**
- Question text, llm_feedback should be present
- Truncated to 50,000 chars if longer (unlikely in test data)

**Example QuizAttempts row:**
| id | user_id | module_id | concept_id | question | user_answer | is_correct |
|----|---------|-----------|------------|----------|-------------|------------|
| 1 | 123 | module01 | graph_basics | What is a node? | A vertex in the graph | TRUE |

---

### Step 11: Verify Row Counts Match (if accessible)

Count actual rows in each sheet and compare to Metadata:

**Formula for verification:**
- Users sheet: (row count - 1) should equal users_count in Metadata
- QuizAttempts: (row count - 1) should equal quiz_attempts_count
- Etc. (subtract 1 for header row)

**Use spreadsheet row indicators** on the left side to check total rows.

---

## Expected Test Results

### ✅ Test PASSES if:

**Part 1 - Data Preparation:**
1. Sample data exists in database (at least 1 user, 2+ quiz attempts)
2. Baseline counts recorded

**Part 2 - Export Execution:**
3. Export command completes without errors
4. Bot response shows success with summary counts
5. Google Sheets link provided
6. Bot logs show successful spreadsheet creation
7. Bot logs show all 6 sheets written

**Part 3 - Spreadsheet Verification (if accessible):**
8. Spreadsheet named "Chibi Student Progress - YYYY-MM-DD HH:MM"
9. All 6 sheets present with correct names
10. Metadata sheet has accurate counts matching baseline
11. Data types properly formatted (TRUE/FALSE, empty cells, timestamps)
12. Row counts in sheets match Metadata counts

**Minimum passing criteria** (without Drive access):
- Items 1-7 above must pass
- Items 8-12 can be verified via logs and bot response

---

### ❌ Test FAILS if:

1. Export command returns error
2. Bot crashes or times out
3. Spreadsheet not created (no ID in logs)
4. Any of the 6 sheets missing
5. Row counts in Metadata don't match database baseline
6. Data type conversions incorrect (1/0 instead of TRUE/FALSE, etc.)
7. Bot logs show errors or exceptions

---

## Troubleshooting

### Issue 1: "Export failed - Database locked"

**Cause:** Another process has the database file open

**Solution:**
```bash
# Check for processes using the database
lsof data/chibi.db

# Stop the bot
# Run export again
```

---

### Issue 2: "API quota exceeded"

**Error message:**
```
Quota exceeded for quota metric 'Write requests' and limit 'Write requests per minute per user'
```

**Solution:**
- Wait 60 seconds
- Retry export
- If persistent, check Google Cloud Console quota limits

---

### Issue 3: Service Account Drive Access

**Problem:** Can't access the exported spreadsheet via link

**Explanation:**
Service accounts have their own Google Drive that's separate from your personal Drive. Files created by the service account are in its Drive, not yours.

**Current behavior (expected):**
- Export succeeds (verified by bot logs)
- Spreadsheet created (ID logged)
- Link provided but you can't access it (permission denied)

**Future enhancement:**
- Implement automatic sharing: After export, share spreadsheet with specific Google accounts
- Or: Use domain-wide delegation to access service account's Drive
- Or: Export to your personal Drive using OAuth user credentials instead

**For this test:**
- ✅ Export success verified by logs is sufficient
- ✅ Spreadsheet ID in logs confirms creation
- ✅ No access to view spreadsheet is OK for now

**Workaround (for developers):**
If you need to verify spreadsheet contents, you can:
1. Add Google account email to service account's sharing permissions via API
2. Implement `/share-export` command that shares the spreadsheet
3. Use the service account key to impersonate and access Drive programmatically

---

### Issue 4: Empty database - no data to export

**Symptom:** All counts are 0 in bot response

**Solution:**
- This is OK for MT-003, proceed to MT-004 (Empty Database Export)
- Or create sample data following Part 1, Step 2

---

### Issue 5: Row count mismatch between database and Metadata

**Symptom:** Baseline counts don't match Metadata sheet counts

**Possible causes:**
- Data was added/deleted between baseline check and export
- Export partially failed (some tables not exported)

**Solution:**
1. Check bot logs for errors
2. Re-run baseline query immediately before export
3. Verify all tables show successful writes in logs

---

## Data Verification Commands

### Quick Database Inspection

```bash
# View all table names
sqlite3 data/chibi.db ".tables"

# View schema for a table
sqlite3 data/chibi.db ".schema users"

# Sample data from each table
sqlite3 data/chibi.db "SELECT * FROM users LIMIT 3;"
sqlite3 data/chibi.db "SELECT id, question, is_correct FROM quiz_attempts LIMIT 5;"
sqlite3 data/chibi.db "SELECT user_id, concept_id, mastery_level FROM concept_mastery LIMIT 5;"
```

### Data Type Verification

```bash
# Check for boolean values (should be 0 or 1)
sqlite3 data/chibi.db "SELECT DISTINCT is_correct FROM quiz_attempts;"
# Expected: 0 and 1

# Check for NULL values in optional columns
sqlite3 data/chibi.db "SELECT COUNT(*) FROM users WHERE student_id IS NULL;"
# Expected: Some count (NULL is valid for this column)

# Check timestamp format
sqlite3 data/chibi.db "SELECT created_at FROM users LIMIT 1;"
# Expected: YYYY-MM-DD HH:MM:SS format
```

---

## Cleanup

After testing:

1. **Keep test data** if you want to run MT-004 through MT-013
2. **Or delete test exports** to avoid cluttering Google Drive:
   - Use `/list-exports` to see all exports
   - Manually delete via Google Drive API or Cloud Console
   - No Discord command for deletion yet (future enhancement)

3. **Backup test database** if you created rich sample data:
   ```bash
   cp data/chibi.db data/chibi-test-backup.db
   ```

---

## Next Steps

After MT-003 passes:
- **MT-004:** Test export with empty database (edge case)
- **MT-005:** Test export with large datasets (performance)
- **MT-006:** Test import functionality (restore data)

---

## References

- **Export Implementation:** `chibi/backup/sheets_exporter.py`
- **Data Transformations:** `sheets_exporter.py:_transform_row()` method
- **Database Schema:** `DATABASE_STRUCTURE.md`
- **Google Sheets API:** https://developers.google.com/sheets/api
- **Service Account Docs:** https://cloud.google.com/iam/docs/service-accounts
