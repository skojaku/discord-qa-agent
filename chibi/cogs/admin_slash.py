"""Admin slash commands cog for instructor/admin functionality.

Admin commands use slash commands with administrator permission checks.
These commands are only visible to users with administrator permissions.
"""

import io
import logging
from datetime import datetime
from typing import Optional, TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from ..constants import (
    CSV_FILENAME_PREFIX,
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
        /admin-grade [module] - Generate CSV grade report
        /admin-status <student> [module] - View student progress
        /admin-clear-similarity [module] - Clear similarity database
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
            name="`/admin-grade [module:]`",
            value="Export student grades as CSV file\n*Optional: filter by module ID*",
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
        name="admin-grade",
        description="[ADMIN] Generate CSV report of student grades"
    )
    @app_commands.describe(
        module="Optional: Filter by module ID"
    )
    @app_commands.autocomplete(module=module_autocomplete)
    @app_commands.checks.has_permissions(administrator=True)
    async def show_grade(
        self,
        interaction: discord.Interaction,
        module: Optional[str] = None,
    ):
        """Generate and send a CSV file with student grades."""
        await interaction.response.defer(ephemeral=True, thinking=True)

        # Validate module if specified
        target_module = None
        if module:
            target_module = self.bot.course.get_module(module)
            if not target_module:
                await interaction.followup.send(ERROR_MODULE_NOT_FOUND, ephemeral=True)
                return

        # Generate CSV data using grade service
        csv_content = await self.bot.grade_service.generate_grade_csv(target_module)

        # Create file object
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        module_suffix = f"_{module}" if module else ""
        filename = f"{CSV_FILENAME_PREFIX}{module_suffix}_{timestamp}.csv"

        file = discord.File(
            io.BytesIO(csv_content.encode("utf-8")),
            filename=filename
        )

        # Send the file
        module_info = f" for module **{target_module.name}**" if target_module else ""
        await interaction.followup.send(
            f"Grade report{module_info} generated successfully.",
            file=file,
            ephemeral=True
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

    # Error handlers for permission errors
    @admin_help.error
    @list_modules.error
    @list_students.error
    @show_grade.error
    @student_status.error
    @clear_similarity.error
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
