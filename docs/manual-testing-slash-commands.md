# Manual Testing Guide: Admin Slash Commands

## Test ID: MT-003

## Objective
Verify that all 12 admin slash commands work correctly with proper permissions, ephemeral messaging, and user interactions.

## Background
This test suite validates the conversion of admin prefix commands (!) to slash commands (/). All admin commands now use Discord's native slash command system with administrator permission checks.

## Prerequisites

- [ ] Discord bot is running (`python main.py`)
- [ ] Bot is connected to a test Discord server
- [ ] Test server has at least two users:
  - One with administrator permissions (for testing admin commands)
  - One without administrator permissions (for testing permission denial)
- [ ] Test server has multiple students registered (for testing status/grade commands)
- [ ] Course configuration has multiple modules defined
- [ ] Admin channel is configured in `config.yaml`
- [ ] Attendance channel is configured in `config.yaml`

## Test Cases

### Section 1: Permission Checks

**Objective:** Verify that only administrators can see and use admin commands.

#### Test 1.1: Admin User Can See Commands
**Steps:**
1. Log in as a user with administrator permissions
2. Type `/` in any channel
3. Look for commands starting with `/admin-`

**Expected Result:**
- All 12 `/admin-*` commands appear in the autocomplete list
- Commands have "[ADMIN]" prefix in descriptions

**Pass/Fail Criteria:**
- [ ] `/admin-help` visible
- [ ] `/admin-modules` visible
- [ ] `/admin-students` visible
- [ ] `/admin-grade` visible
- [ ] `/admin-status` visible
- [ ] `/admin-clear-similarity` visible
- [ ] `/admin-open-attendance` visible
- [ ] `/admin-close-attendance` visible
- [ ] `/admin-export-attendance` visible
- [ ] `/admin-excuse` visible
- [ ] `/admin-mark-present` visible
- [ ] `/admin-remove-attendance` visible

#### Test 1.2: Non-Admin User Cannot See Commands
**Steps:**
1. Log in as a user WITHOUT administrator permissions
2. Type `/` in any channel
3. Search for `/admin-`

**Expected Result:**
- No `/admin-*` commands appear in the autocomplete
- Discord hides these commands from non-admin users automatically

**Pass/Fail Criteria:**
- [ ] No `/admin-*` commands visible to non-admin user

---

### Section 2: General Admin Commands

#### Test 2.1: `/admin-help`
**Steps:**
1. Run `/admin-help` from any channel
2. Check the response

**Expected Result:**
- Response is ephemeral (only visible to you)
- Embed shows all admin commands organized by category
- Quick stats show module count and student count
- Footer suggests using `/admin-modules` and `/admin-students`

**Pass/Fail Criteria:**
- [ ] Response is ephemeral
- [ ] All 6 general admin commands listed
- [ ] All 6 attendance commands listed
- [ ] Module and student counts displayed
- [ ] Command descriptions are clear

#### Test 2.2: `/admin-modules`
**Steps:**
1. Run `/admin-modules` from any channel
2. Check the response

**Expected Result:**
- Response is ephemeral
- Embed lists all configured modules
- Each module shows: ID, name, description (truncated), concept count

**Pass/Fail Criteria:**
- [ ] Response is ephemeral
- [ ] All modules from `course.yaml` are listed
- [ ] Module descriptions are truncated if too long
- [ ] Concept counts are accurate

#### Test 2.3: `/admin-students`
**Steps:**
1. Run `/admin-students` from any channel
2. Check the response

**Expected Result:**
- Response is ephemeral
- Embed lists all registered students
- Each student shows: Discord ID, username, last active date
- Footer suggests using `/admin-status` for details

**Pass/Fail Criteria:**
- [ ] Response is ephemeral
- [ ] All registered students are listed
- [ ] Last active dates are formatted as YYYY-MM-DD
- [ ] Students with no activity show "Never"

#### Test 2.4: `/admin-grade` (all modules)
**Steps:**
1. Run `/admin-grade` without parameters
2. Check the response

**Expected Result:**
- Response is ephemeral
- CSV file attachment with filename format: `student_grades_TIMESTAMP.csv`
- CSV contains columns: `discord_id, username, module, completion_pct`
- CSV includes data for all modules

**Pass/Fail Criteria:**
- [ ] Response is ephemeral
- [ ] CSV file attachment received
- [ ] CSV contains expected columns
- [ ] All modules included in export
- [ ] Completion percentages are calculated correctly

