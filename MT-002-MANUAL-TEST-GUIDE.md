# MT-002 Manual Test Guide: Service Account Authentication

## Prerequisites (from MT-001)
- ✓ google-credential.json exists in project root
- ✓ config.yaml points to google-credential.json
- ✓ Bot starts without errors
- ✓ All 118 automated tests pass

## What This Test Verifies

This test confirms that:
1. Service account authentication works with real Google Sheets API
2. Authentication happens silently (no browser OAuth flow)
3. Bot can successfully connect to Google Sheets API

## Steps to Execute

### 1. Ensure Google Cloud Project Configuration

Before running the bot, verify your Google Cloud project has the required APIs enabled:

```bash
# Check if Google Sheets API is enabled for your project
# You should see "Google Sheets API" listed in the Google Cloud Console:
# https://console.cloud.google.com/apis/library?project=chibi-learning-progress
```

**Required APIs:**
- Google Sheets API
- Google Drive API

If not enabled, enable them at:
- https://console.cloud.google.com/apis/library/sheets.googleapis.com
- https://console.cloud.google.com/apis/library/drive.googleapis.com

### 2. Start the Bot

```bash
# Start the bot in your terminal
uv run python main.py
```

**Expected output:**
```
[INFO] Loaded cog: chibi.cogs.backup_cog
[INFO] BackupService initialized
[INFO] ChibiBot is ready!
```

### 3. Run the Export Command in Discord

In your test Discord server (where you have admin permissions):

```
/export-progress
```

**What to Observe:**

1. **Bot Response Time:** The bot should respond within 5-10 seconds with a "thinking" indicator

2. **No Browser Popup:** Unlike OAuth user credentials, service account authentication should NOT open a browser window or ask you to log in

3. **Success or Error Message:** The bot should respond with either:
   - **Success:** A message containing a Google Sheets link
   - **Error:** A clear error message explaining what went wrong

### 4. Expected Outcomes

#### ✅ Success Case
If authentication works, you should see a response like:
```
✓ Progress Exported Successfully
Created spreadsheet: Chibi Student Progress - 2026-01-11 15:30

📊 Export Summary:
• Users: 0
• Quiz Attempts: 0
• Concept Mastery: 0
• LLM Quiz Attempts: 0
• Attendance: 0

🔗 View Spreadsheet: [link to Google Sheets]
```

*Note: Counts may be 0 if your database is empty (this is OK for MT-002)*

#### ❌ Common Error Cases

**Error 1: Permission Denied**
```
Authentication failed: 403 Permission denied
```
**Solution:** The service account email (quiz-bot@chibi-learning-progress.iam.gserviceaccount.com) needs Google Sheets API access. Check Google Cloud Console permissions.

**Error 2: API Not Enabled**
```
Google Sheets API has not been used in project chibi-learning-progress
```
**Solution:** Enable Google Sheets API at https://console.cloud.google.com/apis/library/sheets.googleapis.com?project=chibi-learning-progress

**Error 3: Invalid Credentials**
```
Could not automatically determine credentials
```
**Solution:** Verify google-credential.json is valid JSON with type: "service_account"

### 5. Verify Authentication Logs

Check the bot's terminal output for authentication details:

```bash
# Look for this log message (confirms service account auth)
[INFO] Authenticating with service account

# Should NOT see (this would indicate OAuth user flow)
[INFO] Starting OAuth flow (browser authentication required)
```

### 6. Verification Checklist

- [ ] Bot started without errors
- [ ] `/export-progress` command executed
- [ ] No browser popup appeared (silent authentication)
- [ ] Bot responded within 30 seconds
- [ ] Either success message with spreadsheet link OR clear error message
- [ ] Terminal logs show "Authenticating with service account"

## MT-002 Pass Criteria

**PASS if:**
1. ✓ No authentication errors
2. ✓ Service account authenticates silently (no browser)
3. ✓ Bot can access Google Sheets API
4. ✓ Export command proceeds (empty DB is OK for this test)

**FAIL if:**
1. ✗ Browser OAuth popup appears
2. ✗ Authentication errors prevent export
3. ✗ Bot crashes or hangs

## Next Steps

- **If MT-002 PASSES:** Proceed to MT-003 (Basic export with sample data)
- **If MT-002 FAILS:** Debug using error messages and Google Cloud Console

## Troubleshooting

### Issue: "credentials file not found"
- Verify: `ls -la google-credential.json`
- Check config.yaml points to correct path

### Issue: "Invalid JSON in credentials file"
- Verify: `python -c "import json; json.load(open('google-credential.json'))"`
- Check file is valid service account JSON

### Issue: "Permission denied" or "403 Forbidden"
- Verify APIs are enabled in Google Cloud Console
- Check service account has proper permissions

### Issue: Bot doesn't respond to /export-progress
- Verify you have admin permissions in Discord server
- Check bot has proper Discord permissions
- Restart bot and try again
