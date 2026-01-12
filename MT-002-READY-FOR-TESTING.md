# MT-002: Ready for Manual Testing

## Summary

The implementation for **MT-002: Test OAuth authentication with service account** is complete and ready for manual testing. All automated tests pass (73/73 backup tests).

## What Was Verified

### ✅ Automated Testing (Complete)
1. **Service Account Detection** - GoogleSheetsClient correctly detects service account credentials
2. **Authentication Logic** - Service account flow bypasses OAuth browser flow
3. **API Integration** - All CRUD operations work with mocked Google Sheets API
4. **Error Handling** - Proper error handling for auth failures

### 📋 Manual Testing (Pending - MT-002)
The following needs to be tested with **real Google Sheets API**:

1. Bot starts without errors with service account credentials
2. `/export-progress` command executes without browser popup
3. Service account authenticates silently
4. Export either succeeds or fails with clear error message
5. Google Sheets API connection is established

## Implementation Status

### Code Complete ✅
- `chibi/backup/google_sheets_client.py` - Service account support (lines 106-113)
- `chibi/backup/backup_service.py` - BackupService orchestration
- `chibi/cogs/backup_cog.py` - Discord slash commands
- `chibi/bot.py` - Integration with bot

### Configuration Complete ✅
- `config.yaml` points to `google-credential.json`
- `google-credential.json` exists with valid service account credentials:
  - type: service_account
  - project_id: chibi-learning-progress
  - client_email: quiz-bot@chibi-learning-progress.iam.gserviceaccount.com

### Tests Complete ✅
All 73 backup tests pass:
- 17 GoogleSheetsClient tests (including service account auth)
- 16 SheetsExporter tests
- 18 SheetsImporter tests
- 22 BackupService tests

## How to Run MT-002

See **MT-002-MANUAL-TEST-GUIDE.md** for step-by-step instructions.

### Quick Start:

1. **Enable APIs** (if not already done):
   - Google Sheets API: https://console.cloud.google.com/apis/library/sheets.googleapis.com?project=chibi-learning-progress
   - Google Drive API: https://console.cloud.google.com/apis/library/drive.googleapis.com?project=chibi-learning-progress

2. **Start the bot**:
   ```bash
   uv run python main.py
   ```

3. **Run command in Discord**:
   ```
   /export-progress
   ```

4. **Verify**:
   - No browser popup appears (service account = silent auth)
   - Bot responds within 30 seconds
   - Success message with spreadsheet link OR clear error message

## Expected Outcomes

### Success Case ✅
```
✓ Progress Exported Successfully
Created spreadsheet: Chibi Student Progress - 2026-01-11 15:30

📊 Export Summary:
• Users: 0
• Quiz Attempts: 0
...

🔗 View Spreadsheet: [link]
```

### Common Errors (with solutions)

**API Not Enabled:**
```
Error: Google Sheets API has not been used in project
```
→ Enable at https://console.cloud.google.com/apis/library/sheets.googleapis.com

**Permission Denied:**
```
Error: 403 Permission denied
```
→ Check service account has Google Sheets API access in Google Cloud Console

## Why MT-002 is Important

This test verifies:
1. **Silent Authentication** - Service accounts don't require browser-based OAuth (critical for automated backups)
2. **Real API Connection** - Automated tests use mocks; this tests real Google Sheets API
3. **Deployment Readiness** - Confirms the bot can connect to Google services in production

## After MT-002 Passes

The next test is **MT-003: Basic export with sample data**, which will test the full export workflow with real data.

## Troubleshooting

If MT-002 fails, check:
1. Google Sheets API is enabled
2. Google Drive API is enabled
3. Service account exists in Google Cloud Console
4. `google-credential.json` is valid JSON
5. Bot has Discord permissions

Full troubleshooting guide in **MT-002-MANUAL-TEST-GUIDE.md**.

## Files Created for MT-002

- `MT-002-MANUAL-TEST-GUIDE.md` - Detailed step-by-step testing instructions
- `MT-002-READY-FOR-TESTING.md` - This file (summary and status)

## Technical Details

The service account authentication flow (google_sheets_client.py:106-113):
```python
if cred_type == "service_account":
    logger.info("Authenticating with service account")
    self.credentials = ServiceAccountCredentials.from_service_account_file(
        self.credentials_file, scopes=self.scopes
    )
    self._authorize_gspread()
    return
```

This bypasses the OAuth browser flow entirely, using the service account JSON directly for authentication.
