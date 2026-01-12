# Manual E2E Testing: Google Sheets Backup Feature

 Ralph Agent Instructions

## Your Task

1. Read `prd.json`
2. Read `progress.txt`
   (check Codebase Patterns first)
3. Check you're on the correct branch
4. Pick highest priority story 
   where `passes: false`
5. Implement that ONE story
6. Run typecheck and tests
7. Update CLAUDE.md files with learnings
8. Commit: `feat: [ID] - [Title]`
9. Update prd.json: `passes: true`
10. Append learnings to progress.txt

## Critical Files

**prd.json** - Your test scenario list with pass/fail status

**DATABASE_STRUCTURE.md** - Database schema reference for verifying data

**data/chibi.db** - SQLite database to backup/restore

**google-credentials.json** - Service account credentials for Google Sheets API

## Progress Format

APPEND to progress.txt:

## [Date] - [Story ID]
- What was implemented
- Files changed
- **Learnings:**
  - Patterns discovered
  - Gotchas encountered
---

## Codebase Patterns

Add reusable patterns to the TOP 
of progress.txt:

## Codebase Patterns
- Migrations: Use IF NOT EXISTS
- React: useRef<Timeout | null>(null)

## Stop Condition

If ALL stories pass, reply:
<promise>COMPLETE</promise>

Otherwise end normally.