#### Test 2.5: `/admin-grade module:` (filtered)
**Steps:**
1. Run `/admin-grade` and start typing a module name
2. Select a module from autocomplete
3. Submit the command

**Expected Result:**
- Autocomplete shows available modules
- Response is ephemeral
- CSV file only contains data for the selected module
- Filename includes module ID: `student_grades_MODULE_TIMESTAMP.csv`

**Pass/Fail Criteria:**
- [ ] Autocomplete works for module selection
- [ ] Response is ephemeral
- [ ] CSV only contains selected module data
- [ ] Filename includes module ID

#### Test 2.6: `/admin-status student:` (summary view)
**Steps:**
1. Run `/admin-status` and use Discord's user picker to select a student
2. Do NOT provide a module parameter
3. Submit the command

**Expected Result:**
- User picker shows all server members
- Response is ephemeral
- Embed shows student summary with:
  - Discord ID
  - Quiz performance (total quizzes, accuracy)
  - Overall progress percentage
  - Module progress bars
  - Last active timestamp
- Footer suggests using with module parameter for details

**Pass/Fail Criteria:**
- [ ] Discord user picker works
- [ ] Response is ephemeral
- [ ] Quiz statistics are accurate
- [ ] Progress bars render correctly
- [ ] All modules shown with progress

#### Test 2.7: `/admin-status student: module:` (detailed view)
**Steps:**
1. Run `/admin-status` with a student selected
2. Provide a module parameter using autocomplete
3. Submit the command

**Expected Result:**
- Response is ephemeral
- Embed shows detailed module progress with:
  - Per-concept mastery status (emojis: ⬜/🟨/🟦/🟩)
  - Progress bar for module
  - Module completion percentage
  - Concept-by-concept breakdown
- Footer suggests using without module for overall summary

**Pass/Fail Criteria:**
- [ ] Response is ephemeral
- [ ] Mastery emojis display correctly
- [ ] Concept names and progress shown
- [ ] Module progress bar is accurate

#### Test 2.8: `/admin-clear-similarity` (all modules)
**Steps:**
1. Run `/admin-clear-similarity` without parameters
2. Confirm the operation

**Expected Result:**
- Response is ephemeral
- Success message shows total questions cleared
- Similarity database (ChromaDB) is cleared for all modules

**Pass/Fail Criteria:**
- [ ] Response is ephemeral
- [ ] Success message includes count
- [ ] Similarity database cleared (verify with subsequent LLM quiz submissions)

#### Test 2.9: `/admin-clear-similarity module:` (specific module)
**Steps:**
1. Run `/admin-clear-similarity` with a module selected from autocomplete
2. Confirm the operation

**Expected Result:**
- Response is ephemeral
- Success message shows questions cleared for that module only
- Only specified module's similarity data is cleared

**Pass/Fail Criteria:**
- [ ] Module autocomplete works
- [ ] Response is ephemeral
- [ ] Success message includes module ID and count
- [ ] Only specified module is cleared

---

### Section 3: Attendance Admin Commands

#### Test 3.1: `/admin-open-attendance`
**Steps:**
1. Ensure no attendance session is active
2. Run `/admin-open-attendance` from any channel
3. Check both admin and attendance channels
4. Wait 15 seconds and check if code rotates

**Expected Result:**
- Ephemeral confirmation message sent to admin
- Public message posted in admin channel showing the code
- Public message posted in attendance channel (no code shown)
- Code rotates every 15 seconds
- Code embed updates with submission count

**Pass/Fail Criteria:**
- [ ] Ephemeral confirmation received
- [ ] Code displayed in admin channel
- [ ] Student notification in attendance channel
- [ ] Code rotates automatically
- [ ] Submission count updates

#### Test 3.2: `/admin-open-attendance` (session already active)
**Steps:**
1. Run `/admin-open-attendance` while a session is already active
2. Check the response

**Expected Result:**
- Ephemeral error message: "An attendance session is already active"
- No new session started

**Pass/Fail Criteria:**
- [ ] Error message is ephemeral
- [ ] Error message is clear
- [ ] Existing session not affected

#### Test 3.3: `/admin-close-attendance`
**Steps:**
1. Open an attendance session
2. Have at least one student submit with `/here <code>`
3. Run `/admin-close-attendance`
4. Check admin and attendance channel messages

