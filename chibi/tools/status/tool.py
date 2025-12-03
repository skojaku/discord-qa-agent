"""Status tool implementation."""

import logging
from typing import TYPE_CHECKING

import discord

from ...agent.state import SubAgentState, ToolResult
from ...constants import ERROR_MODULE_NOT_FOUND
from ...ui import create_progress_bar, get_mastery_emoji
from ..base import BaseTool, ToolConfig

if TYPE_CHECKING:
    from ...bot import ChibiBot
    from ...content.course import Module

logger = logging.getLogger(__name__)


class StatusTool(BaseTool):
    """Status tool - shows learning progress and mastery status.

    This tool displays the user's learning progress, including
    mastery levels, quiz statistics, and LLM Quiz Challenge progress.
    """

    async def execute(self, state: SubAgentState) -> ToolResult:
        """Execute the status tool.

        Args:
            state: Sub-agent state with task description and parameters

        Returns:
            ToolResult with status embed
        """
        try:
            discord_message = state.discord_message
            if discord_message is None:
                return ToolResult(
                    success=False,
                    result=None,
                    summary="No Discord context available",
                    error="Discord message not provided",
                )

            # Get or create user
            user = await self.bot.user_repo.get_or_create(
                discord_id=state.user_id,
                username=state.user_name,
            )

            # Check if module was specified
            module_id = state.parameters.get("module")

            if module_id:
                # Module specified: show detailed view
                target_module = self.bot.course.get_module(module_id)
                if target_module is None:
                    await discord_message.reply(
                        ERROR_MODULE_NOT_FOUND, mention_author=False
                    )
                    return ToolResult(
                        success=False,
                        result=None,
                        summary="Module not found",
                        error=ERROR_MODULE_NOT_FOUND,
                    )
                embed = await self._build_module_detail_embed(
                    user.id, state.user_name, target_module
                )
                summary = f"Detailed progress for {target_module.name}"
            else:
                # No module: show summary
                embed = await self._build_summary_embed(user.id, state.user_name)
                summary = "Overall learning progress summary"

            await discord_message.reply(embed=embed, mention_author=False)

            return ToolResult(
                success=True,
                result=embed,
                summary=summary,
                metadata={
                    "response_type": "embed",
                    "response_sent": True,
                },
            )

        except Exception as e:
            logger.error(f"Error in StatusTool: {e}", exc_info=True)
            return ToolResult(
                success=False,
                result=None,
                summary="Error showing status",
                error=str(e),
            )

    async def _build_summary_embed(
        self, user_id: int, user_name: str
    ) -> discord.Embed:
        """Build summary status embed."""
        # Get mastery records and config
        mastery_records = await self.bot.mastery_repo.get_all_for_user(user_id)
        mastery_by_concept = {m.concept_id: m for m in mastery_records}
        min_attempts = self.bot.config.mastery.min_attempts_for_mastery

        embed = discord.Embed(
            title=f"Learning Progress - {user_name}",
            color=discord.Color.blue(),
        )

        # Quiz stats (fetched from quiz_attempts table)
        total_quizzes = await self.bot.quiz_repo.count_for_user(user_id)
        correct = await self.bot.quiz_repo.count_correct_for_user(user_id)
        accuracy = correct / total_quizzes * 100 if total_quizzes > 0 else 0

        embed.add_field(
            name="Quiz Performance",
            value=f"**{total_quizzes}** quizzes taken\n" f"**{accuracy:.1f}%** accuracy",
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
                status = "Done" if wins >= target else "In Progress"
                progress_lines.append(f"{status} {module_name}: {wins}/{target}")

            embed.add_field(
                name="LLM Quiz Challenge",
                value=(
                    "\n".join(progress_lines)
                    if progress_lines
                    else "No challenges attempted yet"
                ),
                inline=False,
            )

        embed.set_footer(
            text="Use /status <module> for detailed progress | /llm-quiz to challenge the AI"
        )

        return embed

    async def _build_module_detail_embed(
        self, user_id: int, user_name: str, module: "Module"
    ) -> discord.Embed:
        """Build detailed status embed for a specific module."""
        embed = discord.Embed(
            title=f"{module.name} - {user_name}",
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
                concept_lines.append(f"[ ] {concept.name} (0/{min_attempts} passed)")

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

        embed.set_footer(
            text="Use /quiz to practice | /llm-quiz to challenge AI | /status for summary"
        )

        return embed


async def create_tool(bot: "ChibiBot", config: ToolConfig) -> StatusTool:
    """Create a StatusTool instance.

    Args:
        bot: ChibiBot instance
        config: Tool configuration

    Returns:
        Configured StatusTool instance
    """
    return StatusTool(bot, config)
