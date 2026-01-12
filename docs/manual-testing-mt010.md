# Manual E2E Testing: MT-010 - List Recent Exports

## Test Objective
Verify that the `/list-exports` command correctly queries Google Drive, retrieves recent exports, sorts them by date (newest first), respects the limit parameter, and displays results with correct formatting.

## Background
The BackupService.list_recent_exports() method (`chibi/backup/backup_service.py:202-232`) queries Google Drive for spreadsheets named "Chibi Student Progress" and returns them sorted by creation date. The Discord command (`chibi/cogs/backup_cog.py:265-329`) formats these results as an embed with:

- List of exports with creation dates
- Clickable links to open spreadsheets
- Configurable limit parameter (1-25, default 10)
- Empty state handling when no exports exist

This test verifies the query, sorting, formatting, and limit functionality work correctly with real Google Drive API.

## Prerequisites

Before starting this test, verify:

- [ ] MT-003 passed (export functionality works)
- [ ] Bot is running and you have admin permissions in Discord
- [ ] Google Sheets API and Drive API are enabled
- [ ] Service account has permissions to list files

## Part 1: Prepare Test Data

### Step 1: Create multiple exports with time spacing
```bash
# In Discord, create 3 exports with pauses between them
# This ensures they have different creation timestamps

/export-progress
# Wait for completion, copy URL

# Wait 5-10 seconds
# (This ensures different creation times)

/export-progress
# Wait for completion, copy URL

# Wait 5-10 seconds

/export-progress
# Wait for completion, copy URL
```

**Record the URLs:**
- `EXPORT_1 = _________________` (oldest)
- `EXPORT_2 = _________________` (middle)
- `EXPORT_3 = _________________` (newest)

**Expected:** Each export succeeds and returns a unique spreadsheet URL

**Pass criteria:** 3 successful exports with different spreadsheet IDs

### Step 2: Verify exports exist in service account's Drive
**Note:** With service account authentication, you may not be able to view these files in your personal Google Drive. This is expected behavior - the files exist in the service account's isolated Drive space.

**Expected:** Bot logs show successful creations

## Part 2: Test Default List Command

### Step 3: Run list-exports with defaults
```bash
# In Discord:
/list-exports
```

**Expected bot response:**
- 📋 Embed titled "Recent Exports (N)" where N is count
- Description: "Click on a spreadsheet to open it in Google Sheets."
- List shows AT LEAST 3 exports (the ones we just created)
- Each export has:
  - Spreadsheet name (e.g., "Chibi Student Progress - 2026-01-12 14:30")
  - Creation date/time
  - Clickable link

**Pass criteria:**
- Bot responds within 5 seconds
- All 3 recent exports appear in list
- Count in title is accurate
- Links are formatted as clickable hyperlinks

### Step 4: Verify sort order (newest first)
Look at the list returned by Step 3.

**Expected order:**
1. EXPORT_3 (newest, created last)
2. EXPORT_2 (middle)
3. EXPORT_1 (oldest, created first)

**Pass criteria:**
- Exports appear in reverse chronological order
- Most recent export is first in list
- Oldest export is last in list
- Creation timestamps confirm order

**Note:** If you created many exports in previous tests, the list may show more than 3 items. That's acceptable as long as the newest 3 are in correct order.

## Part 3: Test Limit Parameter

### Step 5: Test limit parameter with small value
```bash
# In Discord:
/list-exports limit:2
```

**Expected bot response:**
- Embed titled "Recent Exports (2)"
- Shows exactly 2 exports
- Shows the 2 most recent (EXPORT_3 and EXPORT_2)
- Does NOT show EXPORT_1 (oldest)

**Pass criteria:**
- Exactly 2 exports shown (not more, not less)
- Shows the 2 newest exports
- Limit parameter respected

### Step 6: Test limit parameter with large value
```bash
# In Discord:
/list-exports limit:25
```

**Expected bot response:**
- Embed shows up to 25 exports
- If you have fewer than 25 exports, shows all of them
- Title shows actual count (e.g., "Recent Exports (5)" if you have 5)
- Still sorted newest first

**Pass criteria:**
- Shows all available exports (up to 25 max)
- Count is accurate
- Limit capped at 25 (maximum allowed)

### Step 7: Test limit parameter validation
```bash
# In Discord, test edge cases:
/list-exports limit:0
```

**Expected:** Bot responds with AT LEAST 1 export (limit validated to minimum 1)

```bash
/list-exports limit:100
```

**Expected:** Bot responds with maximum 25 exports (limit capped)

**Pass criteria:**
- Limit 0 → shows at least 1 export (validated to min=1)
- Limit 100 → shows max 25 exports (capped at max=25)
- Validation prevents invalid limits

## Part 4: Test Empty State

### Step 8: Test when no exports exist (optional)
**Note:** This test is optional because it requires deleting all exports or using a clean service account.

**If you want to test:**
1. Delete all export spreadsheets from service account's Drive (if possible)
2. OR create new service account with no exports

```bash
# In Discord:
/list-exports
```