**Expected Result:**
- Ephemeral confirmation showing saved count and session ID
- Admin channel message updated to show "Attendance Session Closed"
- Attendance channel message updated to show "Attendance is Now Closed"
- Code rotation stops
- Records saved to database

**Pass/Fail Criteria:**
- [ ] Ephemeral confirmation received
- [ ] Session ID provided
- [ ] Both channel messages updated
- [ ] Records saved (verify with export)

#### Test 3.4: `/admin-close-attendance` (no active session)
**Steps:**
1. Ensure no session is active
2. Run `/admin-close-attendance`

**Expected Result:**
- Ephemeral error message: "No active attendance session to close"

**Pass/Fail Criteria:**
- [ ] Error message is ephemeral
- [ ] Error message is clear

#### Test 3.5: `/admin-export-attendance` (all records)
**Steps:**
1. Ensure attendance records exist in database
2. Run `/admin-export-attendance` without session_id
3. Check the CSV file

**Expected Result:**
- Response is ephemeral
- CSV file attachment with filename: `attendance_all_TIMESTAMP.csv`
- CSV contains all attendance records
- Message shows record count

**Pass/Fail Criteria:**
- [ ] Response is ephemeral
- [ ] CSV file received
- [ ] All records included
- [ ] Record count accurate

#### Test 3.6: `/admin-export-attendance session_id:` (specific session)
**Steps:**
1. Run `/admin-export-attendance` with a specific session_id
2. Check the CSV file

**Expected Result:**
- Response is ephemeral
- CSV file with filename: `attendance_SESSION_ID.csv`
- CSV only contains records for that session

**Pass/Fail Criteria:**
- [ ] Response is ephemeral
- [ ] CSV filtered to session
- [ ] Filename includes session ID

#### Test 3.7: `/admin-excuse student: date:`
**Steps:**
1. Run `/admin-excuse` and select a student using Discord user picker
2. Provide a date in YYYY-MM-DD format (or leave empty for today)
3. Submit the command

**Expected Result:**
- Discord user picker shows all server members
- Response is ephemeral
- Success message confirms student marked as excused
- Record created/updated in database with status "excused"

**Pass/Fail Criteria:**
- [ ] User picker works
- [ ] Response is ephemeral
- [ ] Success message includes student name and date
- [ ] Database record created/updated

#### Test 3.8: `/admin-excuse student:` (invalid date format)
**Steps:**
1. Run `/admin-excuse` with a student
2. Provide date in wrong format (e.g., "12/01/2025")
3. Submit the command

**Expected Result:**
- Ephemeral error message: "Invalid date format"
- Error message suggests YYYY-MM-DD format

**Pass/Fail Criteria:**
- [ ] Error message is ephemeral
- [ ] Error message is helpful

#### Test 3.9: `/admin-mark-present student: date:` (existing record)
**Steps:**
1. Find a student with an existing attendance record
2. Run `/admin-mark-present` for that student and date
3. Check the response

**Expected Result:**
- Response is ephemeral
- Success message indicates record was updated
- Message shows previous status
- Database record updated to "present"

**Pass/Fail Criteria:**
- [ ] Response is ephemeral
- [ ] Previous status shown
- [ ] Record updated correctly

#### Test 3.10: `/admin-mark-present student: date:` (new record)
**Steps:**
1. Select a student without an attendance record for a specific date
2. Run `/admin-mark-present` for that student and date
3. Check the response

**Expected Result:**
- Response is ephemeral
- Success message confirms manual attendance record created
- Session ID provided
- Database record created with status "present"

**Pass/Fail Criteria:**
- [ ] Response is ephemeral
- [ ] Session ID provided
- [ ] New record created

#### Test 3.11: `/admin-remove-attendance student: date:`
**Steps:**
1. Find a student with an attendance record
2. Run `/admin-remove-attendance` with student and date
3. Confirm the operation

**Expected Result:**
- Response is ephemeral
- Success message shows count of records removed
- Database record deleted

**Pass/Fail Criteria:**
- [ ] Response is ephemeral
- [ ] Record count shown
- [ ] Record deleted from database

#### Test 3.12: `/admin-remove-attendance student:` (no filters)
**Steps:**
1. Run `/admin-remove-attendance` with only student parameter (no date or session_id)
2. Submit the command

**Expected Result:**
- Ephemeral error message: "Please specify either a date or session_id"

**Pass/Fail Criteria:**
- [ ] Error message is ephemeral
- [ ] Error message explains requirement

