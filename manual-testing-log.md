# Manual Testing Log - Google Sheets Backup

## Test Environment
- **Date Started:** 2026-01-11
- **Tester:** Claude (Automated Manual Testing)
- **Environment:** macOS Darwin 24.6.0
- **Database:** data/chibi.db (90KB with existing data)
- **Credentials:** google-credential.json (service account)

---

## MT-000: Add service account support to GoogleSheetsClient
**Date:** 2026-01-11
**Status:** ✅ PASS

**Implementation completed:**
- Added service account credential detection and authentication
- Updated GoogleSheetsClient.authenticate() to handle both OAuth and service account
- Added _detect_credential_type() method
- All 17 unit tests pass including new test_service_account_authentication

**Results:**
- Code changes committed: ceb7b0e
- Ready to proceed with manual testing

---

## MT-001: Verify credentials and configuration
**Date:** 2026-01-11
**Status:** 🔄 IN PROGRESS

**Steps executed:**

### 1. Check google-credential.json file exists
```bash
$ ls -la google-credential.json
-rw-r--r--  1 skojaku-admin  staff  2334 Jan 10 17:00 google-credential.json
```
✅ File exists

### 2. Verify file contains valid service account JSON
```bash
$ cat google-credential.json | python3 -m json.tool | head -5
{
    "type": "service_account",
    "project_id": "chibi-learning-progress",
    "private_key_id": "01a48dc15fa6de3779119e8eccf048d6c6152551",
    "private_key": "-----BEGIN PRIVATE KEY-----\n...",
```
✅ Valid service account JSON

### 3. Confirm project_id is 'chibi-learning-progress'
✅ Confirmed: project_id is "chibi-learning-progress"

### 4. Check client_email is 'quiz-bot@chibi-learning-progress.iam.gserviceaccount.com'
✅ Confirmed: client_email is "quiz-bot@chibi-learning-progress.iam.gserviceaccount.com"

### 5. Verify config.yaml has backup.google_sheets.credentials_file pointing to correct path
```yaml
backup:
  google_sheets:
    credentials_file: "google-credential.json"
```
✅ Configuration correct

### 6. Start bot with 'uv run python main.py'
**Action Required:** This step requires user interaction - bot must be started manually in Discord test server

**Instructions for user:**
1. Open terminal
2. Navigate to project directory
3. Run: `uv run python main.py`
4. Observe bot startup logs
5. Verify no errors during initialization
6. Check Discord - bot should appear online

### 7. Verify bot loads without errors
⏳ **Waiting for user to start bot and confirm**

### 8. Confirm backup cog is loaded
⏳ **Waiting for bot startup - check logs or use /help command in Discord**

---

## Summary - MT-001 Status
**Current Status:** 🔄 PARTIALLY COMPLETE

**Completed Checks:**
- ✅ google-credential.json exists and is valid
- ✅ project_id correct: chibi-learning-progress
- ✅ client_email correct: quiz-bot@chibi-learning-progress.iam.gserviceaccount.com
- ✅ config.yaml properly configured
- ✅ Database has test data (1 user, 2 quiz attempts)

**Pending Actions (Requires User):**
- ⏳ Start bot with `uv run python main.py`
- ⏳ Verify bot loads without errors
- ⏳ Confirm backup commands available: /export-progress, /import-progress, /list-exports

**Next Test:** MT-002 (Test OAuth authentication with service account)

---

## 🎯 USER ACTION REQUIRED: Complete MT-001 and Begin MT-002

### Quick Start Instructions

To complete MT-001 and start MT-002, you need to:

1. **Start the bot:**
   ```bash
   cd /Users/skojaku-admin/Documents/projects/applied-soft-comp/tutor/discord-qa-agent
   uv run python main.py
   ```

2. **Watch for startup logs:**
   - Look for: `"Cogs loaded"` (confirms backup_cog loaded at line 336)
   - Look for: `"Commands synced"` (confirms Discord slash commands registered)
   - Bot should appear **online** in Discord

3. **Test in Discord (as admin user):**
   ```
   /export-progress
   ```

   This single command will:
   - ✅ Complete MT-001 (verify backup cog loads)
   - ✅ Complete MT-002 (test service account authentication)
   - ✅ Complete MT-003 (basic export with sample data)

### Expected Results

**Success Response:**
- Discord embed with:
  - ✅ Title: "Export Successful"
  - 📊 Statistics: Users: 1, Quiz Attempts: 2, Concept Mastery: 7
  - 🔗 Clickable Google Sheets link

**What This Tests:**
- ✅ Bot starts without errors (MT-001)
- ✅ Backup cog loaded successfully (MT-001)
- ✅ Service account authenticates silently (MT-002)
- ✅ Export creates spreadsheet (MT-003)
- ✅ Data exported correctly (MT-003)

### Error Scenarios

**If authentication fails:**
- Check Google Cloud Console: APIs enabled?
  - Google Sheets API
  - Google Drive API
- Check service account permissions
- Check credentials file path in config.yaml

**If bot doesn't start:**
- Check `.env` file has `DISCORD_TOKEN`
- Check database path: `data/chibi.db` exists
- Check Python environment: `uv` installed

### After Export Success

1. **Click the Google Sheets link**
2. **Verify 6 sheets exist:**
   - Metadata
   - Users
   - QuizAttempts
   - ConceptMastery
   - LLMQuizAttempts
   - Attendance

3. **Check Metadata sheet:**
   - export_date: Should be today (2026-01-11)
   - schema_version: Should be "1.0"
   - users_count: Should be 1
   - quiz_attempts_count: Should be 2
   - concept_mastery_count: Should be 7

4. **Copy the spreadsheet URL** - you'll need it for import tests (MT-006 onwards)

---

## MT-002: Test OAuth authentication with service account
**Date:** 2026-01-11
**Status:** ⏳ PENDING (Will be tested during first /export-progress)

**Note:** Service account authentication happens silently during export. No browser popup should occur.

---
