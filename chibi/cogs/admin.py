"""Admin commands cog for instructor/admin functionality."""

import csv
import io
import logging
from datetime import datetime
from typing import List, Optional, TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from ..constants import (
    CSV_FILENAME_PREFIX,
    DISCORD_AUTOCOMPLETE_LIMIT,
    ERROR_ADMIN_CHANNEL_NOT_CONFIGURED,
    ERROR_ADMIN_CHANNEL_ONLY,
    ERROR_ADMIN_ONLY,
    ERROR_MODULE_NOT_FOUND,
    ERROR_SHOW_GRADE,
    ERROR_STUDENT_NOT_FOUND,
    ERROR_STUDENT_STATUS,
    MASTERY_EMOJI,
    MASTERY_MASTERED,
    MASTERY_PROFICIENT,
    PROGRESS_BAR_LENGTH,
)
from .utils import defer_interaction, module_autocomplete_choices, send_error_response

if TYPE_CHECKING:
    from ..bot import ChibiBot
    from ..content.course import Module
    from ..database.models import User

logger = logging.getLogger(__name__)


def is_admin_channel(bot: "ChibiBot", channel: discord.abc.GuildChannel) -> bool:
    """Check if the channel is the configured admin channel.

    Args:
        bot: The bot instance
        channel: The channel to check

    Returns:
        True if the channel matches the configured admin_channel_id
    """
    admin_channel_id = bot.config.discord.admin_channel_id
    if admin_channel_id is None:
        return False
    return channel.id == admin_channel_id


