# Manual Testing Guide: MT-002 - Service Account Authentication

## Test ID: MT-002
**Title:** Test OAuth authentication with service account
**Priority:** 1 (Critical - Setup)
**Category:** Setup
**Prerequisites:** MT-001 passed (credentials verified)

---

## Objective
Verify that the Google Sheets client can successfully authenticate with the Google Sheets API using service account credentials (google-credential.json), without requiring browser-based OAuth flow.

---

## Background

The GoogleSheetsClient supports two authentication modes:

1. **OAuth 2.0 (User Credentials):** Requires browser flow, saves token to `credentials/token.json`
2. **Service Account:** Authenticates silently using `google-credential.json` (no browser required)

The credential type is automatically detected by examining the JSON file's `"type"` field.

**Service Account Detection** (see `chibi/backup/google_sheets_client.py:62-90`):
```python
def _detect_credential_type(self) -> str:
    with open(self.credentials_file, "r") as f:
        cred_data = json.load(f)
        cred_type = cred_data.get("type", "")

        if cred_type == "service_account":
            return "service_account"
        elif "installed" in cred_data or "web" in cred_data:
            return "oauth"
```

**Service Account Authentication** (see lines 106-113):
```python
if cred_type == "service_account":
    logger.info("Authenticating with service account")
    self.credentials = ServiceAccountCredentials.from_service_account_file(
        self.credentials_file, scopes=self.scopes
    )
    self._authorize_gspread()
    return
```

---

## Prerequisites Checklist

Before starting, verify:

- [ ] MT-001 passed (credentials file exists and is valid)
- [ ] `google-credential.json` has `"type": "service_account"`
- [ ] Google Sheets API enabled in Google Cloud Console
- [ ] Google Drive API enabled in Google Cloud Console
- [ ] Bot is running (`uv run python main.py`)
- [ ] You have admin permissions in the test Discord server

---

## Test Steps

### Step 1: Verify Google Cloud APIs are Enabled

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Select project: **chibi-learning-progress**
3. Navigate to **APIs & Services > Library**
4. Search for "Google Sheets API" and verify it's **ENABLED**
5. Search for "Google Drive API" and verify it's **ENABLED**

