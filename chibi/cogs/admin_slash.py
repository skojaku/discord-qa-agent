"""Admin slash commands cog for instructor/admin functionality.

Admin commands use slash commands with administrator permission checks.
These commands are only visible to users with administrator permissions.
"""

import asyncio
import logging
from datetime import datetime
from typing import List, Optional, TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from ..constants import (
    DESCRIPTION_TRUNCATE_LENGTH,
    EMBED_FIELD_CHUNK_SIZE,
    ERROR_MODULE_NOT_FOUND,
    ERROR_STUDENT_NOT_FOUND,
    MASTERY_EMOJI,
)
from ..ui import create_progress_bar, truncate_text
from .utils import module_autocomplete_choices

if TYPE_CHECKING:
    from ..bot import ChibiBot
    from ..content.course import Module
    from ..database.models import User

logger = logging.getLogger(__name__)


class AdminSlashCog(commands.Cog):
    """Cog for admin-only slash commands.

    Commands:
        /admin-help - Show admin commands help
        /admin-modules - List available modules
        /admin-students - List registered students
        /admin-export-grade [module] - Export grades to Google Sheets
        /admin-status <student> [module] - View student progress
        /admin-clear-similarity [module] - Clear similarity database
        /admin-remind <module> [preview] - Send reminder DMs to students with incomplete work
    """

    def __init__(self, bot: "ChibiBot"):
        self.bot = bot

    async def module_autocomplete(
        self, interaction: discord.Interaction, current: str
    ):
        """Autocomplete callback for module selection."""
        try:
            return await module_autocomplete_choices(self.bot.course, current)
        except discord.errors.HTTPException as e:
            # Silently handle "Interaction has already been acknowledged" errors
            # This can happen due to Discord rate limiting or timing issues
            if e.code == 40060:  # Interaction already acknowledged
                logger.debug(f"Autocomplete interaction already acknowledged: {e}")
                return []
            raise

    @app_commands.command(
        name="admin-help",
        description="[ADMIN] Show admin commands help and system stats"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def admin_help(self, interaction: discord.Interaction):
        """Show admin commands, available modules, and registered students."""
        await interaction.response.defer(ephemeral=True, thinking=True)

        embed = discord.Embed(
            title="Admin Commands",
            description="Use these commands to manage and monitor student progress.",
            color=discord.Color.blue(),
        )

        # Commands as individual fields for better readability
        embed.add_field(
            name="`/admin-help`",
            value="Show this help message",
            inline=False,
        )
        embed.add_field(
            name="`/admin-modules`",
            value="List all available modules with details",
            inline=False,
        )
        embed.add_field(
            name="`/admin-students`",
            value="List all registered students with activity info",
            inline=False,
        )
        embed.add_field(
            name="`/admin-export-grade [module:]`",
            value="Export student grades to Google Sheets\n*Optional: filter by module ID*",
            inline=False,
        )
        embed.add_field(
            name="`/admin-status student: [module:]`",
            value="View a student's learning progress\n*Use Discord user picker to select student*",
            inline=False,
        )
        embed.add_field(
            name="`/admin-clear-similarity [module:]`",
            value="Clear LLM Quiz similarity database\n*Optional: specify module to clear only that module*",
            inline=False,
        )
        embed.add_field(
            name="`/admin-remind module: [preview:]`",
            value="Send reminder DMs to students with incomplete work\n*Use preview:True to see who would be reminded without sending*",
            inline=False,
        )
        embed.add_field(
            name="`/admin-resend-reviews`",
            value="Re-send review dropdowns for all pending LLM quiz submissions\n*Use this if review buttons stopped working*",
            inline=False,
        )

        # Attendance commands section
        embed.add_field(
            name="Attendance Commands",
            value=(
                "`/admin-open-attendance` - Start attendance session\n"
                "`/admin-close-attendance` - Close attendance session\n"
                "`/admin-export-attendance` - Export attendance CSV\n"
                "`/admin-excuse` - Mark student excused\n"
                "`/admin-mark-present` - Manually mark present\n"
                "`/admin-remove-attendance` - Remove attendance record"
            ),
            inline=False,
        )

        # Quick stats
        modules = self.bot.course.modules
        users = await self.bot.user_repo.get_all()
        embed.add_field(
            name="Quick Stats",
            value=f"**{len(modules)}** modules | **{len(users)}** students registered",
            inline=False,
        )

        embed.set_footer(text="Use /admin-modules or /admin-students for detailed lists")
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(
        name="admin-modules",
        description="[ADMIN] List all available course modules"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def list_modules(self, interaction: discord.Interaction):
        """List all available modules."""
        await interaction.response.defer(ephemeral=True, thinking=True)

        modules = self.bot.course.modules
        if not modules:
            await interaction.followup.send("No modules configured.", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"Available Modules ({len(modules)})",
            color=discord.Color.green(),
        )

        for m in modules:
            concept_count = len(m.concepts) if m.concepts else 0
            description = truncate_text(
                m.description, DESCRIPTION_TRUNCATE_LENGTH
            ) if m.description else "No description"
            embed.add_field(
                name=f"`{m.id}` - {m.name}",
                value=f"{description}\n*{concept_count} concepts*",
                inline=False,
            )

        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(
        name="admin-students",
        description="[ADMIN] List all registered students with activity info"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def list_students(self, interaction: discord.Interaction):
        """List all registered students."""
        await interaction.response.defer(ephemeral=True, thinking=True)

        users = await self.bot.user_repo.get_all()

        if not users:
            await interaction.followup.send("No students registered yet.", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"Registered Students ({len(users)})",
            color=discord.Color.green(),
        )

        # Build student list with activity info
        lines = []
        for u in users:
            last_active = u.last_active.strftime("%Y-%m-%d") if u.last_active else "Never"
            lines.append(f"`{u.discord_id}` - **{u.username}** (Last: {last_active})")

        # Split into chunks if too many students (embed field limit is 1024 chars)
        for i in range(0, len(lines), EMBED_FIELD_CHUNK_SIZE):
            chunk = lines[i:i + EMBED_FIELD_CHUNK_SIZE]
            field_name = "Students" if i == 0 else f"Students (cont.)"
            embed.add_field(
                name=field_name,
                value="\n".join(chunk),
                inline=False,
            )

        embed.set_footer(text="Use /admin-status to view a student's progress")
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(
        name="admin-export-grade",
        description="[ADMIN] Export student grades to Google Sheets"
    )
    @app_commands.describe(
        module="Optional: Filter by module ID"
    )
    @app_commands.autocomplete(module=module_autocomplete)
    @app_commands.checks.has_permissions(administrator=True)
    async def export_grade(
        self,
        interaction: discord.Interaction,
        module: Optional[str] = None,
    ):
        """Export student grades to a Google Sheets spreadsheet."""
        await interaction.response.defer(ephemeral=True, thinking=True)

        # Validate module if specified
        target_module = None
        if module:
            target_module = self.bot.course.get_module(module)
            if not target_module:
                await interaction.followup.send(ERROR_MODULE_NOT_FOUND, ephemeral=True)
                return

        # Check backup service is available
        if not self.bot.backup_service or not self.bot.backup_service.sheets_client:
            await interaction.followup.send(
                "Google Sheets is not configured. Check backup settings.",
                ephemeral=True,
            )
            return

        try:
            # Generate grade data
            sheet_data = await self.bot.grade_service.generate_grade_sheet_data(
                target_module
            )

            # Create spreadsheet
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            module_suffix = f"_{module}" if module else "_all"
            title = f"grades{module_suffix}_{timestamp}"

            sheets_client = self.bot.backup_service.sheets_client
            spreadsheet_id = sheets_client.create_spreadsheet(title)

            # Write data to the default "Sheet1"
            sheets_client.write_sheet(spreadsheet_id, "Sheet1", sheet_data)

            # Move to configured folder if available
            folder_name = self.bot.backup_service.folder_name
            if folder_name:
                try:
                    folder_id = sheets_client.find_or_create_folder(folder_name)
                    sheets_client.move_spreadsheet_to_folder(
                        spreadsheet_id, folder_id
                    )
                except Exception as e:
                    logger.warning(f"Failed to move grade spreadsheet to folder: {e}")

            spreadsheet_url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}"
            module_info = (
                f" for module **{target_module.name}**" if target_module else ""
            )
            await interaction.followup.send(
                f"Grade report{module_info} exported successfully.\n{spreadsheet_url}",
                ephemeral=True,
            )

            logger.info(
                f"Admin {interaction.user.display_name} exported grades "
                f"(module={module}, spreadsheet={spreadsheet_id})"
            )

        except Exception as e:
            logger.error(f"Error exporting grades: {e}", exc_info=True)
            await interaction.followup.send(
                f"Failed to export grades: {str(e)}",
                ephemeral=True,
            )

    @app_commands.command(
        name="admin-status",
        description="[ADMIN] View a student's learning progress"
    )
    @app_commands.describe(
        student="Select a student from the server",
        module="Optional: Module for detailed progress"
    )
    @app_commands.autocomplete(module=module_autocomplete)
    @app_commands.checks.has_permissions(administrator=True)
    async def student_status(
        self,
        interaction: discord.Interaction,
        student: discord.User,
        module: Optional[str] = None,
    ):
        """Show learning status for a specific student."""
        await interaction.response.defer(ephemeral=True, thinking=True)

        # Look up the student by Discord ID
        user = await self.bot.user_repo.get_by_discord_id(str(student.id))
        if not user:
            await interaction.followup.send(
                f"User {student.mention} hasn't taken any quizzes yet. "
                "They need to use `/quiz` first to appear in the system.",
                ephemeral=True
            )
            return

        # Validate module if specified
        target_module = None
        if module:
            target_module = self.bot.course.get_module(module)
            if not target_module:
                await interaction.followup.send(ERROR_MODULE_NOT_FOUND, ephemeral=True)
                return

        # Build the appropriate embed
        if target_module is None:
            embed = await self._build_student_summary_embed(user)
        else:
            embed = await self._build_student_module_embed(user, target_module)

        await interaction.followup.send(embed=embed, ephemeral=True)

    async def _build_student_summary_embed(self, user: "User") -> discord.Embed:
        """Build summary status embed for a student."""
        # Get mastery records and config
        mastery_records = await self.bot.mastery_repo.get_all_for_user(user.id)
        mastery_by_concept = {m.concept_id: m for m in mastery_records}
        min_attempts = self.bot.config.mastery.min_attempts_for_mastery

        embed = discord.Embed(
            title=f"📊 Learning Progress - {user.username}",
            description=f"Discord ID: `{user.discord_id}`",
            color=discord.Color.blue(),
        )

        # Quiz stats (fetched from quiz_attempts table)
        total_quizzes = await self.bot.quiz_repo.count_for_user(user.id)
        correct = await self.bot.quiz_repo.count_correct_for_user(user.id)
        accuracy = correct / total_quizzes * 100 if total_quizzes > 0 else 0

        embed.add_field(
            name="Quiz Performance",
            value=f"**{total_quizzes}** quizzes taken\n"
            f"**{accuracy:.1f}%** accuracy",
            inline=True,
        )

        # Calculate overall passed/required
        total_passed = 0
        total_required = 0

        # Module progress bars
        module_lines = []
        for module in self.bot.course.modules:
            module_passed = 0
            module_required = len(module.concepts) * min_attempts

            for concept in module.concepts:
                mastery = mastery_by_concept.get(concept.id)
                if mastery:
                    # Cap correct_attempts at min_attempts per concept
                    module_passed += min(mastery.correct_attempts, min_attempts)

            total_passed += module_passed
            total_required += module_required

            # Create progress bar for this module
            progress_bar = create_progress_bar(module_passed, module_required)
            module_lines.append(f"**{module.name}**\n`{progress_bar}`")

        # Overall progress
        overall_pct = total_passed / total_required * 100 if total_required > 0 else 0
        embed.add_field(
            name="Overall Progress",
            value=f"**{overall_pct:.1f}%** complete ({total_passed}/{total_required} quizzes passed)",
            inline=True,
        )

        # Module breakdown
        embed.add_field(
            name="Module Progress",
            value="\n".join(module_lines) if module_lines else "No modules available",
            inline=False,
        )

        # Activity info
        if user.last_active:
            embed.add_field(
                name="Last Active",
                value=user.last_active.strftime("%Y-%m-%d %H:%M UTC"),
                inline=True,
            )

        embed.set_footer(text="Use /admin-status with module parameter for detailed module progress")

        return embed

    async def _build_student_module_embed(
        self, user: "User", module: "Module"
    ) -> discord.Embed:
        """Build detailed status embed for a specific module."""
        embed = discord.Embed(
            title=f"📚 {module.name} - {user.username}",
            description=f"Discord ID: `{user.discord_id}`"
            + (f"\n{module.description}" if module.description else ""),
            color=discord.Color.blue(),
        )

        # Get mastery records and config
        mastery_records = await self.bot.mastery_repo.get_all_for_user(user.id)
        mastery_by_concept = {m.concept_id: m for m in mastery_records}
        min_attempts = self.bot.config.mastery.min_attempts_for_mastery

        # Calculate module progress
        module_passed = 0
        module_required = len(module.concepts) * min_attempts

        concept_lines = []
        for concept in module.concepts:
            mastery = mastery_by_concept.get(concept.id)
            if mastery:
                # Cap correct_attempts at min_attempts per concept
                capped_correct = min(mastery.correct_attempts, min_attempts)
                module_passed += capped_correct

                emoji = MASTERY_EMOJI.get(mastery.mastery_level, "⬜")
                concept_lines.append(
                    f"{emoji} **{concept.name}** ({capped_correct}/{min_attempts} passed)"
                )
            else:
                concept_lines.append(f"⬜ {concept.name} (0/{min_attempts} passed)")

        # Module summary with progress bar
        progress_bar = create_progress_bar(module_passed, module_required)
        progress_pct = module_passed / module_required * 100 if module_required > 0 else 0
        embed.add_field(
            name="Module Progress",
            value=f"```\n{progress_bar}\n```\n"
            f"**{progress_pct:.1f}%** complete ({module_passed}/{module_required} quizzes passed)",
            inline=False,
        )

        # Concept details
        if concept_lines:
            embed.add_field(
                name="Concepts",
                value="\n".join(concept_lines),
                inline=False,
            )

        embed.set_footer(text="Use /admin-status without module for overall summary")

        return embed

    @app_commands.command(
        name="admin-clear-similarity",
        description="[ADMIN] Clear questions from LLM Quiz similarity database"
    )
    @app_commands.describe(
        module="Optional: Specific module to clear (leave empty to clear all)"
    )
    @app_commands.autocomplete(module=module_autocomplete)
    @app_commands.checks.has_permissions(administrator=True)
    async def clear_similarity(
        self,
        interaction: discord.Interaction,
        module: Optional[str] = None
    ):
        """Clear questions from the LLM Quiz similarity database.

        This removes stored questions used for duplicate detection,
        allowing previously submitted questions to be used again.
        """
        await interaction.response.defer(ephemeral=True, thinking=True)

        if not hasattr(self.bot, 'similarity_service') or self.bot.similarity_service is None:
            await interaction.followup.send(
                "Similarity service is not configured.",
                ephemeral=True
            )
            return

        try:
            if module:
                # Clear specific module
                count = await self.bot.similarity_service.similarity_repo.clear_module(module)
                await interaction.followup.send(
                    f"✅ Cleared **{count}** questions from module `{module}`",
                    ephemeral=True
                )
            else:
                # Clear all
                count = await self.bot.similarity_service.similarity_repo.clear_all()
                await interaction.followup.send(
                    f"✅ Cleared **{count}** questions from all modules",
                    ephemeral=True
                )

            logger.info(
                f"Admin {interaction.user.display_name} cleared similarity database "
                f"(module={module}, count={count})"
            )

        except Exception as e:
            logger.error(f"Error clearing similarity database: {e}", exc_info=True)
            await interaction.followup.send(
                f"❌ Error clearing similarity database: {str(e)}",
                ephemeral=True
            )

    async def _get_students_needing_reminders(
        self, guild: discord.Guild, module: "Module"
    ) -> List[dict]:
        """Get students who have incomplete work for a module."""
        users = await self.bot.user_repo.get_all()
        concept_ids = [c.id for c in module.concepts]
        target_wins = self.bot.llm_quiz_service.target_wins_per_module
        students = []

        for user in users:
            # Skip server admins
            member = guild.get_member(int(user.discord_id))
            if member and member.guild_permissions.administrator:
                continue

            # Check concept mastery
            mastery_records = await self.bot.mastery_repo.get_by_concepts(
                user.id, concept_ids
            )
            mastery_by_concept = {m.concept_id: m for m in mastery_records}
            missing_concepts = [
                c for c in concept_ids
                if mastery_by_concept.get(c) is None
                or mastery_by_concept[c].mastery_level != "mastered"
            ]

            # Check LLM quiz wins
            approved_wins = await self.bot.llm_quiz_repo.count_wins_for_module(
                user.id, module.id
            )
            llm_quiz_needed = max(0, target_wins - approved_wins)

            if missing_concepts or llm_quiz_needed > 0:
                students.append({
                    "discord_id": user.discord_id,
                    "display_name": user.student_name or user.username,
                    "missing_concepts": missing_concepts,
                    "approved_wins": approved_wins,
                    "llm_quiz_needed": llm_quiz_needed,
                })

        return students

    def _build_reminder_message(
        self, student: dict, module: "Module", concept_names: dict
    ) -> str:
        """Build a personalized reminder DM for a student."""
        name = student["display_name"]
        missing = student["missing_concepts"]
        llm_needed = student["llm_quiz_needed"]
        llm_wins = student["approved_wins"]
        target_wins = self.bot.llm_quiz_service.target_wins_per_module
        total_concepts = len(concept_names)

        lines = [
            f"Hi {name},",
            "",
            f"This is a friendly reminder about **{module.name}**. "
            "Here's what you still need to complete:",
            "",
        ]

        task_num = 1

        if missing:
            concept_list = ", ".join(
                f"**{concept_names[c]}**" for c in missing
            )
            if len(missing) == total_concepts:
                lines.append(
                    f"{task_num}. **Quiz**: You haven't started the quizzes yet. "
                    f"You need to master all {total_concepts} concepts: {concept_list}. "
                    f"Use `/quiz {module.id}` to get started."
                )
            else:
                mastered = total_concepts - len(missing)
                lines.append(
                    f"{task_num}. **Quiz**: You've mastered {mastered}/{total_concepts} concepts. "
                    f"Still need to master: {concept_list}. "
                    f"Use `/quiz {module.id}` to continue."
                )
            task_num += 1

        if llm_needed > 0:
            if llm_wins == 0:
                lines.append(
                    f"{task_num}. **LLM Quiz**: You need at least {target_wins} approved wins. "
                    f"Use `/llm-quiz module:{module.id}` to challenge the AI with a question from this module."
                )
            else:
                lines.append(
                    f"{task_num}. **LLM Quiz**: You have {llm_wins}/{target_wins} approved wins. "
                    f"You need {llm_needed} more. "
                    f"Use `/llm-quiz module:{module.id}` to submit another question."
                )

        lines.extend([
            "",
            f"You can check your progress anytime with `/status {module.id}`.",
            "",
            "If you have questions, reach out to the TA or the Instructor!",
        ])

        return "\n".join(lines)

    @app_commands.command(
        name="admin-remind",
        description="[ADMIN] Send reminder DMs to students with incomplete work"
    )
    @app_commands.describe(
        module="Module ID",
        preview="Preview only, don't send DMs"
    )
    @app_commands.autocomplete(module=module_autocomplete)
    @app_commands.checks.has_permissions(administrator=True)
    async def send_reminders(
        self,
        interaction: discord.Interaction,
        module: str,
        preview: bool = False,
    ):
        """Send reminder DMs to students with incomplete module work."""
        await interaction.response.defer(ephemeral=True, thinking=True)

        # Validate module
        target_module = self.bot.course.get_module(module)
        if not target_module:
            await interaction.followup.send(ERROR_MODULE_NOT_FOUND, ephemeral=True)
            return

        # Build concept name mapping
        concept_names = {c.id: c.name for c in target_module.concepts}

        # Get students needing reminders
        students = await self._get_students_needing_reminders(
            interaction.guild, target_module
        )

        if not students:
            await interaction.followup.send(
                f"All students have completed **{target_module.name}**!",
                ephemeral=True,
            )
            return

        # Build preview
        preview_lines = [
            f"**{target_module.name}** — {len(students)} student(s) need reminders:\n"
        ]
        for s in students:
            parts = []
            if s["missing_concepts"]:
                names = ", ".join(concept_names[c] for c in s["missing_concepts"])
                parts.append(f"quiz: {names}")
            if s["llm_quiz_needed"] > 0:
                parts.append(f"llm-quiz: {s['llm_quiz_needed']} more win(s)")
            preview_lines.append(f"• **{s['display_name']}** — {'; '.join(parts)}")

        preview_text = "\n".join(preview_lines)

        if preview:
            await interaction.followup.send(preview_text, ephemeral=True)
            return

        # Send DMs
        sent = 0
        failed = 0
        failed_names = []

        for s in students:
            msg = self._build_reminder_message(s, target_module, concept_names)
            try:
                user = await self.bot.fetch_user(int(s["discord_id"]))
                await user.send(msg)
                sent += 1
            except Exception as e:
                logger.warning(f"Failed to DM {s['display_name']}: {e}")
                failed += 1
                failed_names.append(s["display_name"])
            await asyncio.sleep(1)

        # Report results
        result_lines = [f"Sent **{sent}** reminder(s) for **{target_module.name}**."]
        if failed:
            result_lines.append(
                f"Failed to send to **{failed}** student(s): {', '.join(failed_names)}"
            )
        await interaction.followup.send("\n".join(result_lines), ephemeral=True)

        logger.info(
            f"Admin {interaction.user.display_name} sent reminders for {module} "
            f"(sent={sent}, failed={failed})"
        )

    @app_commands.command(
        name="admin-resend-reviews",
        description="[ADMIN] Re-send review messages for all pending LLM quiz submissions"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def resend_reviews(self, interaction: discord.Interaction):
        """Re-send fresh review dropdowns for all PENDING LLM quiz attempts."""
        await interaction.response.defer(ephemeral=True, thinking=True)

        admin_channel_id = self.bot.config.discord.admin_channel_id
        if not admin_channel_id:
            await interaction.followup.send(
                "Admin channel is not configured.", ephemeral=True
            )
            return

        try:
            admin_channel = self.bot.get_channel(admin_channel_id)
            if not admin_channel:
                admin_channel = await self.bot.fetch_channel(admin_channel_id)
        except Exception as e:
            await interaction.followup.send(
                f"Could not find admin channel: {e}", ephemeral=True
            )
            return

        pending = await self.bot.llm_quiz_repo.get_pending_reviews()
        if not pending:
            await interaction.followup.send("No pending reviews found.", ephemeral=True)
            return

        # Import here to avoid circular imports
        from ..ui.views.admin_review import AdminReviewView, build_review_request_embed
        from ..cogs.llm_quiz import LLMQuizCog

        llm_quiz_cog = self.bot.cogs.get("LLMQuizCog")
        if not llm_quiz_cog:
            await interaction.followup.send(
                "LLMQuizCog not found — cannot re-send reviews.", ephemeral=True
            )
            return

        sent = 0
        for attempt in pending:
            try:
                module = self.bot.course.get_module(attempt.module_id)
                module_name = module.name if module else attempt.module_id

                # Look up the student username
                user_record = await self.bot.user_repo.get_by_discord_id(str(attempt.discord_user_id)) if attempt.discord_user_id else None
                student_username = user_record.username if user_record else str(attempt.discord_user_id or attempt.user_id)

                embed = build_review_request_embed(
                    attempt=attempt,
                    student_username=student_username,
                    module_name=module_name,
                )
                view = AdminReviewView(
                    attempt_id=attempt.id,
                    on_review_callback=llm_quiz_cog.handle_review_decision,
                )
                await admin_channel.send(embed=embed, view=view)
                sent += 1
            except Exception as e:
                logger.error(f"Failed to re-send review for attempt #{attempt.id}: {e}", exc_info=True)

        await interaction.followup.send(
            f"Re-sent **{sent}** pending review(s) to <#{admin_channel_id}>.",
            ephemeral=True,
        )
        logger.info(
            f"Admin {interaction.user.display_name} re-sent {sent} pending review(s)"
        )

    # Error handlers for permission errors
    @admin_help.error
    @list_modules.error
    @list_students.error
    @export_grade.error
    @student_status.error
    @clear_similarity.error
    @send_reminders.error
    @resend_reviews.error
    async def admin_command_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ):
        """Handle errors for admin commands."""
        if isinstance(error, app_commands.errors.MissingPermissions):
            try:
                await interaction.response.send_message(
                    "❌ You need administrator permissions to use admin commands.",
                    ephemeral=True,
                )
            except discord.InteractionResponded:
                await interaction.followup.send(
                    "❌ You need administrator permissions to use admin commands.",
                    ephemeral=True,
                )
        else:
            logger.error(f"Admin command error: {error}", exc_info=True)
            try:
                await interaction.response.send_message(
                    "❌ An error occurred. Please try again or check the logs.",
                    ephemeral=True,
                )
            except discord.InteractionResponded:
                await interaction.followup.send(
                    "❌ An error occurred. Please try again or check the logs.",
                    ephemeral=True,
                )


async def setup(bot: "ChibiBot"):
    """Set up the Admin Slash cog."""
    await bot.add_cog(AdminSlashCog(bot))
