# Daily Backup Automation Guide

This guide explains how to set up automated daily exports of student progress data to Google Sheets with Discord notifications.

## Overview

The daily backup system automatically exports all student data to Google Sheets at a scheduled time and posts a notification to a Discord channel with the spreadsheet link.

**What gets backed up:**
- User profiles and registration data
- Quiz attempts with LLM feedback and scores
- Concept mastery tracking
- LLM quiz challenge attempts
- Attendance records

## Prerequisites

Before setting up automation, ensure you have:

1. **Google Sheets credentials configured** (see `docs/google-sheets-setup.md`)
   - OAuth credentials in `credentials/google_oauth_credentials.json`
   - Valid access token in `credentials/token.json` (created on first use)

2. **Discord bot token** in your `.env` file

3. **Python environment** with all dependencies installed (`uv sync`)

## Quick Setup

### 1. Configure Discord Notification Channel

Add the channel ID to your `.env` file where backup notifications should be posted:

```bash
# .env
BACKUP_NOTIFICATION_CHANNEL_ID=1234567890123456789
```

**To get the channel ID:**
1. Enable Developer Mode in Discord (User Settings → Advanced → Developer Mode)
2. Right-click the channel where you want notifications
3. Select "Copy Channel ID"

### 2. Test the Backup Script Manually

Before scheduling, test that the script works:

```bash
# From project root
python scripts/daily_backup.py
```

**Expected output:**
- Console logs showing backup progress
- New spreadsheet created in Google Drive
- Discord notification posted to configured channel
- Exit code 0 (success)

**If this fails:**
- Check that Google Sheets credentials are valid
- Verify Discord token and channel ID are correct
- Review logs in `logs/daily_backup.log`

### 3. Schedule with Cron (macOS/Linux)

#### Create the Cron Job

Edit your crontab:

```bash
crontab -e
```

Add this line to run backup daily at 2:00 AM:

```cron
0 2 * * * cd /Users/skojaku-admin/Documents/projects/applied-soft-comp/tutor/discord-qa-agent && /usr/bin/python3 scripts/daily_backup.py >> logs/cron_backup.log 2>&1
```

**Important:** Update the path to match your project location!

#### Cron Schedule Syntax

The format is: `minute hour day_of_month month day_of_week command`

Common schedules:
- `0 2 * * *` - Daily at 2:00 AM
- `0 0 * * *` - Daily at midnight
- `0 6 * * *` - Daily at 6:00 AM
- `0 2 * * 1` - Weekly on Mondays at 2:00 AM
- `0 2 1 * *` - Monthly on 1st at 2:00 AM

#### Verify Cron Job

List your cron jobs to confirm it was added:

```bash
crontab -l
```

### 4. Monitor the Backups

**Discord Notifications:**
- Success notifications include spreadsheet link and record counts
- Failure notifications show error details

**Log Files:**
- `logs/daily_backup.log` - Detailed backup operation logs
- `logs/cron_backup.log` - Cron execution output (stdout/stderr)

**Check Recent Logs:**

```bash
# View last 50 lines of backup log
tail -50 logs/daily_backup.log

# View cron execution log
tail -50 logs/cron_backup.log

# Watch logs in real-time during manual test
tail -f logs/daily_backup.log
```

## Alternative: Task Scheduler (Windows)

For Windows servers, use Task Scheduler instead of cron:

### Create Scheduled Task

1. Open Task Scheduler
2. Create Basic Task
   - Name: "Chibi Daily Backup"
   - Trigger: Daily at 2:00 AM
   - Action: Start a program
   - Program: `C:\Python311\python.exe` (adjust to your Python path)
   - Arguments: `scripts\daily_backup.py`
   - Start in: `C:\path\to\discord-qa-agent` (your project path)

### Configure Task Settings

- Run whether user is logged on or not
- Run with highest privileges
- Configure for: Windows 10/11

## Troubleshooting

### Backup Fails Silently

**Symptoms:** No Discord notification, no logs
**Causes:** Cron environment issues, path problems
**Solutions:**

1. Add full paths to cron command:
```cron
0 2 * * * cd /full/path/to/project && /usr/bin/python3 scripts/daily_backup.py
```

2. Add environment variables to cron:
```cron
DISCORD_TOKEN=your_token_here
BACKUP_NOTIFICATION_CHANNEL_ID=channel_id_here
0 2 * * * cd /path/to/project && python3 scripts/daily_backup.py
```