**Expected bot response:**
- Embed titled "📋 Recent Exports"
- Description: "No exports found. Use `/export-progress` to create one."
- Empty list (no exports shown)
- Blue color (informational)

**Pass criteria:**
- Graceful empty state handling
- Helpful message guides user to create export
- No errors or crashes

**Skip criteria:** If you cannot delete exports or create clean service account, skip this step. It's not critical.

## Part 5: Test Link Functionality

### Step 9: Click a link to verify it works
From the list in Step 3 or Step 6:
1. Click on any spreadsheet link
2. Observe if browser opens
3. Check if spreadsheet loads

**Expected:**
- Link opens in new browser tab/window
- Google Sheets interface loads (or permission error if service account Drive)
- Spreadsheet ID in URL matches the one in Discord

**Pass criteria (Minimum):**
- Link is clickable
- URL format is correct: `https://docs.google.com/spreadsheets/d/{ID}`
- Spreadsheet ID matches Discord output

**Pass criteria (Full):**
- Spreadsheet actually opens and displays data
- (May not be possible with service account isolation)

## Part 6: Test Response Time

### Step 10: Measure response time for large list
```bash
# In Discord, time this command:
/list-exports limit:25
```

**Expected:** Bot responds within 10 seconds

**Pass criteria:**
- Response time < 10 seconds for up to 25 exports
- No timeout errors
- Google Drive API query completes successfully

## Part 7: Verify Data Accuracy

### Step 11: Compare export details
From the list in Step 3:
1. Pick EXPORT_3 (newest) from list
2. Note the creation date/time shown
3. Compare to when you actually created it (Step 1)

**Expected:**
- Creation date/time is accurate (within 1 minute)
- Spreadsheet name matches format: "Chibi Student Progress - YYYY-MM-DD HH:MM"
- Time zone is consistent

**Pass criteria:**
- Timestamps are accurate
- Format is consistent across all exports
- No incorrect or missing data

## Pass/Fail Criteria

### Minimum Passing Criteria (Required)
All of the following MUST be true for MT-010 to pass:

1. **Default List Command (Steps 3-4):**
   - [ ] `/list-exports` returns list of exports
   - [ ] Shows at least the 3 exports created in Step 1
   - [ ] Exports sorted by date (newest first)
   - [ ] Title shows accurate count
   - [ ] Each export has name, date, and clickable link

2. **Limit Parameter (Steps 5-7):**
   - [ ] `limit:2` shows exactly 2 exports (newest 2)
   - [ ] `limit:25` shows up to 25 exports
   - [ ] `limit:0` validated to minimum 1
   - [ ] `limit:100` capped at maximum 25
   - [ ] Limit parameter correctly applied

3. **Link Functionality (Step 9):**
   - [ ] Links are clickable in Discord
   - [ ] URL format correct: `https://docs.google.com/spreadsheets/d/{ID}`
   - [ ] Spreadsheet IDs are unique and valid

4. **Response Time (Step 10):**
   - [ ] Command completes within 10 seconds
   - [ ] No timeout errors
   - [ ] API queries succeed

5. **Data Accuracy (Step 11):**
   - [ ] Creation timestamps accurate
   - [ ] Spreadsheet names formatted correctly
   - [ ] Data matches actual export details

### Full Verification (Optional)
If you have spreadsheet access:

6. **Empty State (Step 8):**
   - [ ] Graceful handling when no exports exist
   - [ ] Helpful message displayed

7. **Spreadsheet Access (Step 9):**
   - [ ] Links actually open spreadsheets
   - [ ] Data visible and correct

## Common Issues & Solutions

### Issue 1: "No exports found" despite creating exports
**Symptoms:** List-exports returns empty even after creating exports in Step 1

**Causes:**
- Google Drive API indexing delay (files not yet indexed)
- Query filter not matching file names
- Service account permissions issue
- Different Drive space than expected

**Solutions:**
1. Wait 30-60 seconds and try again (API indexing delay)
2. Check bot logs for Drive API errors
3. Verify export names contain "Chibi Student Progress"
4. Run `/export-progress` again to create new export
5. Check service account has Drive API access
6. Verify query: `name contains 'Chibi Student Progress'`

**Code reference:** `chibi/backup/backup_service.py:225` (query string)

### Issue 2: Exports not in chronological order
**Symptoms:** List shows exports in wrong order (not newest first)

**Causes:**
- GoogleSheetsClient not sorting by creation date
- Creation timestamps too close together
- API returns unsorted results

**Solutions:**
1. Check GoogleSheetsClient.list_spreadsheets() implementation
2. Verify sorting by createdTime field
3. Create exports with longer pauses (30+ seconds apart)
4. Check API response includes createdTime field
5. Review sorting logic in backup_service.py

**Code reference:** `chibi/backup/google_sheets_client.py` (list_spreadsheets method)

### Issue 3: Cannot access spreadsheet links
**Symptoms:** Clicking link shows "You need permission"

**Causes:**
- Service account creates files in isolated Drive
- Human users don't have access to service account's Drive
- This is EXPECTED behavior

