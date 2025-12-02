"""LLM Quiz Challenge cog - stump the AI!"""

import logging
from typing import List, Optional, TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from ..constants import ERROR_MODULE_NOT_FOUND
from .utils import (
    get_or_create_user_from_interaction,
    module_autocomplete_choices,
)

if TYPE_CHECKING:
    from ..bot import ChibiBot

logger = logging.getLogger(__name__)

# Error messages
ERROR_LLM_QUIZ = "Oops! Something went wrong during the LLM Quiz Challenge. Please try again!"


class LLMQuizModal(discord.ui.Modal, title="LLM Quiz Challenge"):
    """Modal for submitting a question to stump the LLM."""

    question = discord.ui.TextInput(
        label="Your Question",
        style=discord.TextStyle.paragraph,
        placeholder="Enter a challenging question about the module topic...",
        required=True,
        max_length=1000,
    )

    answer = discord.ui.TextInput(
        label="Your Answer (the correct answer)",
        style=discord.TextStyle.paragraph,
        placeholder="Enter the correct answer to your question...",
        required=True,
        max_length=500,
    )

    def __init__(self, cog: "LLMQuizCog", module_id: str, module_name: str, module_content: Optional[str]):
        super().__init__()
        self.cog = cog
        self.module_id = module_id
        self.module_name = module_name
        self.module_content = module_content

    async def on_submit(self, interaction: discord.Interaction):
        """Handle modal submission."""
        await interaction.response.defer(thinking=True)

        try:
            # Get or create user
            user = await get_or_create_user_from_interaction(
                self.cog.bot.user_repo, interaction
            )

            # Run the challenge
            result = await self.cog.bot.llm_quiz_service.challenge_llm(
                question=self.question.value,
                student_answer=self.answer.value,
                module_content=self.module_content,
            )

            # Log the attempt
            await self.cog.bot.llm_quiz_service.log_attempt(
                user_id=user.id,
                module_id=self.module_id,
                question=self.question.value,
                student_answer=self.answer.value,
                result=result,
            )

            # Get updated progress
            wins, target = await self.cog.bot.llm_quiz_service.get_module_progress(
                user.id, self.module_id
            )

            # Build response embed
            embed = self._build_result_embed(result, wins, target)
            await interaction.followup.send(embed=embed)

            logger.info(
                f"LLM Quiz Challenge for {interaction.user.display_name}: "
                f"{'WIN' if result.student_wins else 'LOSE'} (module: {self.module_id})"
            )

        except Exception as e:
            logger.error(f"Error in LLM Quiz Challenge: {e}", exc_info=True)
            try:
                await interaction.followup.send(ERROR_LLM_QUIZ)
            except discord.NotFound:
                pass

    def _build_result_embed(self, result, wins: int, target: int) -> discord.Embed:
        """Build the result embed."""
        if result.student_wins:
            color = discord.Color.green()
            title = "You stumped the AI!"
        else:
            color = discord.Color.red()
            if result.student_answer_correctness != "CORRECT":
                title = "Your answer was incorrect!"
            else:
                title = "The AI got it right!"

        embed = discord.Embed(
            title=title,
            color=color,
        )

        embed.add_field(
            name="Module",
            value=self.module_name,
            inline=True,
        )

        # Truncate question if too long
        question_display = self.question.value
        if len(question_display) > 200:
            question_display = question_display[:197] + "..."

        embed.add_field(
            name="Your Question",
            value=question_display,
            inline=False,
        )

        # Truncate answers if too long
        student_answer_display = self.answer.value
        if len(student_answer_display) > 200:
            student_answer_display = student_answer_display[:197] + "..."

        llm_answer_display = result.llm_answer
        if len(llm_answer_display) > 200:
            llm_answer_display = llm_answer_display[:197] + "..."

        embed.add_field(
            name="Your Answer",
            value=student_answer_display,
            inline=True,
        )

        embed.add_field(
            name="AI's Answer",
            value=llm_answer_display,
            inline=True,
        )

        # Student answer correctness
        correctness_emoji = {
            "CORRECT": "Correct",
            "INCORRECT": "Incorrect",
            "PARTIALLY_CORRECT": "Partially Correct",
        }
        embed.add_field(
            name="Your Answer Validity",
            value=correctness_emoji.get(result.student_answer_correctness, result.student_answer_correctness),
            inline=True,
        )

        # Truncate evaluation explanation if too long
        explanation_display = result.evaluation_explanation
        if len(explanation_display) > 500:
            explanation_display = explanation_display[:497] + "..."

        embed.add_field(
            name="Evaluation",
            value=explanation_display,
            inline=False,
        )

        # Progress indicator
        progress_bar = self._create_progress_bar(wins, target)
        embed.add_field(
            name="Module Progress",
            value=f"{progress_bar} ({wins}/{target} stumps)",
            inline=False,
        )

        # Factual issues if any
        if result.factual_issues:
            issues_text = "\n".join(f"- {issue}" for issue in result.factual_issues[:3])
            if issues_text:
                embed.add_field(
                    name="Notes",
                    value=issues_text,
                    inline=False,
                )

        return embed

    def _create_progress_bar(self, current: int, target: int) -> str:
        """Create a simple progress bar."""
        filled = min(current, target)
        empty = target - filled
        return "🟩" * filled + "⬜" * empty


class LLMQuizCog(commands.Cog):
    """Cog for the /llm-quiz command."""

    def __init__(self, bot: "ChibiBot"):
        self.bot = bot

    async def module_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> List[app_commands.Choice[str]]:
        """Autocomplete for module selection."""
        return await module_autocomplete_choices(self.bot.course, current)

    @app_commands.command(
        name="llm-quiz",
        description="Challenge the AI! Create a question to stump the LLM"
    )
    @app_commands.describe(
        module="Select a module to challenge the AI on",
    )
    @app_commands.autocomplete(module=module_autocomplete)
    async def llm_quiz(
        self,
        interaction: discord.Interaction,
        module: str,
    ):
        """Launch the LLM Quiz Challenge modal."""
        # Validate module
        module_obj = self.bot.course.get_module(module)
        if not module_obj:
            await interaction.response.send_message(
                ERROR_MODULE_NOT_FOUND, ephemeral=True
            )
            return

        # Create and send modal
        modal = LLMQuizModal(
            cog=self,
            module_id=module_obj.id,
            module_name=module_obj.name,
            module_content=module_obj.content,
        )
        await interaction.response.send_modal(modal)


async def setup(bot: "ChibiBot"):
    """Set up the LLM Quiz cog."""
    await bot.add_cog(LLMQuizCog(bot))
