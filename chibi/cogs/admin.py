"""Admin commands cog for instructor/admin functionality.

Admin commands use prefix commands (!command) instead of slash commands
to keep them hidden from students. They only work in the configured admin channel.
"""

import csv
import io
import logging
from datetime import datetime
from typing import Optional, TYPE_CHECKING

import discord
from discord.ext import commands

from ..constants import (
    CSV_FILENAME_PREFIX,
    ERROR_ADMIN_CHANNEL_NOT_CONFIGURED,
    ERROR_ADMIN_CHANNEL_ONLY,
    ERROR_MODULE_NOT_FOUND,
    ERROR_SHOW_GRADE,
    ERROR_STUDENT_NOT_FOUND,
    ERROR_STUDENT_STATUS,
    MASTERY_EMOJI,
    MASTERY_MASTERED,
    MASTERY_PROFICIENT,
    PROGRESS_BAR_LENGTH,
)

if TYPE_CHECKING:
    from ..bot import ChibiBot
    from ..content.course import Module
    from ..database.models import User

logger = logging.getLogger(__name__)


def admin_channel_only():
    """Check that ensures command is only used in the admin channel."""
    async def predicate(ctx: commands.Context) -> bool:
        bot: "ChibiBot" = ctx.bot
        admin_channel_id = bot.config.discord.admin_channel_id

        if admin_channel_id is None:
            await ctx.send(ERROR_ADMIN_CHANNEL_NOT_CONFIGURED)
            return False

        if ctx.channel.id != admin_channel_id:
            await ctx.send(f"{ERROR_ADMIN_CHANNEL_ONLY} Please use <#{admin_channel_id}>.")
            return False

        return True
    return commands.check(predicate)


class AdminCog(commands.Cog):
    """Cog for admin-only prefix commands.

    Commands:
        !show_grade [module] - Generate CSV report of student grades
        !status <student> [module] - View a student's learning progress
    """

    def __init__(self, bot: "ChibiBot"):
        self.bot = bot

    @commands.command(name="show_grade")
    @commands.has_permissions(administrator=True)
    @admin_channel_only()
    async def show_grade(
        self,
        ctx: commands.Context,
        module: Optional[str] = None,
    ):
        """Generate and send a CSV file with student grades.

        Usage: !show_grade [module]

        Args:
            module: Optional module ID to filter by
        """
        try:
            async with ctx.typing():
                # Validate module if specified
                target_module = None
                if module:
                    target_module = self.bot.course.get_module(module)
                    if not target_module:
                        await ctx.send(ERROR_MODULE_NOT_FOUND)
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
                await ctx.send(
                    f"Grade report{module_info} generated successfully.",
                    file=file
                )

        except Exception as e:
            logger.error(f"Error in !show_grade command: {e}", exc_info=True)
            await ctx.send(ERROR_SHOW_GRADE)

    async def _generate_grade_csv(
        self,
        target_module=None,
    ) -> str:
        """Generate CSV content with student grades in tidy format.

        Args:
            target_module: If specified, only include data for this module

        Returns:
            CSV content as a string (one row per user-module combination)
        """
        # Get all users
        users = await self.bot.repository.get_all_users()

        # Get course modules info
        if target_module:
            modules = [target_module]
        else:
            modules = self.bot.course.modules

        # Create CSV writer with tidy format headers
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["discord_id", "username", "module", "completion_pct"])

        # Process each user
        for user in users:
            # Get user's mastery records
            mastery_records = await self.bot.repository.get_user_mastery_all(user.id)
            mastery_by_concept = {m.concept_id: m for m in mastery_records}

            # One row per module (tidy format)
            for mod in modules:
                module_concepts = mod.concepts

                # Count completed concepts (proficient or mastered)
                completed_count = sum(
                    1 for concept in module_concepts
                    if mastery_by_concept.get(concept.id)
                    and mastery_by_concept[concept.id].mastery_level in (MASTERY_PROFICIENT, MASTERY_MASTERED)
                )

                # Calculate completion percentage
                completion_pct = (
                    (completed_count / len(module_concepts) * 100)
                    if module_concepts else 0
                )

                writer.writerow([
                    user.discord_id,
                    user.username,
                    mod.id,
                    f"{completion_pct:.1f}"
                ])

        return output.getvalue()

    @commands.command(name="status")
    @commands.has_permissions(administrator=True)
    @admin_channel_only()
    async def student_status(
        self,
        ctx: commands.Context,
        student: str,
        module: Optional[str] = None,
    ):
        """Show learning status for a specific student.

        Usage: !status <student> [module]

        Args:
            student: Student Discord ID or username to look up
            module: Optional module to show detailed progress for
        """
        try:
            async with ctx.typing():
                # Look up the student
                user = await self.bot.repository.search_user_by_identifier(student)
                if not user:
                    await ctx.send(ERROR_STUDENT_NOT_FOUND)
                    return

                # Validate module if specified
                target_module = None
                if module:
                    target_module = self.bot.course.get_module(module)
                    if not target_module:
                        await ctx.send(ERROR_MODULE_NOT_FOUND)
                        return

                # Build the appropriate embed
                if target_module is None:
                    embed = await self._build_student_summary_embed(user)
                else:
                    embed = await self._build_student_module_embed(user, target_module)

                await ctx.send(embed=embed)

        except Exception as e:
            logger.error(f"Error in !status command: {e}", exc_info=True)
            await ctx.send(ERROR_STUDENT_STATUS)

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

        embed.set_footer(text="Use !status <student> <module> for detailed module progress")

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

        embed.set_footer(text="Use !status <student> for overall summary")

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

async def setup(bot: "ChibiBot"):
    """Set up the Admin cog."""
    await bot.add_cog(AdminCog(bot))
