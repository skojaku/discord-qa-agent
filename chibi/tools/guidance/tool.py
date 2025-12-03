"""Guidance tool implementation."""

import logging
from typing import TYPE_CHECKING

import discord

from ...agent.state import SubAgentState, ToolResult
from ...constants import ERROR_MODULE_NOT_FOUND, MASTERY_EMOJI
from ..base import BaseTool, ToolConfig

if TYPE_CHECKING:
    from ...bot import ChibiBot
    from ...services.guidance_service import ConceptGuidance, ModuleGuidance

logger = logging.getLogger(__name__)


class GuidanceTool(BaseTool):
    """Guidance tool - shows what students need to do to achieve full grades.

    This tool provides personalized guidance based on the student's current
    accomplishments and calculates exactly what they need to complete for
    full grades in each module.
    """

    async def execute(self, state: SubAgentState) -> ToolResult:
        """Execute the guidance tool.

        Args:
            state: Sub-agent state with task description and parameters

        Returns:
            ToolResult with guidance embed
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
                # Validate module exists
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

            # Get guidance from service
            guidance = await self.bot.guidance_service.get_guidance(
                user_id=user.id,
                module_id=module_id,
            )

            # Build and send embed
            if module_id:
                # Single module detailed view
                module_guidance = guidance.modules[0] if guidance.modules else None
                if module_guidance:
                    embed = self._build_module_detail_embed(
                        state.user_name, module_guidance
                    )
                    summary = f"Grading guidance for {module_guidance.module_name}"
                else:
                    embed = discord.Embed(
                        title="No Guidance Available",
                        description="Could not generate guidance for this module.",
                        color=discord.Color.orange(),
                    )
                    summary = "No guidance available"
            else:
                # Overview of all modules
                embed = self._build_overview_embed(state.user_name, guidance)
                summary = "Overall grading guidance"

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
            logger.error(f"Error in GuidanceTool: {e}", exc_info=True)
            return ToolResult(
                success=False,
                result=None,
                summary="Error generating guidance",
                error=str(e),
            )

    def _build_overview_embed(
        self, user_name: str, guidance
    ) -> discord.Embed:
        """Build overview embed with guidance for all modules."""
        from ...services.guidance_service import GradingGuidance

        guidance: GradingGuidance = guidance

        embed = discord.Embed(
            title=f"Grading Guidance - {user_name}",
            description=(
                f"**Overall Completion: {guidance.overall_completion:.1f}%**\n\n"
                "Here's what you need to do to achieve full grades:"
            ),
            color=discord.Color.gold(),
        )

        # Add each module summary
        for mod_guidance in guidance.modules:
            status_icon = "✅" if mod_guidance.completion_percentage >= 100 else "📝"
            field_value = self._format_module_summary(mod_guidance)
            embed.add_field(
                name=f"{status_icon} {mod_guidance.module_name}",
                value=field_value,
                inline=False,
            )

        # Priority actions
        if guidance.priority_actions:
            actions_text = "\n".join(
                f"• {action}" for action in guidance.priority_actions
            )
            embed.add_field(
                name="Priority Actions",
                value=actions_text[:1024],  # Discord field limit
                inline=False,
            )

        embed.set_footer(
            text="Use /guidance <module> for detailed concept-by-concept guidance"
        )

        return embed

    def _build_module_detail_embed(
        self, user_name: str, mod_guidance: "ModuleGuidance"
    ) -> discord.Embed:
        """Build detailed guidance embed for a specific module."""
        completion_icon = "✅" if mod_guidance.completion_percentage >= 100 else "📝"

        embed = discord.Embed(
            title=f"{completion_icon} {mod_guidance.module_name} - Guidance",
            description=(
                f"**Completion: {mod_guidance.completion_percentage:.1f}%** "
                f"({mod_guidance.concepts_complete}/{mod_guidance.concepts_total} concepts)\n\n"
                f"{mod_guidance.summary}"
            ),
            color=discord.Color.gold()
            if mod_guidance.completion_percentage < 100
            else discord.Color.green(),
        )

        # Separate complete and incomplete concepts
        incomplete_concepts = [
            cg for cg in mod_guidance.concept_guidance if not cg.is_complete
        ]
        complete_concepts = [
            cg for cg in mod_guidance.concept_guidance if cg.is_complete
        ]

        # Show incomplete concepts first (what needs to be done)
        if incomplete_concepts:
            incomplete_text = self._format_concept_guidance_list(incomplete_concepts)
            embed.add_field(
                name="Needs Work",
                value=incomplete_text[:1024],
                inline=False,
            )

        # Show complete concepts
        if complete_concepts:
            complete_text = "\n".join(
                f"✅ **{cg.concept_name}** - {cg.current_level.capitalize()} "
                f"({cg.current_accuracy:.0f}%)"
                for cg in complete_concepts
            )
            embed.add_field(
                name="Completed",
                value=complete_text[:1024],
                inline=False,
            )

        # LLM Quiz Challenge guidance
        if mod_guidance.llm_quiz_guidance:
            llm = mod_guidance.llm_quiz_guidance
            llm_icon = "✅" if llm.is_complete else "🎯"
            llm_text = (
                f"Progress: **{llm.current_wins}/{llm.target_wins}** wins\n"
                f"{llm.guidance_text}"
            )
            embed.add_field(
                name=f"{llm_icon} LLM Quiz Challenge",
                value=llm_text,
                inline=False,
            )

        embed.set_footer(text="Use /quiz to practice | /llm-quiz to challenge the AI")

        return embed

    def _format_module_summary(self, mod_guidance: "ModuleGuidance") -> str:
        """Format module summary for overview embed."""
        lines = [
            f"**{mod_guidance.completion_percentage:.0f}%** complete "
            f"({mod_guidance.concepts_complete}/{mod_guidance.concepts_total} concepts)"
        ]

        # Count incomplete concepts
        incomplete = [cg for cg in mod_guidance.concept_guidance if not cg.is_complete]
        if incomplete:
            lines.append(f"📚 {len(incomplete)} concept(s) need practice")

        # LLM Quiz status
        if mod_guidance.llm_quiz_guidance:
            llm = mod_guidance.llm_quiz_guidance
            if llm.is_complete:
                lines.append("🎯 LLM Quiz: Complete")
            else:
                lines.append(
                    f"🎯 LLM Quiz: {llm.current_wins}/{llm.target_wins} "
                    f"(need {llm.wins_needed} more)"
                )

        return "\n".join(lines)

    def _format_concept_guidance_list(
        self, concepts: list["ConceptGuidance"]
    ) -> str:
        """Format list of concept guidance items."""
        lines = []
        for cg in concepts:
            emoji = MASTERY_EMOJI.get(cg.current_level, "⬜")
            status_info = (
                f"{cg.current_attempts} attempts, {cg.current_accuracy:.0f}% accuracy"
                if cg.current_attempts > 0
                else "Not started"
            )
            lines.append(
                f"{emoji} **{cg.concept_name}** ({status_info})\n"
                f"   → {cg.guidance_text}"
            )
        return "\n".join(lines)


async def create_tool(bot: "ChibiBot", config: ToolConfig) -> GuidanceTool:
    """Create a GuidanceTool instance.

    Args:
        bot: ChibiBot instance
        config: Tool configuration

    Returns:
        Configured GuidanceTool instance
    """
    return GuidanceTool(bot, config)
