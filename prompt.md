# Manual E2E Testing: Google Sheets Backup Feature

You are conducting manual end-to-end testing of the Google Sheets backup feature using **real Google Sheets API credentials**. This tests the actual integration with Google's services, not mocks.

## Your Mission

Verify the backup feature works correctly with real Google Sheets by completing manual test scenarios in order. Each test validates a different aspect of the backup system.

## Prerequisites

Before starting, ensure:
- ✅ Bot is fully implemented (US-001 through US-014 complete)
- ✅ `google-credentials.json` exists in project root (service account credentials)
- ✅ Google Sheets API and Drive API are enabled for the project
- ✅ Bot has access to test Discord server
- ✅ Test user has administrator permissions in Discord

## Critical Files

**manual-testing-prd.json** - Your test scenario list with pass/fail status

**DATABASE_STRUCTURE.md** - Database schema reference for verifying data

**data/chibi.db** - SQLite database to backup/restore

**google-credentials.json** - Service account credentials for Google Sheets API

## Test Environment Setup

### 1. Prepare Test Data

Create sample data in the database:
```bash
# Start the bot
uv run python main.py

# In Discord, as admin user:
# 1. Register a test student: !register_student <discord_user> <student_id> <name>
# 2. Take 2-3 quizzes: /quiz
# 3. Check status: /status
# 4. Verify data exists in database
```

### 2. Verify Test Data

Check the database has data to export:
```bash
sqlite3 data/chibi.db "SELECT COUNT(*) FROM users;"
sqlite3 data/chibi.db "SELECT COUNT(*) FROM quiz_attempts;"
sqlite3 data/chibi.db "SELECT COUNT(*) FROM concept_mastery;"
```

You should have at least 1 user and several quiz attempts.

## Test Execution Workflow

### For Each Test Scenario

1. **Read Scenario**
   - Read `manual-testing-prd.json` to find next test (passes: false)
   - Note the test ID, description, and steps

2. **Execute Test Steps**
   - Follow steps exactly as written
   - Use real Discord commands (not code)
   - Interact with actual Google Sheets in browser
   - Document any issues encountered

3. **Verify Expected Outcomes**
   - Check all acceptance criteria are met
   - Compare actual vs expected results
   - Verify data integrity (counts, content, types)

4. **Record Results**
   - If ALL criteria pass: Update `manual-testing-prd.json` with `"passes": true`
   - If ANY criteria fail: Document failure, leave `"passes": false`, add notes
   - Append findings to `manual-testing-log.md`

5. **Check Completion**
   - If all scenarios pass: Testing complete ✅
   - If scenarios remain: Continue to next test

## Test Data Validation

### Database Queries for Verification

Check data before and after operations:

```bash
# Count records per table
sqlite3 data/chibi.db <<EOF
SELECT 'users' as table_name, COUNT(*) as count FROM users
UNION ALL
SELECT 'quiz_attempts', COUNT(*) FROM quiz_attempts
UNION ALL
SELECT 'concept_mastery', COUNT(*) FROM concept_mastery
UNION ALL
SELECT 'llm_quiz_attempts', COUNT(*) FROM llm_quiz_attempts
UNION ALL
SELECT 'attendance', COUNT(*) FROM attendance;
EOF

# Check specific user data
sqlite3 data/chibi.db "SELECT * FROM users WHERE discord_id='<discord_id>';"

# Check foreign key relationships
sqlite3 data/chibi.db "SELECT u.username, COUNT(q.id) FROM users u LEFT JOIN quiz_attempts q ON u.id = q.user_id GROUP BY u.id;"
```

### Google Sheets Validation

Open exported spreadsheet and verify:
- **Metadata sheet** has correct export date and counts
- **Users sheet** has all user records with correct columns
- **QuizAttempts sheet** has quiz data with proper formatting
- **ConceptMastery sheet** has mastery tracking data
- **LLMQuizAttempts sheet** has challenge game data (if any)
- **Attendance sheet** has attendance records (if any)

Data type conversions to verify:
- NULL → empty cell
- TRUE/FALSE → actual TRUE/FALSE values
- Timestamps → readable ISO format
- Long text → no truncation (unless >50k chars)

## Test Scenarios Overview

**Setup Tests (MT-001 to MT-002):**
- Verify credentials and bot configuration
- Test OAuth authentication flow