class AdminCog(commands.Cog):
    """Cog for admin-only commands."""

    def __init__(self, bot: "ChibiBot"):
        self.bot = bot

    async def _check_admin_permissions(
        self, interaction: discord.Interaction
    ) -> Optional[str]:
        """Check if user has admin permissions and is in admin channel.

        Args:
            interaction: The Discord interaction

        Returns:
            Error message if check fails, None if all checks pass
        """
        # Check if user is an administrator
        if not interaction.user.guild_permissions.administrator:
            return ERROR_ADMIN_ONLY

        # Check if admin channel is configured
        admin_channel_id = self.bot.config.discord.admin_channel_id
        if admin_channel_id is None:
            return ERROR_ADMIN_CHANNEL_NOT_CONFIGURED

        # Check if command is used in admin channel
        if not is_admin_channel(self.bot, interaction.channel):
            return f"{ERROR_ADMIN_CHANNEL_ONLY} Please use <#{admin_channel_id}>."

        return None

    @app_commands.command(
        name="show_grade",
        description="Generate a CSV report of student grades (Admin only)"
    )
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(
        module="Filter by specific module (optional)"
    )
    @defer_interaction(thinking=True)
    async def show_grade(
        self,
        interaction: discord.Interaction,
        module: Optional[str] = None,
    ):
        """Generate and send a CSV file with student grades.

        The CSV includes:
        - Student ID (Discord ID)
        - Username
        - Completed concepts
        - Percentage of completion per module
        """
        try:
            # Check admin permissions
            error = await self._check_admin_permissions(interaction)
            if error:
                await interaction.followup.send(error, ephemeral=True)
                return

            # Validate module if specified
            target_module = None
            if module:
                target_module = self.bot.course.get_module(module)
                if not target_module:
                    await interaction.followup.send(ERROR_MODULE_NOT_FOUND, ephemeral=True)
                    return

            # Generate CSV data
            csv_content = await self._generate_grade_csv(target_module)

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
                file=file
            )

        except Exception as e:
            await send_error_response(
                interaction, ERROR_SHOW_GRADE, logger, e, "/show_grade command"
            )

    async def _generate_grade_csv(
        self,
        target_module=None,
    ) -> str:
        """Generate CSV content with student grades.

        Args:
            target_module: If specified, only include data for this module

        Returns:
            CSV content as a string
        """
        # Get all users
        users = await self.bot.repository.get_all_users()

        # Get course modules info
        if target_module:
            modules = [target_module]
        else:
            modules = self.bot.course.modules

        # Build CSV headers
        headers = ["discord_id", "username"]

        # Add columns for each module: completed concepts and completion percentage
        for mod in modules:
            headers.append(f"{mod.id}_completed_concepts")
            headers.append(f"{mod.id}_completion_pct")

        # Add overall columns if showing all modules
        if not target_module:
            headers.append("total_completed_concepts")
            headers.append("overall_completion_pct")

        # Create CSV writer
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(headers)

        # Process each user
        for user in users:
            row = [user.discord_id, user.username]

            # Get user's mastery records
            mastery_records = await self.bot.repository.get_user_mastery_all(user.id)
            mastery_by_concept = {m.concept_id: m for m in mastery_records}

            total_completed = 0
            total_concepts = 0

            for mod in modules:
                module_concepts = mod.concepts
                total_concepts += len(module_concepts)

                # Count completed concepts (proficient or mastered)
                completed_concepts = []
                for concept in module_concepts:
                    mastery = mastery_by_concept.get(concept.id)
                    if mastery and mastery.mastery_level in (MASTERY_PROFICIENT, MASTERY_MASTERED):
                        completed_concepts.append(concept.id)

                completed_count = len(completed_concepts)
                total_completed += completed_count

                # Calculate completion percentage for this module
                completion_pct = (
                    (completed_count / len(module_concepts) * 100)
                    if module_concepts else 0
                )

                # Add module data to row
                row.append(";".join(completed_concepts) if completed_concepts else "")
                row.append(f"{completion_pct:.1f}")

            # Add overall totals if showing all modules
            if not target_module:
                all_completed = []
                for mod in modules:
                    for concept in mod.concepts:
                        mastery = mastery_by_concept.get(concept.id)
                        if mastery and mastery.mastery_level in (MASTERY_PROFICIENT, MASTERY_MASTERED):
                            all_completed.append(concept.id)

                overall_pct = (
                    (len(all_completed) / total_concepts * 100)
                    if total_concepts > 0 else 0
                )

                row.append(";".join(all_completed) if all_completed else "")
                row.append(f"{overall_pct:.1f}")

            writer.writerow(row)

        return output.getvalue()

    @show_grade.autocomplete("module")
    async def module_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        """Provide autocomplete choices for module selection."""
        return await module_autocomplete_choices(self.bot.course, current)

    @app_commands.command(
        name="_status",
        description="View a student's learning progress (Admin only)"
    )
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(
        student="Student Discord ID or username",
        module="Module to show detailed progress for (leave empty for summary)",
    )
    @defer_interaction(thinking=True)
    async def student_status(
        self,
        interaction: discord.Interaction,
        student: str,
        module: Optional[str] = None,
    ):
        """Show learning status for a specific student.

        Args:
            interaction: The Discord interaction
            student: Student Discord ID or username to look up
            module: Optional module to show detailed progress for
        """
        try:
            # Check admin permissions
            error = await self._check_admin_permissions(interaction)
            if error:
                await interaction.followup.send(error, ephemeral=True)
                return

            # Look up the student
            user = await self.bot.repository.search_user_by_identifier(student)
            if not user:
                await interaction.followup.send(ERROR_STUDENT_NOT_FOUND, ephemeral=True)
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

            await interaction.followup.send(embed=embed)

        except Exception as e:
            await send_error_response(
                interaction, ERROR_STUDENT_STATUS, logger, e, "/_status command"
            )

    async def _build_student_summary_embed(self, user: "User") -> discord.Embed:
        """Build summary status embed for a student."""
        summary = await self.bot.repository.get_mastery_summary(user.id)
        total_concepts = len(self.bot.course.get_all_concepts())

        embed = discord.Embed(
            title=f"📊 Learning Progress - {user.username}",
            description=f"Discord ID: `{user.discord_id}`",
            color=discord.Color.blue(),
        )

        # Overall progress
        mastered = summary.get("mastered", 0)
        proficient = summary.get("proficient", 0)
        progress_pct = (
            (mastered + proficient) / total_concepts * 100 if total_concepts > 0 else 0
        )

        embed.add_field(
            name="Overall Progress",
            value=f"**{progress_pct:.1f}%** complete\n"
            f"({mastered + proficient}/{total_concepts} concepts)",
            inline=True,
        )

        # Quiz stats
        total_quizzes = summary.get("total_quiz_attempts", 0)
        correct = summary.get("total_correct", 0)
        accuracy = correct / total_quizzes * 100 if total_quizzes > 0 else 0

        embed.add_field(
            name="Quiz Performance",
            value=f"**{total_quizzes}** quizzes taken\n"
            f"**{accuracy:.1f}%** accuracy",
            inline=True,
        )

        # Mastery breakdown
        mastery_bar = self._create_progress_bar(
            mastered, proficient, summary.get("learning", 0), summary.get("novice", 0)
        )
        embed.add_field(
            name="Mastery Levels",
            value=f"```\n{mastery_bar}\n```\n"
            f"🏆 Mastered: {mastered}\n"
            f"⭐ Proficient: {proficient}\n"
            f"📖 Learning: {summary.get('learning', 0)}\n"
            f"🌱 Novice: {summary.get('novice', 0)}",
            inline=False,
        )

        # Activity info
        if user.last_active:
            embed.add_field(
                name="Last Active",
                value=user.last_active.strftime("%Y-%m-%d %H:%M UTC"),
                inline=True,
            )

        embed.set_footer(text="Use /_status <student> <module> for detailed module progress")

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

        # Get all mastery records for this user
        mastery_records = await self.bot.repository.get_user_mastery_all(user.id)
        mastery_by_concept = {m.concept_id: m for m in mastery_records}

        # Module progress stats
        total_concepts = len(module.concepts)
        started_count = 0
        mastered_count = 0
        proficient_count = 0

        concept_lines = []
        for concept in module.concepts:
            mastery = mastery_by_concept.get(concept.id)
            if mastery:
                started_count += 1
                if mastery.mastery_level == "mastered":
                    mastered_count += 1
                elif mastery.mastery_level == "proficient":
                    proficient_count += 1

                emoji = MASTERY_EMOJI.get(mastery.mastery_level, "⬜")
                accuracy = (
                    mastery.correct_attempts / mastery.total_attempts * 100
                    if mastery.total_attempts > 0
                    else 0
                )
                concept_lines.append(
                    f"{emoji} **{concept.name}** ({accuracy:.0f}% - {mastery.total_attempts} attempts)"
                )
            else:
                concept_lines.append(f"⬜ {concept.name} (not started)")

        # Module summary
        progress_pct = (
            (mastered_count + proficient_count) / total_concepts * 100
            if total_concepts > 0
            else 0
        )
        embed.add_field(
            name="Module Progress",
            value=f"**{progress_pct:.1f}%** complete ({mastered_count + proficient_count}/{total_concepts})\n"
            f"🏆 Mastered: {mastered_count} | ⭐ Proficient: {proficient_count} | Started: {started_count}/{total_concepts}",
            inline=False,
        )

        # Concept details
        if concept_lines:
            embed.add_field(
                name="Concepts",
                value="\n".join(concept_lines),
                inline=False,
            )

        embed.set_footer(text="Use /_status <student> for overall summary")

        return embed

    def _create_progress_bar(
        self, mastered: int, proficient: int, learning: int, novice: int
    ) -> str:
        """Create a visual progress bar."""
        total = mastered + proficient + learning + novice
        if total == 0:
            return "[ No data yet ]"

        m_len = int(mastered / total * PROGRESS_BAR_LENGTH)
        p_len = int(proficient / total * PROGRESS_BAR_LENGTH)
        l_len = int(learning / total * PROGRESS_BAR_LENGTH)
        n_len = PROGRESS_BAR_LENGTH - m_len - p_len - l_len

        return (
            "["
            + "█" * m_len
            + "▓" * p_len
            + "▒" * l_len
            + "░" * n_len
            + "]"
        )

    async def student_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> List[app_commands.Choice[str]]:
        """Provide autocomplete choices for student selection."""
        users = await self.bot.repository.get_all_users()

        choices = []
        current_lower = current.lower()

        for user in users:
            # Match on username or discord_id
            if current_lower in user.username.lower() or current_lower in user.discord_id:
                # Show username with discord_id as the value for exact matching
                choices.append(
                    app_commands.Choice(
                        name=f"{user.username} ({user.discord_id})",
                        value=user.discord_id,
                    )
                )
                if len(choices) >= DISCORD_AUTOCOMPLETE_LIMIT:
                    break

        return choices

    @student_status.autocomplete("student")
    async def student_status_student_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> List[app_commands.Choice[str]]:
        """Autocomplete for student parameter."""
        return await self.student_autocomplete(interaction, current)

    @student_status.autocomplete("module")
    async def student_status_module_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> List[app_commands.Choice[str]]:
        """Autocomplete for module parameter."""
        return await module_autocomplete_choices(self.bot.course, current)


async def setup(bot: "ChibiBot"):
    """Set up the Admin cog."""
    await bot.add_cog(AdminCog(bot))
