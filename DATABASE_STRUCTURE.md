# Chibi Bot Database Structure

## Overview
The Chibi bot uses SQLite as its primary database (`data/chibi.db`) to store user data, quiz attempts, mastery tracking, and attendance records. All database operations are async using `aiosqlite`.

## Tables

### 1. users
Stores Discord user profiles and student registration information.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | Internal user ID |
| discord_id | TEXT | UNIQUE NOT NULL | Discord user ID |
| username | TEXT | NOT NULL | Discord username |
| student_id | TEXT | - | Student ID for class registration |
| student_name | TEXT | - | Student's real name |
| created_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | When user first interacted with bot |
| last_active | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Last interaction timestamp |

**Indexes:**
- `idx_users_student_id` on `student_id`

**Notes:**
- `student_id` and `student_name` are added via migration (may not exist in old databases)
- Used for linking Discord accounts to class roster

---

### 2. quiz_attempts
Records all quiz question attempts with LLM evaluation feedback.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | Attempt ID |
| user_id | INTEGER | NOT NULL, FOREIGN KEY → users(id) | User who took quiz |
| module_id | TEXT | NOT NULL | Module identifier (e.g., "module01") |
| concept_id | TEXT | NOT NULL | Concept identifier (e.g., "concept01") |
| quiz_format | TEXT | NOT NULL | Format: "mc", "tf", "short_answer" |
| question | TEXT | NOT NULL | The quiz question |
| user_answer | TEXT | NOT NULL | Student's submitted answer |
| correct_answer | TEXT | - | The correct answer (may be null for open-ended) |
| is_correct | BOOLEAN | NOT NULL | Whether answer was correct (0 or 1) |
| llm_feedback | TEXT | - | LLM-generated feedback on answer quality |
| llm_quality_score | INTEGER | - | Quality score (0-100) from LLM |
| created_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | When attempt was made |

**Indexes:**
- `idx_quiz_attempts_user` on `user_id`
- `idx_quiz_attempts_concept` on `concept_id`

**Foreign Keys:**
- `user_id` → `users(id)`

**Notes:**
- Used to track quiz performance and generate mastery metrics
- LLM feedback provides personalized learning guidance
- `llm_quality_score` ranges from 0-100 (higher is better)

---

### 3. concept_mastery
Tracks learning progress and mastery level for each concept per user.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | Mastery record ID |
| user_id | INTEGER | NOT NULL, FOREIGN KEY → users(id) | User being tracked |
| concept_id | TEXT | NOT NULL | Concept identifier |
| total_attempts | INTEGER | DEFAULT 0 | Total quiz attempts for this concept |
| correct_attempts | INTEGER | DEFAULT 0 | Number of correct attempts |
| avg_quality_score | REAL | DEFAULT 0.0 | Average LLM quality score |
| mastery_level | TEXT | DEFAULT 'novice' | Current mastery: novice/learning/proficient/mastered |
| last_attempt_at | TIMESTAMP | - | Timestamp of most recent attempt |
| updated_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | When record was last updated |

**Constraints:**
- `UNIQUE(user_id, concept_id)` - One mastery record per user per concept

**Indexes:**
- `idx_concept_mastery_user` on `user_id`

**Foreign Keys:**
- `user_id` → `users(id)`

**Mastery Levels:**
- `novice` - Just starting (0-2 correct answers)
- `learning` - Making progress (3-4 correct answers)
- `proficient` - Good understanding (5-7 correct answers)
- `mastered` - Fully mastered (8+ correct answers)

**Notes:**
- Automatically updated after each quiz attempt
- Used for adaptive difficulty and progress tracking

---

### 4. llm_quiz_attempts
Records "Stump the AI" challenge game where students try to create questions the LLM can't answer correctly.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | Challenge attempt ID |
| user_id | INTEGER | NOT NULL, FOREIGN KEY → users(id) | Student who created question |
| module_id | TEXT | NOT NULL | Module identifier |
| question | TEXT | NOT NULL | Student-created question |
| student_answer | TEXT | NOT NULL | Student's answer to their own question |
| llm_answer | TEXT | NOT NULL | LLM's attempt to answer the question |
| student_wins | BOOLEAN | NOT NULL | Whether student stumped the AI (0 or 1) |
| student_answer_correctness | TEXT | NOT NULL | Evaluation of student's answer quality |
| evaluation_explanation | TEXT | - | Explanation of why student won/lost |
| review_status | TEXT | DEFAULT 'auto_approved' | Review state: auto_approved/pending/approved/rejected |
| reviewed_at | TIMESTAMP | - | When admin reviewed (if manual review) |
| reviewed_by | TEXT | - | Admin who reviewed |
| discord_user_id | TEXT | - | Discord ID for notifications |
| created_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | When challenge was created |

**Indexes:**
- `idx_llm_quiz_attempts_user` on `user_id`
- `idx_llm_quiz_attempts_module` on `module_id`
- `idx_llm_quiz_attempts_review_status` on `review_status`

