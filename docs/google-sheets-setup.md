# Google Sheets Backup & Export Setup

Export and import student progress data to/from Google Sheets for backup, grading, or cross-machine transfer. All exports are saved to **your personal Google Drive** in an organized folder.

## Quick Reference

### Commands

- **`/export-progress`** - Export all student data to a new Google Sheets spreadsheet
- **`/import-progress <url> [mode]`** - Import data from a Google Sheets backup
  - **Replace mode**: Deletes all existing data before importing (requires confirmation)
  - **Merge mode**: Updates existing records and adds new ones
- **`/list-exports [limit]`** - List recent exports with clickable links

### What Gets Exported

- User profiles (Discord ID, student ID, name)
- Quiz attempts and responses with LLM evaluations
- Concept mastery tracking
- LLM Quiz Challenge attempts
- Attendance records

---

## One-Time Setup

### Step 1: Enable Google APIs

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or select existing)
3. Enable the following APIs:
   - [Google Sheets API](https://console.cloud.google.com/apis/library/sheets.googleapis.com)
   - [Google Drive API](https://console.cloud.google.com/apis/library/drive.googleapis.com)
4. Wait 1-2 minutes for changes to propagate

### Step 2: Create OAuth Credentials

1. In Google Cloud Console, navigate to: **APIs & Services** → **Credentials**
2. Click: **Create Credentials** → **OAuth client ID**
3. If prompted to configure the OAuth consent screen:
   - User Type: Choose **External**
   - App information:
     - App name: `Chibi Bot` (or any name)
     - User support email: Your email
     - Developer contact email: Your email
   - Click **Save and Continue** through all steps (you can skip optional sections)
4. Back on the Credentials page, click **Create Credentials** → **OAuth client ID** again
5. Application type: Select **Desktop app**
6. Name: `Chibi Bot` (or any name)
7. Click **Create**
8. **Download** the JSON credentials file (click the download icon)
9. Save it as: `credentials/google_oauth_credentials.json` in your project directory

### Step 3: Configure Export Folder (Optional)

Edit `config.yaml` to customize where exports are saved:

```yaml
backup:
  credentials_file: "credentials/google_oauth_credentials.json"
  token_file: "credentials/token.json"
  folder_name: "Chibi Bot Exports"  # Folder name in your Google Drive
  scopes:
    - "https://www.googleapis.com/auth/spreadsheets"
    - "https://www.googleapis.com/auth/drive.file"
```

The `folder_name` setting organizes all exports into a specific Google Drive folder. The folder is created automatically if it doesn't exist. To save exports to your Drive root instead, set `folder_name: ""` or remove the line.

### Step 4: Authorize Access

When you first run `/export-progress`, you'll need to authorize the bot:

1. Run `/export-progress` in Discord
2. Check your terminal - you'll see a URL
3. Open the URL in your browser
4. Sign in with your Google account
5. Click **"Advanced"** → **"Go to Chibi Bot (unsafe)"**
   - This warning appears because the app is in development mode
   - Your bot is safe since you created it!
6. Click **"Allow"** to grant permissions
7. The bot saves an access token to `credentials/token.json`
8. Future exports work automatically without needing a browser

---

## Using the Backup System

### Exporting Data

1. In Discord (as an admin), run:
   ```
   /export-progress
   ```

2. The bot will:
   - Create a new spreadsheet in your Google Drive
   - Save it to the configured folder
   - Reply with a clickable link and export summary

3. The spreadsheet contains multiple sheets:
   - **Users** - Student profiles
   - **Quiz Attempts** - All quiz attempts with responses
   - **Concept Mastery** - Mastery levels per concept
   - **LLM Quiz Attempts** - LLM Challenge history
   - **Attendance** - Attendance records

### Importing Data

**⚠️ Warning:** Replace mode will delete all existing data!

1. Get the spreadsheet URL from a previous export
2. In Discord, run:
   ```
   /import-progress <spreadsheet_url> mode:merge
   ```
   or
   ```
   /import-progress <spreadsheet_url> mode:replace
   ```

3. For replace mode, you'll need to confirm with a button click

4. The bot will import data and report the number of records imported

### Listing Recent Exports

```
/list-exports
```

Shows the 10 most recent exports with clickable links.

---

## Troubleshooting

### "API not enabled" error

**Problem:** Google Sheets API or Google Drive API is not enabled

**Solution:**
- Ensure both APIs are enabled in Google Cloud Console
- Wait 1-2 minutes after enabling for changes to propagate
- Verify you're using the correct Google Cloud project

### "Browser authorization fails" or "Invalid credentials"

**Problem:** OAuth credentials are incorrect or corrupted

**Solution:**
1. Delete `credentials/token.json` if it exists
2. Verify `credentials/google_oauth_credentials.json` is the OAuth client ID file (not service account)
3. Run `/export-progress` again and complete authorization
4. Make sure you downloaded the "Desktop app" OAuth credentials

### "Permission denied" or "Access not granted"

**Problem:** OAuth flow was cancelled or permissions were denied

**Solution:**
- During OAuth flow, ensure you click **"Allow"** for all requested permissions
- Don't click "Cancel" or close the browser during authorization
- If you accidentally denied permission, delete `credentials/token.json` and try again

### "Folder creation failed"

**Problem:** Can't create the export folder in Google Drive

**Solution:**
- Check that your `config.yaml` has valid `folder_name` (avoid special characters like `/`, `\`, `:`)
- Ensure Drive API is enabled in Google Cloud Console
- Verify OAuth scopes in `config.yaml` include `drive.file`

### Imports not working

**Problem:** Import command fails or imports incomplete data

**Solution:**
- Verify the spreadsheet URL is correct and accessible
- Ensure the spreadsheet was created by this bot (has expected format)
- Don't manually edit column names or sheet names in the spreadsheet
- For Replace mode, confirm you clicked the confirmation button
- Check bot logs for specific error messages

### "Token expired" or "Invalid grant"

**Problem:** OAuth token has expired or been revoked

**Solution:**
1. Delete `credentials/token.json`
2. Run `/export-progress` again
3. Complete the authorization flow in your browser

---

## Security Best Practices

### Credential Files

**Keep these files secure and never commit them to git:**
- `credentials/google_oauth_credentials.json` - OAuth client credentials
- `credentials/token.json` - OAuth access/refresh tokens

**Recommended `.gitignore` entries:**
```
credentials/*.json
credentials/token.json
```

### Sharing Spreadsheets

- Exported spreadsheets are private to your Google account by default
- You can share them with others via Google Drive's sharing settings
- Be aware that spreadsheets contain student data (PII)
- Follow your institution's data privacy policies

### Access Control

- Only administrators can run backup commands
- OAuth credentials grant access to your Google Drive
- Tokens are stored locally and never shared
- The bot only creates/accesses files it created (via Drive API scope)

---

## Advanced Usage

### Scheduled Backups

Consider creating a cron job or scheduled task to export regularly:

```bash
# Example: Daily backup at 2 AM
0 2 * * * cd /path/to/discord-qa-agent && python -c "from chibi.backup import BackupService; import asyncio; asyncio.run(BackupService(...).export_progress())"
```

### Cross-Machine Data Transfer

Use exports to move student data between environments:

1. On machine A: `/export-progress`
2. Copy the spreadsheet URL
3. On machine B: `/import-progress <url> mode:replace`
4. All student progress is now on machine B

### Data Recovery

Keep periodic exports as backups:

- Weekly exports for routine backup
- Before major bot updates
- Before database migrations
- After important class sessions

### Custom Export Folders

Organize exports by semester or course:

```yaml
backup:
  folder_name: "Chibi Bot Exports/Fall 2025"
```

Folders are created automatically with `/` separators.

---

## Understanding Export Format

### Spreadsheet Structure

Each export creates a new spreadsheet with multiple sheets:

**Users Sheet**
- Columns: user_id, discord_id, username, student_id, student_name, created_at, last_active
- One row per registered student

**Quiz Attempts Sheet**
- Columns: attempt_id, user_id, module_id, concept_id, question, user_answer, correct_answer, is_correct, score, feedback, created_at
- One row per quiz attempt

**Concept Mastery Sheet**
- Columns: user_id, concept_id, mastery_level, correct_attempts, total_attempts, last_updated
- One row per user per concept

**LLM Quiz Attempts Sheet**
- Columns: attempt_id, user_id, module_id, question, student_answer, llm_answer, student_correct, llm_correct, won, created_at
- One row per LLM Challenge attempt

**Attendance Sheet**
- Columns: record_id, user_id, username, session_id, date_id, status, submitted_at
- One row per attendance submission

### Data Integrity

- All IDs are preserved during import/export
- Timestamps are stored as ISO 8601 strings
- Replace mode deletes before importing (no orphaned data)
- Merge mode updates existing records by ID

---

## Related Documentation

- [Complete Setup Guide](../SETUP_GUIDE.md) - Full setup instructions for beginners
- [Configuration Guide](configuration.md) - All config.yaml options
- [Admin Commands](commands.md) - Complete command reference