---

### Section 4: Edge Cases

#### Test 4.1: Student Not in Database
**Steps:**
1. Run `/admin-status` with a Discord user who has never used the bot
2. Check the response

**Expected Result:**
- Ephemeral message: "User hasn't taken any quizzes yet. They need to use /quiz first."

**Pass/Fail Criteria:**
- [ ] Helpful error message
- [ ] Message mentions /quiz command

#### Test 4.2: Empty Database
**Steps:**
1. Test with no students registered
2. Run `/admin-students`
3. Run `/admin-grade`

**Expected Result:**
- `/admin-students`: "No students registered yet"
- `/admin-grade`: Empty CSV or appropriate message

**Pass/Fail Criteria:**
- [ ] Graceful handling of empty state
- [ ] No errors thrown

#### Test 4.3: Invalid Module ID
**Steps:**
1. Run `/admin-grade` with autocomplete
2. Select a module, but then modify the module ID to an invalid value manually (if possible)
3. Submit

**Expected Result:**
- Error message: "Module not found"

**Pass/Fail Criteria:**
- [ ] Error message is clear
- [ ] Autocomplete prevents most invalid inputs

#### Test 4.4: Commands from Non-Admin Channel
**Steps:**
1. Run any `/admin-*` command from a channel other than the admin channel
2. Check if command works

**Expected Result:**
- Command works from any channel (no channel restriction for slash commands)
- Response is ephemeral

**Pass/Fail Criteria:**
- [ ] Commands work from any channel
- [ ] Responses remain ephemeral

---

### Section 5: Backwards Compatibility

#### Test 5.1: Prefix Commands Still Work
**Steps:**
1. In the admin channel, run old prefix commands:
   - `!help`
   - `!status @user`
   - `!show_grade`
   - `!open_attendance`
2. Check responses

**Expected Result:**
- All prefix commands still function
- Responses match previous behavior

**Pass/Fail Criteria:**
- [ ] Prefix commands work
- [ ] No breaking changes

#### Test 5.2: Deprecation Warnings (Optional Future Enhancement)
**Steps:**
1. Run a prefix command
2. Check if there's a deprecation notice

**Expected Result:**
- (Optional) Response includes a note about slash commands being preferred

**Pass/Fail Criteria:**
- [ ] If implemented, deprecation notice is present
- [ ] If not implemented, skip this test

---

## Common Issues & Troubleshooting

### Issue: Commands Don't Appear
**Cause:** Discord hasn't synced commands yet
**Solution:**
- Ensure `sync_commands_on_startup: true` in config.yaml
- Restart bot
- Wait 1-2 minutes for Discord to sync
- Try in a private/incognito window

### Issue: "Interaction Failed"
**Cause:** Command took too long to respond
**Solution:**
- Check bot logs for errors
- Ensure database connections are working
- Verify LLM providers are accessible

### Issue: Session Manager Conflicts
**Cause:** Both prefix and slash cogs trying to use different session managers
**Solution:**
- Verify bot.py initializes shared `attendance_session_manager`
- Check both attendance.py and attendance_slash.py use `bot.attendance_session_manager`

### Issue: Ephemeral Messages Not Working
**Cause:** Wrong response method used
**Solution:**
- Verify commands use `await interaction.response.defer(ephemeral=True)`
- Use `interaction.followup.send(..., ephemeral=True)` for responses

---

## Summary

| Category | Test Count | Expected Pass Rate |
|----------|------------|--------------------|
| Permission Checks | 2 | 100% |
| General Admin Commands | 7 | 100% |
| Attendance Admin Commands | 9 | 100% |
| Edge Cases | 4 | 100% |
| Backwards Compatibility | 2 | 100% |
| **Total** | **24** | **100%** |

## Code References

**Implementation Files:**
- `chibi/cogs/admin_slash.py` - All 6 general admin slash commands
- `chibi/cogs/attendance_slash.py` - All 6 attendance admin slash commands
- `chibi/bot.py:143` - Attendance session manager initialization
- `chibi/bot.py:334-337` - Cog loading

**Shared Components:**
- `chibi/services/attendance_session.py` - AttendanceSessionManager (shared between cogs)
- `chibi/cogs/utils.py` - module_autocomplete_choices helper

**Backwards Compatibility:**
- `chibi/cogs/admin.py:1-13` - Deprecation notice
- `chibi/cogs/attendance.py:1-14` - Deprecation notice
