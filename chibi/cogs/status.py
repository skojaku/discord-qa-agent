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
        try:
            return await module_autocomplete_choices(self.bot.course, current)
        except discord.errors.HTTPException as e:
            # Silently handle "Interaction has already been acknowledged" errors
            # This can happen due to Discord rate limiting or timing issues
            if e.code == 40060:  # Interaction already acknowledged
                logger.debug(f"Autocomplete interaction already acknowledged: {e}")
                return []
            raise

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

        # Send follow-up "what's remaining" message
        try:
            guidance = await self.bot.guidance_service.get_guidance(user.id, module)
            remaining_msg = self._build_remaining_message(guidance, module)
            if remaining_msg:
                await interaction.followup.send(remaining_msg)
        except Exception as e:
            logger.warning(f"Failed to send remaining message: {e}")

    def _build_remaining_message(
        self, guidance, module_id: Optional[str] = None
    ) -> Optional[str]:
        """Build a plain-text message summarizing what's remaining.

        Args:
            guidance: GradingGuidance from the guidance service
            module_id: Optional module ID for module-specific view

        Returns:
            Formatted message string, or None if everything is complete
        """
        if module_id:
            # Module detail view
            if not guidance.modules:
                return None
            mod = guidance.modules[0]
            lines = []
            for cg in mod.concept_guidance:
                if not cg.is_complete:
                    lines.append(
                        f"\u2022 {cg.concept_name}: {cg.guidance_text} Use `/quiz {module_id}`"
                    )
            if mod.llm_quiz_guidance and not mod.llm_quiz_guidance.is_complete:
                lines.append(
                    f"\u2022 LLM Quiz: {mod.llm_quiz_guidance.guidance_text} "
                    f"Use `/llm-quiz module:{module_id}`"
                )
            if not lines:
                return None
            header = f"\U0001f4cb What's remaining for {mod.module_name}:"
            return header + "\n" + "\n".join(lines)
        else:
            # Summary view - use priority_actions
            if not guidance.priority_actions:
                return None
            lines = []
            for action in guidance.priority_actions:
                # Extract module ID for command hints
                # priority_actions format: "[Module Name] Concept: guidance_text"
                cmd_hint = self._extract_command_hint(action, guidance)
                lines.append(f"\u2022 {action}{cmd_hint}")
            header = "\U0001f4cb What's remaining:"
            return header + "\n" + "\n".join(lines)

    def _extract_command_hint(self, action: str, guidance) -> str:
        """Extract a command hint from a priority action string."""
        for mod in guidance.modules:
            if action.startswith(f"[{mod.module_name}]"):
                if "LLM Quiz" in action:
                    return f" Use `/llm-quiz module:{mod.module_id}`"
                else:
                    return f" Use `/quiz {mod.module_id}`"
        return ""

    async def _build_summary_embed(
        self, user_id: int, discord_user: discord.User
    ) -> discord.Embed:
        """Build summary status embed."""
        # Get mastery records and config
        mastery_records = await self.bot.mastery_repo.get_all_for_user(user_id)
        mastery_by_concept = {m.concept_id: m for m in mastery_records}
        min_attempts = self.bot.config.mastery.min_attempts_for_mastery

        embed = discord.Embed(
            title=f"📊 Learning Progress - {discord_user.display_name}",
            color=discord.Color.blue(),
        )

        # Quiz stats (fetched from quiz_attempts table)
        total_quizzes = await self.bot.quiz_repo.count_for_user(user_id)
        correct = await self.bot.quiz_repo.count_correct_for_user(user_id)
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

        example_id = self.bot.course.modules[0].id if self.bot.course.modules else "m01"
        embed.set_footer(text=f"Use /status {example_id} for detailed progress | /llm-quiz module:{example_id} to challenge the AI")

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

        # Get mastery records and config
        mastery_records = await self.bot.mastery_repo.get_all_for_user(user_id)
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

                emoji = get_mastery_emoji(mastery.mastery_level)
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

        embed.set_footer(text=f"Use /quiz {module.id} to practice | /llm-quiz module:{module.id} to challenge AI | /status for summary")

        return embed


async def setup(bot: "ChibiBot"):
    """Set up the Status cog."""
    await bot.add_cog(StatusCog(bot))
