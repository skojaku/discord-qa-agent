"""Status command cog for learning progress tracking."""

import logging
from typing import List, Optional, TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from ..constants import (
    ERROR_MODULE_NOT_FOUND,
    ERROR_STATUS,
)
from ..ui import create_progress_bar, get_mastery_emoji
from .utils import (
    defer_interaction,
    get_or_create_user_from_interaction,
    handle_slash_command_errors,
    module_autocomplete_choices,
)

if TYPE_CHECKING:
    from ..bot import ChibiBot
    from ..content.course import Module

logger = logging.getLogger(__name__)


class StatusCog(commands.Cog):
    """Cog for the /status command."""

    def __init__(self, bot: "ChibiBot"):
        self.bot = bot

    async def module_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> List[app_commands.Choice[str]]:
        """Autocomplete callback for module selection."""
        return await module_autocomplete_choices(self.bot.course, current)

    @app_commands.command(name="status", description="View your learning progress")
    @app_commands.describe(
        module="Module to show detailed progress for (leave empty for summary)",
    )
    @app_commands.autocomplete(module=module_autocomplete)
    @defer_interaction(thinking=True)
    @handle_slash_command_errors(error_message=ERROR_STATUS, context="/status")
    async def status(
        self,
        interaction: discord.Interaction,
        module: Optional[str] = None,
    ):
        """Show learning status and progress."""
        # Get or create user
        user = await get_or_create_user_from_interaction(
            self.bot.user_repo, interaction
        )

        if module is None:
            # No module specified: show summary
            embed = await self._build_summary_embed(user.id, interaction.user)
        else:
            # Module specified: show detailed view for that module
            target_module = self.bot.course.get_module(module)
            if target_module is None:
                await interaction.followup.send(ERROR_MODULE_NOT_FOUND)
                return
            embed = await self._build_module_detail_embed(
                user.id, interaction.user, target_module
            )

        await interaction.followup.send(embed=embed)

    async def _build_summary_embed(
        self, user_id: int, discord_user: discord.User
    ) -> discord.Embed:
        """Build summary status embed."""
        summary = await self.bot.mastery_repo.get_summary(user_id)
        total_concepts = len(self.bot.course.get_all_concepts())

        embed = discord.Embed(
            title=f"📊 Learning Progress - {discord_user.display_name}",
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

        # LLM Quiz Challenge progress
        llm_quiz_progress = await self.bot.llm_quiz_service.get_all_progress(user_id)
        if llm_quiz_progress:
            progress_lines = []
            for module_id, (wins, target) in llm_quiz_progress.items():
                module_obj = self.bot.course.get_module(module_id)
                module_name = module_obj.name if module_obj else module_id
                status = "✅" if wins >= target else "⏳"
                progress_lines.append(f"{status} {module_name}: {wins}/{target}")

            embed.add_field(
                name="🎯 LLM Quiz Challenge",
                value="\n".join(progress_lines) if progress_lines else "No challenges attempted yet",
                inline=False,
            )

        embed.set_footer(text="Use /status <module> for detailed progress | /llm-quiz to challenge the AI")

        return embed

    async def _build_module_detail_embed(
        self, user_id: int, discord_user: discord.User, module: "Module"
    ) -> discord.Embed:
        """Build detailed status embed for a specific module.

        Args:
            user_id: Database user ID
            discord_user: Discord user object
            module: The module to show details for
        """
        embed = discord.Embed(
            title=f"📚 {module.name} - {discord_user.display_name}",
            description=module.description if module.description else None,
            color=discord.Color.blue(),
        )

        # Get all mastery records for this user
        mastery_records = await self.bot.mastery_repo.get_all_for_user(user_id)
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

                emoji = get_mastery_emoji(mastery.mastery_level)
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

        embed.set_footer(text="Use /quiz to practice | /llm-quiz to challenge AI | /status for summary")

        return embed


async def setup(bot: "ChibiBot"):
    """Set up the Status cog."""
    await bot.add_cog(StatusCog(bot))