**Export Tests (MT-003 to MT-005):**
- Basic export with sample data
- Export with empty database
- Export with large dataset

**Import Tests (MT-006 to MT-009):**
- Import to clean database (replace mode)
- Import to existing database (merge mode)
- Import with schema validation
- Import error handling

**List Tests (MT-010):**
- List recent exports from Drive

**Cross-Machine Tests (MT-011):**
- Export from one machine, import on another

**Data Integrity Tests (MT-012 to MT-013):**
- Verify data types preserved
- Verify referential integrity maintained

## Recording Test Results

Create `manual-testing-log.md` with this format:

```markdown
# Manual Testing Log - Google Sheets Backup

## MT-001: Verify credentials
**Date:** 2026-01-11 15:30
**Tester:** [Your name]
**Status:** ✅ PASS

**Steps executed:**
1. Checked google-credentials.json exists: ✓
2. Verified file contains service_account type: ✓
3. Confirmed project_id is chibi-learning-progress: ✓

**Results:**
- All credentials valid
- No issues encountered

**Screenshots:** [If applicable]

---

## MT-002: Test OAuth authentication
**Date:** 2026-01-11 15:35
**Tester:** [Your name]
**Status:** ❌ FAIL

**Steps executed:**
1. Started bot: ✓
2. Bot loaded backup cog: ✓
3. Ran /export-progress: ✗ Error

**Error encountered:**
```
google.auth.exceptions.DefaultCredentialsError: Could not load credentials
```

**Root cause:**
Service account credentials not properly configured in config.yaml

**Resolution:**
Updated config.yaml with correct credentials_file path

**Retry:** Passed on second attempt ✅

---
```

## Common Issues and Troubleshooting

### Authentication Errors

**Problem:** `DefaultCredentialsError` or `RefreshError`
- **Check:** credentials file path in config.yaml
- **Check:** credentials file is valid JSON
- **Check:** Service account has necessary permissions
- **Fix:** Verify GOOGLE_APPLICATION_CREDENTIALS or use explicit credentials_file

### API Errors

**Problem:** `429 Rate Limit Exceeded`
- **Cause:** Too many API requests in short time
- **Fix:** Wait 60 seconds, then retry
- **Prevention:** Reduce test frequency

**Problem:** `403 Permission Denied`
- **Cause:** Service account lacks permissions
- **Fix:** Share spreadsheets with service account email
- **Fix:** Enable APIs in Google Cloud Console

### Data Issues

**Problem:** Missing data after import
- **Check:** Schema validation passed
- **Check:** Transaction completed without errors
- **Check:** Foreign key relationships maintained
- **Debug:** Query database directly with sqlite3

**Problem:** Wrong data types after import
- **Check:** TRUE/FALSE converted to 1/0
- **Check:** Empty cells converted to NULL
- **Debug:** Compare exported sheet with database

## Test Completion Criteria

Testing is complete when:
- ✅ All scenarios in `manual-testing-prd.json` have `"passes": true`
- ✅ All acceptance criteria met for each scenario
- ✅ `manual-testing-log.md` documents all test executions
- ✅ No critical bugs remain unresolved
- ✅ Feature ready for production use

## Safety Notes

**Important:**
- Use test database, not production data
- Keep backup of `data/chibi.db` before destructive tests
- Test in isolated Discord server (not production)
- Service account credentials are for testing only
- Delete test spreadsheets after testing to avoid quota issues

## Commands Reference

```bash
# Start bot
uv run python main.py

# Backup database before testing
cp data/chibi.db data/chibi.db.backup

# Restore database if needed
cp data/chibi.db.backup data/chibi.db

# Check database
sqlite3 data/chibi.db ".schema"
sqlite3 data/chibi.db "SELECT COUNT(*) FROM users;"

# View logs
tail -f logs/chibi.log  # If logging configured
```

## Discord Commands

```
# Admin commands (require administrator permission)
/export-progress                          # Export all data to Google Sheets
/import-progress <url> [mode]             # Import from Sheets (replace/merge)
/list-exports [limit]                     # List recent exports (default 10)

# Regular commands (for creating test data)
/quiz                                     # Take a quiz
/status                                   # View progress
/llm-quiz                                 # Try LLM challenge
```

---

Now, read `manual-testing-prd.json` and execute test scenarios in order. Document all results in `manual-testing-log.md`.
