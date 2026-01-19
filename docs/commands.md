# Commands Reference

Complete reference for all Discord commands in Chibi Bot.

## Table of Contents

- [Student Commands](#student-commands)
- [Admin Commands](#admin-commands)
- [Google Sheets Commands](#google-sheets-commands)
- [Legacy Prefix Commands](#legacy-prefix-commands)

---

## Student Commands

Commands available to all users in the Discord server.

### `/quiz [module:]`

Generate a quiz question to test your knowledge.

**Parameters:**
- `module` (optional) - Specific module ID to quiz from. If not provided, selects from all available modules.

**Usage:**
```
/quiz
/quiz module:network-science
```

**What happens:**
1. Bot selects a concept from the specified module (or random module)
2. Generates a question using RAG-retrieved content
3. Opens a modal dialog for you to submit your answer
4. Evaluates your response and provides feedback
5. Updates your mastery progress

---

### `/llm-quiz module:`

Challenge the AI! Create a question to stump the LLM.

**Parameters:**
- `module` (required) - Module ID for the challenge

**Usage:**
```
/llm-quiz module:network-science
```

**How it works:**
1. Opens a modal where you write a question and your answer
2. An AI (quiz model) attempts to answer your question
3. An evaluator judges both answers
4. You win if your answer is correct AND the AI's is incorrect
5. Winning questions are tracked toward module completion

**Anti-cheat:** Questions are checked for similarity to prevent reuse.

---

### `/status [module:]`

View your learning progress and concept mastery.

**Parameters:**
- `module` (optional) - View detailed progress for a specific module

**Usage:**
```
/status                    # Overall progress
/status module:m01         # Detailed module view
```

**What you see:**
- **Overall view:** Quiz stats, progress bars per module, mastery overview
- **Module view:** Per-concept mastery, progress toward completion, LLM Quiz wins

---

### `/modules`

List all available course modules with descriptions.

**Usage:**
```
/modules
```

**Shows:**
- Module ID and name
- Brief description
- Number of concepts in each module

---

### `/register student_id: [student_name:]`

Register your student ID for attendance and gradebook integration.

**Parameters:**
- `student_id` (required) - Your student ID number
- `student_name` (optional) - Your full name

**Usage:**
```
/register student_id:12345
/register student_id:12345 student_name:John Doe
```

**Why register:**
- Links your Discord account to your student ID
- Enables attendance export with student information
- Shows your name in admin reports

---

### `/here code:`

Submit attendance with the current code.

**Parameters:**
- `code` (required) - The attendance code displayed by the instructor

**Usage:**
```
/here code:ABC123
```

**Notes:**
- Only works in the configured attendance channel
- Only works when an attendance session is active
- Latest submission counts (can resubmit with new codes)
- Codes rotate every 15 seconds

---

### `/guidance`

Get personalized guidance on your learning progress.

**Usage:**
```
/guidance
```

**Shows:**
- Areas where you're excelling
- Concepts that need more work
- Suggested next steps for studying

---

## Admin Commands

Commands only visible to users with administrator permissions.

### `/admin-help`

Show admin commands help and system stats.

**Usage:**
```
/admin-help
```

**Shows:**
- List of all admin commands
- Quick stats (module count, student count)
- Links to detailed documentation

---

### `/admin-modules`

List all available modules with details.

**Usage:**
```
/admin-modules
```

**Shows:**
- Module ID, name, description
- Number of concepts per module
- Content URLs

---

### `/admin-students`

List all registered students with activity info.

**Usage:**
```
/admin-students
```

**Shows:**
- Discord ID and username
- Last active date
- Student ID (if registered)
- Student name (if registered)

---

### `/admin-grade [module:]`

Generate CSV report of student grades.

**Parameters:**
- `module` (optional) - Filter by specific module

**Usage:**
```
/admin-grade                    # All modules
/admin-grade module:m01         # Specific module
```

**CSV contains:**
- Discord ID, username
- Module name
- Completion percentage
- Mastery levels

**Output:** Ephemeral file attachment (only you see it)

---

### `/admin-status student: [module:]`

View a student's learning progress.

**Parameters:**
- `student` (required) - Select student using Discord user picker
- `module` (optional) - View specific module details

**Usage:**
```
/admin-status student:@StudentName
/admin-status student:@StudentName module:m01
```

**Shows:**
- Quiz performance stats
- Overall or module-specific progress
- Concept-by-concept mastery
- Last active timestamp

**Note:** Uses Discord's native user picker for easy selection!

---

### `/admin-clear-similarity [module:]`

Clear LLM Quiz similarity database.

**Parameters:**
- `module` (optional) - Clear specific module or all if not provided

**Usage:**
```
/admin-clear-similarity              # Clear all modules
/admin-clear-similarity module:m01   # Clear specific module
```

**Purpose:**
- Resets the anti-cheat database
- Allows previously-used questions to be submitted again
- Useful when starting a new semester/cohort

---

### `/admin-open-attendance`

Start attendance session with rotating codes.

**Usage:**
```
/admin-open-attendance
```

**What happens:**
1. Posts code in admin channel (display on projector)
2. Posts notification in attendance channel (students see this)
3. Starts code rotation (every 15 seconds)
4. Tracks submissions in memory

**Note:** Only one session can be active at a time

---

### `/admin-close-attendance`

Close attendance session and save records to database.

**Usage:**
```
/admin-close-attendance
```

**What happens:**
1. Stops code rotation
2. Saves all submissions to database
3. Updates channel messages to show "closed"
4. Shows total submission count and session ID

---

### `/admin-export-attendance [session_id:]`

Export attendance records to CSV.

**Parameters:**
- `session_id` (optional) - Export specific session or all if not provided

**Usage:**
```
/admin-export-attendance                    # All records
/admin-export-attendance session_id:abc123  # Specific session
```

**CSV contains:**
- Student ID, name, Discord username
- Session ID, date
- Timestamp, status

**Output:** Ephemeral file attachment

---

### `/admin-excuse student: [date:]`

Mark a student as excused for a specific date.

**Parameters:**
- `student` (required) - Select student using Discord user picker
- `date` (optional) - Date in YYYY-MM-DD format (defaults to today)

**Usage:**
```
/admin-excuse student:@StudentName
/admin-excuse student:@StudentName date:2025-01-19
```

**Effect:**
- Creates or updates attendance record with "excused" status
- Shows in attendance exports

---

### `/admin-mark-present student: [date:] [session_id:]`

Manually mark a student as present.

**Parameters:**
- `student` (required) - Select student
- `date` (optional) - Date in YYYY-MM-DD format (defaults to today)
- `session_id` (optional) - Specific session ID

**Usage:**
```
/admin-mark-present student:@StudentName
/admin-mark-present student:@StudentName date:2025-01-19
/admin-mark-present student:@StudentName session_id:abc123
```

**Use cases:**
- Student had technical issues during class
- Retroactively mark attendance
- Override incorrect submissions

---

### `/admin-remove-attendance student: [date:] [session_id:]`

Remove a student's attendance record.

**Parameters:**
- `student` (required) - Select student
- `date` (optional) - Date in YYYY-MM-DD format
- `session_id` (optional) - Specific session ID

**Usage:**
```
/admin-remove-attendance student:@StudentName date:2025-01-19
/admin-remove-attendance student:@StudentName session_id:abc123
```

**Notes:**
- Requires at least one filter (date or session_id)
- Shows confirmation of records removed

---

## Google Sheets Commands

Admin commands for backup and data export.

### `/export-progress`

Export all student data to a new Google Sheets spreadsheet.

**Usage:**
```
/export-progress
```

**What gets exported:**
- User profiles
- Quiz attempts and responses
- Concept mastery tracking
- LLM Quiz Challenge attempts
- Attendance records

**Output:**
- Ephemeral message with spreadsheet link
- Summary of records exported
- Spreadsheet saved to configured Google Drive folder

---

### `/import-progress url: [mode:]`

Import student progress from a Google Sheets backup.

**Parameters:**
- `url` (required) - Google Sheets URL or spreadsheet ID
- `mode` (optional) - "replace" or "merge" (default: merge)

**Usage:**
```
/import-progress url:https://docs.google.com/spreadsheets/d/...
/import-progress url:https://docs.google.com/spreadsheets/d/... mode:replace
```

**Modes:**
- **Merge** - Update existing records, add new ones
- **Replace** - Delete all data first, then import (requires confirmation)

**Use cases:**
- Restore from backup
- Transfer data between machines
- Merge data from multiple sources

---

### `/list-exports [limit:]`

List recent Google Sheets exports.

**Parameters:**
- `limit` (optional) - Number of exports to show (default: 10, max: 25)

**Usage:**
```
/list-exports
/list-exports limit:5
```

**Shows:**
- Export name and creation date
- Clickable links to spreadsheets
- Ordered by most recent first

---

## Legacy Prefix Commands

**⚠️ DEPRECATED:** These prefix commands still work but will be removed in a future version. Please use the slash command equivalents above.

| Legacy Command | Slash Command Equivalent |
|---------------|-------------------------|
| `!help` or `!admin` | `/admin-help` |
| `!modules` | `/admin-modules` |
| `!students` | `/admin-students` |
| `!show_grade [module]` | `/admin-grade [module:]` |
| `!status <student> [module]` | `/admin-status student: [module:]` |
| `!clear_similarity [module]` | `/admin-clear-similarity [module:]` |
| `!open_attendance` | `/admin-open-attendance` |
| `!close_attendance` | `/admin-close-attendance` |
| `!export_attendance [session_id]` | `/admin-export-attendance [session_id:]` |
| `!excuse <student> [date]` | `/admin-excuse student: [date:]` |
| `!mark_present <student> [date] [session_id]` | `/admin-mark-present student: [date:] [session_id:]` |
| `!remove_attendance <student> [date] [session_id]` | `/admin-remove-attendance student: [date:] [session_id:]` |

**Why migrate:**
- Slash commands use Discord's native UI (user pickers, autocomplete)
- No need to remember exact syntax
- Better error messages
- Work from any channel (not restricted to admin channel)
- Ephemeral responses (only you see them)

---

## Related Documentation

- [Features Guide](features.md) - Detailed feature explanations
- [Setup Guide](../SETUP_GUIDE.md) - Installation and configuration
- [Configuration Guide](configuration.md) - Config file options
- [Google Sheets Setup](google-sheets-setup.md) - Backup system setup
