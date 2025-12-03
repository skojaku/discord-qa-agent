"""Guidance command cog for personalized grading guidance."""

import logging
from typing import List, Optional, TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from ..constants import (
    ERROR_MODULE_NOT_FOUND,
    MASTERY_EMOJI,
)
from .utils import (
    defer_interaction,
    get_or_create_user_from_interaction,
    handle_slash_command_errors,
    module_autocomplete_choices,
)

if TYPE_CHECKING:
    from ..bot import ChibiBot
    from ..services.guidance_service import ConceptGuidance, ModuleGuidance

logger = logging.getLogger(__name__)

ERROR_GUIDANCE = "Oops! Something went wrong while generating guidance. Please try again!"


class GuidanceCog(commands.Cog):
    """Cog for the /guidance command."""

    def __init__(self, bot: "ChibiBot"):
        self.bot = bot

    async def module_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> List[app_commands.Choice[str]]:
        """Autocomplete callback for module selection."""
        return await module_autocomplete_choices(self.bot.course, current)

    @app_commands.command(
        name="guidance",
        description="Get personalized guidance on what you need to achieve full grades",
    )
    @app_commands.describe(
        module="Module to show guidance for (leave empty for all modules)",
    )
    @app_commands.autocomplete(module=module_autocomplete)
    @defer_interaction(thinking=True)
    @handle_slash_command_errors(error_message=ERROR_GUIDANCE, context="/guidance")
    async def guidance(
        self,
        interaction: discord.Interaction,
        module: Optional[str] = None,
    ):
        """Show personalized grading guidance."""
        # Get or create user
        user = await get_or_create_user_from_interaction(
            self.bot.user_repo, interaction
        )

        if module is not None:
            # Validate module exists
            target_module = self.bot.course.get_module(module)
            if target_module is None:
                await interaction.followup.send(ERROR_MODULE_NOT_FOUND)
                return

        # Get guidance from service
        guidance = await self.bot.guidance_service.get_guidance(
            user_id=user.id,
            module_id=module,
        )

        # Build and send embed
        if module:
            # Single module detailed view
            module_guidance = guidance.modules[0] if guidance.modules else None
            if module_guidance:
                embed = self._build_module_detail_embed(
                    interaction.user, module_guidance
                )
            else:
                embed = discord.Embed(
                    title="No Guidance Available",
                    description="Could not generate guidance for this module.",
                    color=discord.Color.orange(),
                )
        else:
            # Overview of all modules
            embed = self._build_overview_embed(interaction.user, guidance)

        await interaction.followup.send(embed=embed)

    def _build_overview_embed(
        self, discord_user: discord.User, guidance
    ) -> discord.Embed:
        """Build overview embed with guidance for all modules."""
        from ..services.guidance_service import GradingGuidance

        guidance: GradingGuidance = guidance

        embed = discord.Embed(
            title=f"Grading Guidance - {discord_user.display_name}",
            description=(
                f"**Overall Completion: {guidance.overall_completion:.1f}%**\n\n"
                "Here's what you need to do to achieve full grades:"
            ),
            color=discord.Color.gold(),
        )

        # Add each module summary
        for mod_guidance in guidance.modules:
            status_icon = (
                "✅" if mod_guidance.completion_percentage >= 100 else "📝"
            )
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
        self, discord_user: discord.User, mod_guidance: "ModuleGuidance"
    ) -> discord.Embed:
        """Build detailed guidance embed for a specific module."""
        completion_icon = (
            "✅" if mod_guidance.completion_percentage >= 100 else "📝"
        )

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

        embed.set_footer(
            text="Use /quiz to practice | /llm-quiz to challenge the AI"
        )

        return embed

    def _format_module_summary(self, mod_guidance: "ModuleGuidance") -> str:
        """Format module summary for overview embed."""
        lines = [
            f"**{mod_guidance.completion_percentage:.0f}%** complete "
            f"({mod_guidance.concepts_complete}/{mod_guidance.concepts_total} concepts)"
        ]

        # Count incomplete concepts
        incomplete = [
            cg for cg in mod_guidance.concept_guidance if not cg.is_complete
        ]
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


async def setup(bot: "ChibiBot"):
    """Set up the Guidance cog."""
    await bot.add_cog(GuidanceCog(bot))
