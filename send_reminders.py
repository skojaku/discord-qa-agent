"""One-off script to send personalized module reminder DMs to students.

Usage:
    python send_reminders.py m01          # Module 1
    python send_reminders.py m02          # Module 2
    python send_reminders.py m01 --send   # Skip preview confirmation
"""

import argparse
import asyncio
import sqlite3
import os

import discord
import yaml
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")

# Instructor discord IDs to skip
SKIP_DISCORD_IDS = {"1153713967852683294"}  # Sadamori

LLM_QUIZ_TARGET = 2


def load_module_info(module_id, course_path="course.yaml"):
    """Load module name and concepts from course.yaml."""
    with open(course_path) as f:
        course = yaml.safe_load(f)

    for module in course["modules"]:
        if module["id"] == module_id:
            concepts = {c["id"]: c["name"] for c in module.get("concepts", [])}
            return module["name"], concepts

    raise ValueError(f"Module '{module_id}' not found in {course_path}. "
                     f"Available: {[m['id'] for m in course['modules']]}")


def get_student_status(module_id, concept_ids, db_path="data/chibi.db"):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute("SELECT id, discord_id, username, student_name FROM users")
    users = cur.fetchall()

    students = []
    for user_id, discord_id, username, student_name in users:
        if discord_id in SKIP_DISCORD_IDS:
            continue

        display_name = student_name or username

        # Check concept mastery
        placeholders = ",".join("?" for _ in concept_ids)
        cur.execute(
            f"""
            SELECT concept_id, mastery_level
            FROM concept_mastery
            WHERE user_id = ? AND concept_id IN ({placeholders})
            """,
            (user_id, *concept_ids),
        )
        mastery = {row[0]: row[1] for row in cur.fetchall()}

        missing_concepts = [c for c in concept_ids if mastery.get(c) != "mastered"]

        # Check approved LLM quiz wins
        cur.execute(
            """
            SELECT COUNT(*) FROM llm_quiz_attempts
            WHERE user_id = ? AND module_id = ?
              AND student_wins = 1
              AND review_status IN ('approved', 'approved_with_bonus', 'auto_approved')
            """,
            (user_id, module_id),
        )
        approved_wins = cur.fetchone()[0]
        llm_quiz_needed = max(0, LLM_QUIZ_TARGET - approved_wins)

        if missing_concepts or llm_quiz_needed > 0:
            students.append({
                "discord_id": discord_id,
                "display_name": display_name,
                "missing_concepts": missing_concepts,
                "approved_wins": approved_wins,
                "llm_quiz_needed": llm_quiz_needed,
            })

    conn.close()
    return students


def build_message(student, module_id, module_name, concept_names):
    name = student["display_name"]
    missing = student["missing_concepts"]
    llm_needed = student["llm_quiz_needed"]
    llm_wins = student["approved_wins"]
    total_concepts = len(concept_names)

    lines = [
        f"Hi {name},",
        "",
        f"This is a friendly reminder about **{module_name}**. "
        "Here's what you still need to complete:",
        "",
    ]

    task_num = 1

    if missing:
        concept_list = ", ".join(f"**{concept_names[c]}**" for c in missing)
        if len(missing) == total_concepts:
            lines.append(f"{task_num}. **Quiz**: You haven't started the quizzes yet. "
                         f"You need to master all {total_concepts} concepts: {concept_list}. "
                         f"Use `/quiz {module_id}` to get started.")
        else:
            mastered = total_concepts - len(missing)
            lines.append(f"{task_num}. **Quiz**: You've mastered {mastered}/{total_concepts} concepts. "
                         f"Still need to master: {concept_list}. Use `/quiz {module_id}` to continue.")
        task_num += 1

    if llm_needed > 0:
        if llm_wins == 0:
            lines.append(f"{task_num}. **LLM Quiz**: You need at least {LLM_QUIZ_TARGET} approved wins. "
                         f"Use `/llm-quiz module:{module_id}` to challenge the AI with a question from this module.")
        else:
            lines.append(f"{task_num}. **LLM Quiz**: You have {llm_wins}/{LLM_QUIZ_TARGET} approved wins. "
                         f"You need {llm_needed} more. Use `/llm-quiz module:{module_id}` to submit another question.")

    lines.extend([
        "",
        f"You can check your progress anytime with `/status {module_id}`.",
        "",
        "If you have questions, reach out to the TA or the Instructor!",
    ])

    return "\n".join(lines)


async def main():
    parser = argparse.ArgumentParser(description="Send personalized module reminder DMs")
    parser.add_argument("module_id", help="Module ID (e.g., m01, m02)")
    parser.add_argument("--send", action="store_true", help="Skip confirmation prompt")
    parser.add_argument("--db", default="data/chibi.db", help="Path to SQLite database")
    parser.add_argument("--course", default="course.yaml", help="Path to course.yaml")
    args = parser.parse_args()

    module_name, concept_names = load_module_info(args.module_id, args.course)
    concept_ids = list(concept_names.keys())

    print(f"Module: {args.module_id} - {module_name}")
    print(f"Concepts: {', '.join(concept_names.values())}")
    print(f"LLM Quiz target: {LLM_QUIZ_TARGET} approved wins\n")

    students = get_student_status(args.module_id, concept_ids, args.db)

    if not students:
        print(f"All students have completed {module_name}!")
        return

    print(f"Found {len(students)} students who need reminders.\n")

    for s in students:
        msg = build_message(s, args.module_id, module_name, concept_names)
        print(f"--- To: {s['display_name']} (Discord ID: {s['discord_id']}) ---")
        print(msg)
        print()

    if not args.send:
        confirm = input("Send these DMs? (yes/no): ").strip().lower()
        if confirm != "yes":
            print("Aborted.")
            return

    intents = discord.Intents.default()
    intents.members = True
    client = discord.Client(intents=intents)

    @client.event
    async def on_ready():
        print(f"Logged in as {client.user}")
        sent = 0
        failed = 0

        for s in students:
            msg = build_message(s, args.module_id, module_name, concept_names)
            try:
                user = await client.fetch_user(int(s["discord_id"]))
                await user.send(msg)
                print(f"  Sent to {s['display_name']}")
                sent += 1
            except discord.Forbidden:
                print(f"  FAILED (DMs disabled): {s['display_name']}")
                failed += 1
            except Exception as e:
                print(f"  FAILED ({e}): {s['display_name']}")
                failed += 1

            await asyncio.sleep(1)

        print(f"\nDone! Sent: {sent}, Failed: {failed}")
        await client.close()

    await client.start(TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