3. Use a wrapper shell script:
```bash
#!/bin/bash
export DISCORD_TOKEN="your_token"
export BACKUP_NOTIFICATION_CHANNEL_ID="channel_id"
cd /path/to/project
python3 scripts/daily_backup.py
```

### Google Sheets Authentication Fails

**Symptoms:** "Credentials not found" or "Token expired"
**Solutions:**

1. Verify credentials file exists: `credentials/google_oauth_credentials.json`
2. Regenerate token by running manual export first:
   ```bash
   python -c "from chibi.bot import create_bot; import asyncio; bot = create_bot('config.yaml'); asyncio.run(bot.backup_service.export_progress())"
   ```
3. Check token file permissions: `chmod 600 credentials/token.json`

### Discord Notification Not Posted

**Symptoms:** Backup succeeds but no Discord message
**Solutions:**

1. Verify `BACKUP_NOTIFICATION_CHANNEL_ID` is set in `.env`
2. Check bot has permission to post in that channel
3. Verify bot token is valid
4. Review logs for Discord API errors

### Permission Denied Errors

**Symptoms:** "Permission denied" when running cron job
**Solutions:**

1. Make script executable:
   ```bash
   chmod +x scripts/daily_backup.py
   ```

2. Check log directory exists and is writable:
   ```bash
   mkdir -p logs
   chmod 755 logs
   ```

3. Verify cron user has access to project directory

## Advanced Configuration

### Custom Backup Schedule

Edit the cron schedule to match your needs. For example, backup twice daily:

```cron
# Daily at 2 AM and 2 PM
0 2,14 * * * cd /path/to/project && python3 scripts/daily_backup.py
```

### Custom Notification Format

Edit `scripts/daily_backup.py` to customize the Discord embed:

- Modify `format_export_embed()` function
- Change colors, fields, or description
- Add additional data from export result

### Silent Backups (No Discord Notification)

Remove `BACKUP_NOTIFICATION_CHANNEL_ID` from `.env` to disable notifications:

```bash
# .env - comment out or remove the line
# BACKUP_NOTIFICATION_CHANNEL_ID=1234567890123456789
```

Backups will still run and log to files, but won't post to Discord.

### Multiple Backup Destinations

To export to multiple channels or services, modify the script:

```python
# In scripts/daily_backup.py main() function
for channel_id in [channel1_id, channel2_id, admin_channel_id]:
    await post_to_discord(channel_id, discord_token, content, embed)
```

## Maintenance

### Regular Checks

1. **Weekly:** Review Discord notifications to confirm backups are running
2. **Monthly:** Check Google Drive for expected number of backups
3. **Quarterly:** Test restore process using `/import-progress` command

### Log Rotation

Prevent log files from growing too large:

```bash
# Add to cron to rotate logs monthly
0 0 1 * * find /path/to/project/logs -name "*.log" -type f -mtime +30 -delete
```

Or use `logrotate`:

```bash
# /etc/logrotate.d/chibi-backup
/path/to/project/logs/daily_backup.log {
    daily
    rotate 30
    compress
    missingok
    notifempty
}
```

## Security Considerations

1. **Credentials Protection:**
   - Never commit `.env` or `credentials/*.json` to git
   - Restrict file permissions: `chmod 600 .env credentials/*.json`
   - Use environment variables for sensitive data

2. **Cron Environment:**
   - Avoid putting tokens directly in crontab (use `.env` instead)
   - Redirect output to log files, not email
   - Use full paths to avoid path injection

3. **Discord Bot Permissions:**
   - Bot only needs "Send Messages" permission in notification channel
   - Use a dedicated admin/logging channel with restricted access
   - Regularly rotate bot token if exposed

## Related Documentation

- [Google Sheets Setup Guide](google-sheets-setup.md) - OAuth credentials setup
- [Backup Commands Reference](../README.md#backup-commands) - Manual export/import commands
- [Manual Testing Guide](manual-testing-mt002.md) - E2E testing procedures

## Support

If you encounter issues:

1. Check logs: `logs/daily_backup.log` and `logs/cron_backup.log`
2. Test manual execution: `python scripts/daily_backup.py`
3. Verify environment variables in `.env`
4. Review Google Sheets setup: `docs/google-sheets-setup.md`
