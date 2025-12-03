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
        summary = await self.bot.mastery_repo.get_summary(user_id)
        total_concepts = len(self.bot.course.get_all_concepts())

        embed = discord.Embed(
            title=f"Learning Progress - {user_name}",
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

        # Quiz stats (fetched from quiz_attempts table)
        total_quizzes = await self.bot.quiz_repo.count_for_user(user_id)
        correct = await self.bot.quiz_repo.count_correct_for_user(user_id)
        accuracy = correct / total_quizzes * 100 if total_quizzes > 0 else 0

        embed.add_field(
            name="Quiz Performance",
            value=f"**{total_quizzes}** quizzes taken\n" f"**{accuracy:.1f}%** accuracy",
            inline=True,
        )

        # Mastery breakdown
        mastery_bar = create_progress_bar(
            mastered, proficient, summary.get("learning", 0), summary.get("novice", 0)
        )
        embed.add_field(
            name="Mastery Levels",
            value=f"```\n{mastery_bar}\n```\n"
            f"Mastered: {mastered}\n"
            f"Proficient: {proficient}\n"
            f"Learning: {summary.get('learning', 0)}\n"
            f"Novice: {summary.get('novice', 0)}",
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
                concept_lines.append(f"[ ] {concept.name} (not started)")

        # Module summary
        progress_pct = (
            (mastered_count + proficient_count) / total_concepts * 100
            if total_concepts > 0
            else 0
        )
        embed.add_field(
            name="Module Progress",
            value=f"**{progress_pct:.1f}%** complete ({mastered_count + proficient_count}/{total_concepts})\n"
            f"Mastered: {mastered_count} | Proficient: {proficient_count} | Started: {started_count}/{total_concepts}",
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
