"""Admin commands cog for instructor/admin functionality.

Admin commands use prefix commands (!command) instead of slash commands
to keep them hidden from students. They only work in the configured admin channel.
"""

import csv
import io
import logging
import re
from datetime import datetime
from typing import Optional, TYPE_CHECKING

import discord
from discord.ext import commands

from ..constants import (
    CSV_FILENAME_PREFIX,
    DESCRIPTION_TRUNCATE_LENGTH,
    EMBED_FIELD_CHUNK_SIZE,
    ERROR_ADMIN_CHANNEL_NOT_CONFIGURED,
    ERROR_ADMIN_CHANNEL_ONLY,
    ERROR_MODULE_NOT_FOUND,
    ERROR_SHOW_GRADE,
    ERROR_STUDENT_NOT_FOUND,
    ERROR_STUDENT_STATUS,
    MASTERY_EMOJI,
    MASTERY_MASTERED,
    MASTERY_PROFICIENT,
)
from ..ui import create_progress_bar, truncate_text

if TYPE_CHECKING:
    from ..bot import ChibiBot
    from ..content.course import Module
    from ..database.models import User

logger = logging.getLogger(__name__)

# Pattern to match Discord user mentions: <@123456789> or <@!123456789>
MENTION_PATTERN = re.compile(r"<@!?(\d+)>")


def extract_user_id_from_mention(text: str) -> Optional[str]:
    """Extract Discord user ID from a mention string.

    Args:
        text: Text that might be a mention like <@123456789> or <@!123456789>

    Returns:
        The user ID as a string if it's a mention, None otherwise
    """
    match = MENTION_PATTERN.match(text)
    if match:
        return match.group(1)
    return None


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

    @commands.command(name="help", aliases=["admin"])
    @commands.has_permissions(administrator=True)
    @admin_channel_only()
    async def admin_help(self, ctx: commands.Context):
        """Show admin commands, available modules, and registered students.

        Usage: !help or !admin
        """
        try:
            async with ctx.typing():
                embed = discord.Embed(
                    title="Admin Commands",
                    description="Use these commands to manage and monitor student progress.",
                    color=discord.Color.blue(),
                )

                # Commands as individual fields for better readability
                embed.add_field(
                    name="`!help` or `!admin`",
                    value="Show this help message",
                    inline=False,
                )
                embed.add_field(
                    name="`!modules`",
                    value="List all available modules with details",
                    inline=False,
                )
                embed.add_field(
                    name="`!students`",
                    value="List all registered students with activity info",
                    inline=False,
                )
                embed.add_field(
                    name="`!show_grade [module]`",
                    value="Export student grades as CSV file\n*Optional: filter by module ID*",
                    inline=False,
                )
                embed.add_field(
                    name="`!status <student> [module]`",
                    value="View a student's learning progress\n*Accepts @mention, Discord ID, or username*",
                    inline=False,
                )

                # Quick stats
                modules = self.bot.course.modules
                users = await self.bot.repository.get_all_users()
                embed.add_field(
                    name="Quick Stats",
                    value=f"**{len(modules)}** modules | **{len(users)}** students registered",
                    inline=False,
                )

                embed.set_footer(text="Use !modules or !students for detailed lists")
                await ctx.send(embed=embed)

        except Exception as e:
            logger.error(f"Error in !admin command: {e}", exc_info=True)
            await ctx.send("Failed to show admin help.")

    @commands.command(name="modules")
    @commands.has_permissions(administrator=True)
    @admin_channel_only()
    async def list_modules(self, ctx: commands.Context):
        """List all available modules.

        Usage: !modules
        """
        try:
            modules = self.bot.course.modules
            if not modules:
                await ctx.send("No modules configured.")
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

            await ctx.send(embed=embed)

        except Exception as e:
            logger.error(f"Error in !modules command: {e}", exc_info=True)
            await ctx.send("Failed to list modules.")

    @commands.command(name="students")
    @commands.has_permissions(administrator=True)
    @admin_channel_only()
    async def list_students(self, ctx: commands.Context):
        """List all registered students.

        Usage: !students
        """
        try:
            async with ctx.typing():
                users = await self.bot.repository.get_all_users()

                if not users:
                    await ctx.send("No students registered yet.")
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

                embed.set_footer(text="Use !status <student> to view a student's progress")
                await ctx.send(embed=embed)

        except Exception as e:
            logger.error(f"Error in !students command: {e}", exc_info=True)
            await ctx.send("Failed to list students.")

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
            student: Student @mention, Discord ID, or username to look up
            module: Optional module to show detailed progress for
        """
        try:
            async with ctx.typing():
                # Extract user ID from mention if applicable
                identifier = extract_user_id_from_mention(student) or student
                logger.debug(f"Looking up student: input='{student}', identifier='{identifier}'")

                # Look up the student
                user = await self.bot.repository.search_user_by_identifier(identifier)
                if not user:
                    # Check if it's a valid Discord user who just hasn't used the bot yet
                    mention_id = extract_user_id_from_mention(student)
                    if mention_id:
                        await ctx.send(
                            f"User <@{mention_id}> hasn't taken any quizzes yet. "
                            "They need to use `/quiz` first to appear in the system."
                        )
                    else:
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
        mastery_bar = create_progress_bar(
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


async def setup(bot: "ChibiBot"):
    """Set up the Admin cog."""
    await bot.add_cog(AdminCog(bot))