**Expected:** Both APIs show "Manage" button (indicating they're enabled)

**If not enabled:**
```bash
# Enable APIs using gcloud CLI (if available)
gcloud services enable sheets.googleapis.com --project=chibi-learning-progress
gcloud services enable drive.googleapis.com --project=chibi-learning-progress
```

Or enable manually in the Cloud Console.

---

### Step 2: Check Bot Startup Logs

1. Start the bot if not already running:
   ```bash
   uv run python main.py
   ```

2. Monitor the logs for BackupService initialization:
   ```
   INFO - BackupService initialized with credentials: google-credential.json
   INFO - BackupCog loaded
   ```

3. Verify no authentication errors during startup

**Expected:** Bot starts without errors, BackupService loads successfully

---

### Step 3: Run /export-progress Command

This is the critical test. The export command will trigger service account authentication.

1. Open Discord test server
2. In any channel where you have admin permissions, type:
   ```
   /export-progress
   ```

3. The bot will show "Thinking..." (this means it deferred the response)

4. Wait for the bot's response (typically 5-30 seconds depending on data size)

---

### Step 4: Analyze Bot Response

**Success Indicators:**

✅ Bot responds with an embed titled "Export Successful"
✅ Message includes a clickable Google Sheets link
✅ Message shows counts for each table (Users, QuizAttempts, etc.)
✅ NO authentication errors mentioned

**Example successful response:**
```
📊 Export Successful

Spreadsheet: Chibi Student Progress - 2026-01-12 14:30
Link: https://docs.google.com/spreadsheets/d/abc123...

Summary:
• Users: 3
• Quiz Attempts: 15
• Concept Mastery: 8
• LLM Quiz Attempts: 2
• Attendance: 5
```

**Failure Indicators:**

❌ Error message: "Authentication failed"
❌ Error message: "Permission denied"
❌ Error message: "API not enabled"
❌ Error message: "Invalid credentials"

---

### Step 5: Check Bot Logs for Authentication Details

While the export is running, monitor the terminal where the bot is running. Look for these log messages:

**Expected log sequence:**
```
INFO - Authenticating with service account
DEBUG - gspread client authorized
INFO - Created spreadsheet: Chibi Student Progress - 2026-01-12 14:30 (ID: abc123...)
INFO - Wrote 3 rows to Users
INFO - Wrote 15 rows to QuizAttempts
...
```

**Key verification:**
- ✅ "Authenticating with service account" appears (NOT "Starting OAuth flow")
- ✅ No browser window opens
- ✅ No errors about token.json or browser authentication

---

### Step 6: Verify No Browser OAuth Flow

**Critical check:** During the entire export process:

- [ ] NO browser window should open
- [ ] NO message about "Visit this URL to authenticate"
- [ ] NO creation of `credentials/token.json` file

**Verify:**
```bash
# This file should NOT exist after service account auth
ls credentials/token.json 2>/dev/null && echo "FAIL: OAuth token created" || echo "PASS: No OAuth token"
```

Expected output: `PASS: No OAuth token`

---

## Common Issues and Solutions

### Issue 1: "API not enabled"
**Error message:**
```
Google Sheets API has not been used in project chibi-learning-progress before or it is disabled.
```

**Solution:**
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Select project: chibi-learning-progress
3. Enable both Google Sheets API and Google Drive API
4. Wait 1-2 minutes for propagation
5. Retry /export-progress

---

### Issue 2: "Permission denied"
**Error message:**
```
The caller does not have permission
```

**Possible causes:**
- Service account doesn't have necessary IAM permissions
- APIs not enabled in the project

**Solution:**
1. Verify service account has "Editor" or "Owner" role in the project
2. Ensure APIs are enabled (see Step 1)
3. Check service account email in google-credential.json matches the one in IAM

---

### Issue 3: "Credential type detection failed"
**Error message:**
```
Unknown credential type in google-credential.json
```

**Solution:**
1. Verify the JSON file has `"type": "service_account"` field
2. Check the file is valid JSON:
   ```bash
   python -c 'import json; json.load(open("google-credential.json"))'
   ```
3. If file is corrupted, re-download from Google Cloud Console

---

### Issue 4: Export succeeds but can't access spreadsheet
**Symptom:** Export completes, but clicking link shows "Permission denied"

**Explanation:** Service accounts create files in their own Google Drive, which is separate from your personal Drive.

**Solution:**
This is expected behavior. To access the file:
1. Use the /list-exports command to see the file
2. Or, update the implementation to share the spreadsheet (future enhancement)

For this test, we only need to verify authentication succeeds (no errors). Accessing the file is covered in MT-003.

---

## Expected Outcome

### ✅ Test PASSES if:

1. Export command completes without authentication errors
2. Bot logs show "Authenticating with service account"
3. No browser OAuth flow is triggered
4. `credentials/token.json` is NOT created
5. Bot response indicates export succeeded (may not be able to access file yet)
6. Logs show spreadsheet was created with an ID

### ❌ Test FAILS if:

1. Authentication error occurs
2. Browser window opens (OAuth flow triggered)
3. Error about APIs not being enabled
4. Bot crashes or times out
5. Logs show OAuth-related messages instead of service account messages

---

## Notes for Test Documentation

When documenting your test results, include:

1. **Pass/Fail status**
2. **Bot log output** (authentication section)
3. **Discord bot response** (screenshot or text)
4. **Any errors encountered** and how you resolved them
5. **Time taken** for export to complete

---

## Cleanup

After testing, you may want to delete test exports to avoid cluttering Google Drive:

1. Use /list-exports to see recent exports
2. Manually delete test spreadsheets from the service account's Drive (requires Drive API access token)
3. Or leave them - they don't consume significant quota

---

## Next Steps

Once MT-002 passes:
- **MT-003:** Test full export with sample data and verify spreadsheet contents
- **MT-004:** Test export with empty database
- **MT-005:** Test export with large datasets

---

## References

- **Implementation:** `chibi/backup/google_sheets_client.py:62-113`
- **Service Account Docs:** https://cloud.google.com/iam/docs/service-accounts
- **Google Sheets API:** https://developers.google.com/sheets/api
- **gspread library:** https://docs.gspread.org/