**Solutions:**
1. **This is not a bug** - working as designed with service account
2. Verify link format is correct (that's sufficient for passing)
3. Alternative: switch to OAuth credentials to use personal Drive
4. Future enhancement: implement sharing via Drive API
5. Test passes based on link format, not accessibility

**Code reference:** `chibi/backup/google_sheets_client.py:96-113` (authentication type)

### Issue 4: Limit parameter doesn't work
**Symptoms:** Shows wrong number of exports despite limit parameter

**Causes:**
- Limit validation not applied
- BackupService not respecting limit
- Discord command not passing limit correctly

**Solutions:**
1. Check limit validation: `limit = max(1, min(limit, 25))`
2. Verify BackupService receives limit parameter
3. Check list slicing: `spreadsheets[:limit]`
4. Test with explicit limits: 1, 5, 10, 25
5. Check logs for limit value passed to service

**Code reference:** `chibi/cogs/backup_cog.py:287` (limit validation)
**Code reference:** `chibi/backup/backup_service.py:229` (limit application)

### Issue 5: Command times out or is very slow
**Symptoms:** Bot takes >10 seconds to respond or times out

**Causes:**
- Many exports in Drive (1000+)
- Google Drive API rate limiting
- Network latency
- API quota exhausted

**Solutions:**
1. Check Google Cloud Console for API quotas
2. Reduce limit to smaller value (e.g., limit:5)
3. Verify network connectivity
4. Check for API rate limit errors in logs
5. Wait a few minutes and retry

**Code reference:** `chibi/backup/google_sheets_client.py` (API calls)

### Issue 6: Duplicate exports shown
**Symptoms:** Same export appears multiple times in list

**Causes:**
- Google Drive API returning duplicates
- Query filter too broad
- Multiple exports with identical names

**Solutions:**
1. Check if exports actually have identical spreadsheet IDs
2. If IDs different but names same: expected (created at same second)
3. If IDs identical: bug in list_spreadsheets() implementation
4. Add logging to see raw API response
5. Test creating exports with longer time gaps

**Code reference:** `chibi/backup/backup_service.py:226` (spreadsheets query)

### Issue 7: Formatting issues in Discord embed
**Symptoms:** Links not clickable, formatting broken, text cut off

**Causes:**
- Discord embed field limits (1024 chars per field)
- Markdown formatting errors
- Too many exports for single embed

**Solutions:**
1. Check embed field character limits
2. Verify link format: `[Name](URL)` for clickable links
3. If too many exports, Discord may truncate
4. Test with smaller limit to verify formatting
5. Check for special characters in spreadsheet names

**Code reference:** `chibi/cogs/backup_cog.py:302-329` (embed building)

## Implementation Details

### List Exports Flow
```
/list-exports [limit]
  ↓
backup_cog.list_exports()  // Discord command handler
  ↓
Validate limit (1-25)  // chibi/cogs/backup_cog.py:287
  ↓
BackupService.list_recent_exports(limit)  // chibi/backup/backup_service.py:202
  ↓
GoogleSheetsClient.list_spreadsheets(query)  // Query Drive API
  query = "name contains 'Chibi Student Progress'"
  ↓
Drive API returns matching files
  sorted by createdTime DESC (newest first)
  ↓
Return spreadsheets[:limit]  // Apply limit
  ↓
Format as Discord embed
  Title, description, list of links
  ↓
Send ephemeral response to user
```

### Code Locations
- **Discord command:** `chibi/cogs/backup_cog.py:265-329`
- **Limit validation:** `chibi/cogs/backup_cog.py:287`
- **Service method:** `chibi/backup/backup_service.py:202-232`
- **Query string:** `chibi/backup/backup_service.py:225`
- **Limit application:** `chibi/backup/backup_service.py:229`
- **GoogleSheetsClient:** `chibi/backup/google_sheets_client.py` (list_spreadsheets method)

### Why List Functionality Matters
1. **Discoverability:** Users can find previous exports without saving URLs
2. **Audit Trail:** Track when exports were created
3. **Data Recovery:** Quickly access older exports if needed
4. **Usability:** Convenient access to backup history
5. **Transparency:** Users see what data has been exported

## Test Completion Checklist

- [ ] All 11 steps completed
- [ ] All 5 minimum passing criteria met
- [ ] List returns exports in correct order (newest first)
- [ ] Limit parameter works correctly
- [ ] Links are formatted and clickable
- [ ] Response time acceptable (< 10 seconds)
- [ ] Data accuracy verified

## Notes
- Estimated test duration: 15-20 minutes
- Requires creating multiple exports (may take 5-10 minutes)
- Service account Drive access limitations acceptable
- Link format verification sufficient (full access not required)
- Empty state test optional (difficult to set up)

## Test Result

**Date:** _____________
**Tester:** _____________
**Result:** ☐ PASS  ☐ FAIL
**Notes:**

---

**Test Guide Version:** 1.0
**Associated Story:** MT-010
**Dependencies:** MT-003 (export functionality must work)
**Implementation Reference:** `chibi/backup/backup_service.py:202-232`, `chibi/cogs/backup_cog.py:265-329`