**Foreign Keys:**
- `user_id` → `users(id)`

**Review Status Values:**
- `auto_approved` - Automatically approved by system
- `pending` - Awaiting admin review
- `approved` - Admin approved as valid
- `rejected` - Admin rejected as invalid

**Notes:**
- Review columns (`review_status`, `reviewed_at`, `reviewed_by`, `discord_user_id`) added via migration
- Used for gamification and deeper concept understanding
- Students win if LLM fails to answer correctly

---

### 5. attendance
Records class attendance for in-person or synchronous sessions.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | Attendance record ID |
| user_id | INTEGER | NOT NULL, FOREIGN KEY → users(id) | Student being tracked |
| username | TEXT | NOT NULL | Discord username (for display) |
| timestamp | TEXT | NOT NULL | ISO format timestamp of attendance |
| date_id | TEXT | NOT NULL | Date identifier (YYYY-MM-DD) |
| session_id | TEXT | NOT NULL | Session identifier (e.g., "session01") |
| status | TEXT | DEFAULT 'present' | Attendance status: present/excused |

**Constraints:**
- `UNIQUE(user_id, session_id)` - One attendance record per user per session

**Indexes:**
- `idx_attendance_session` on `session_id`
- `idx_attendance_date` on `date_id`
- `idx_attendance_user` on `user_id`

**Foreign Keys:**
- `user_id` → `users(id)`

**Status Values:**
- `present` - Student was present
- `excused` - Student was absent but excused

**Notes:**
- Links Discord users to physical class attendance
- Used for generating attendance reports
- Exportable to CSV via `/export-attendance` command

---

## Database Relationships

```
users (1) ──< (many) quiz_attempts
users (1) ──< (many) concept_mastery
users (1) ──< (many) llm_quiz_attempts
users (1) ──< (many) attendance
```

## Data Types

**SQLite Type Mappings:**
- `INTEGER` - Whole numbers, booleans (0/1)
- `TEXT` - Strings, JSON, timestamps (ISO format)
- `REAL` - Floating point numbers
- `TIMESTAMP` - Stored as TEXT in ISO format (YYYY-MM-DD HH:MM:SS)
- `BOOLEAN` - Stored as INTEGER (0 = false, 1 = true)

## Schema Migrations

The database uses automatic migrations to add new columns to existing databases:

**Migration 1: LLM Quiz Review Columns**
- Added to `llm_quiz_attempts`:
  - `review_status` TEXT DEFAULT 'auto_approved'
  - `reviewed_at` TIMESTAMP
  - `reviewed_by` TEXT
  - `discord_user_id` TEXT

**Migration 2: Student Registration Columns**
- Added to `users`:
  - `student_id` TEXT
  - `student_name` TEXT

Migrations run automatically on database connection via `Database._run_migrations()`.

## Connection Pattern

```python
from chibi.database.connection import Database

# Initialize
db = Database("data/chibi.db")
await db.connect()

# Use async context manager
async with db.connection.execute(query, params) as cursor:
    rows = await cursor.fetchall()

# Transactions
async with db.connection.execute("BEGIN"):
    # Multiple operations
    await db.connection.commit()

# Close
await db.close()
```

## Backup Considerations

**What to backup:**
- All 5 tables contain student learning progress data
- Tables are independent (no cross-table queries during backup)
- Foreign keys must be preserved during restore

**What NOT to backup:**
- ChromaDB vector database (`data/chromadb/`) - contains course content, not student data
- Can be regenerated from source materials

**Data transformations for Google Sheets export:**
- BOOLEAN (0/1) → TRUE/FALSE
- NULL → empty string
- TIMESTAMP → keep as ISO string
- Long TEXT fields → truncate to 50,000 characters (Sheets limit)

## Query Patterns

**Async queries with parameters:**
```python
# Single row
async with db.connection.execute(
    "SELECT * FROM users WHERE discord_id = ?",
    (discord_id,)
) as cursor:
    row = await cursor.fetchone()

# Multiple rows
async with db.connection.execute(
    "SELECT * FROM quiz_attempts WHERE user_id = ? ORDER BY created_at DESC",
    (user_id,)
) as cursor:
    rows = await cursor.fetchall()

# Insert with RETURNING
async with db.connection.execute(
    "INSERT INTO users (discord_id, username) VALUES (?, ?) RETURNING id",
    (discord_id, username)
) as cursor:
    row = await cursor.fetchone()
    user_id = row["id"]
```

**Always use parameterized queries to prevent SQL injection.**

## Database File Location

- **Path:** `data/chibi.db`
- **Configured in:** `config.yaml` under `database.path`
- **Default:** Creates `data/` directory if it doesn't exist
- **Size:** Typically 50-500 KB depending on usage

## Testing

For tests, use in-memory database:
```python
db = Database(":memory:")
await db.connect()
# Test operations
await db.close()
```

In-memory databases are isolated, fast, and automatically cleaned up after tests.
