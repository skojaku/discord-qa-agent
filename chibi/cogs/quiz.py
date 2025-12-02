"""Quiz command cog for quiz interactions."""

import logging
import random
from typing import List, Optional, TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from ..constants import (
    ERROR_MODULE_NOT_FOUND,
    ERROR_NO_CONCEPTS,
    ERROR_QUIZ,
)
from ..ui.embeds import QuizEmbedBuilder
from .utils import (
    defer_interaction,
    get_or_create_user_from_interaction,
    handle_slash_command_errors,
    module_autocomplete_choices,
)

if TYPE_CHECKING:
    from ..bot import ChibiBot

logger = logging.getLogger(__name__)


class QuizAnswerModal(discord.ui.Modal, title="Quiz"):
    """Modal for submitting a quiz answer."""

    def __init__(
        self,
        cog: "QuizCog",
        db_user_id: int,
        module_id: str,
        concept_id: str,
        concept_name: str,
        concept_description: str,
        question: str,
        correct_answer: Optional[str],
    ):
        super().__init__()
        self.cog = cog
        self.db_user_id = db_user_id
        self.module_id = module_id
        self.concept_id = concept_id
        self.concept_name = concept_name
        self.concept_description = concept_description
        self.question = question
        self.correct_answer = correct_answer

        # Add question display field (read-only conceptually)
        # Truncate if too long for modal (max ~4000 chars total)
        question_display = question[:1500] if len(question) > 1500 else question
        # Label max is 45 chars
        label_concept = concept_name[:30] if len(concept_name) > 30 else concept_name
        self.question_field = discord.ui.TextInput(
            label=f"Question: {label_concept}",
            style=discord.TextStyle.paragraph,
            default=question_display,
            required=False,
            max_length=2000,
        )
        self.add_item(self.question_field)

        # Add answer field
        self.answer_field = discord.ui.TextInput(
            label="Your Answer",
            style=discord.TextStyle.paragraph,
            placeholder="Type your answer here...",
            required=True,
            max_length=2000,
        )
        self.add_item(self.answer_field)

    async def on_submit(self, interaction: discord.Interaction):
        """Handle answer submission."""
        await interaction.response.defer(thinking=True)

        try:
            student_answer = self.answer_field.value

            # Evaluate the answer
            result = await self.cog.bot.quiz_service.evaluate_answer(
                question=self.question,
                student_answer=student_answer,
                concept_name=self.concept_name,
                concept_description=self.concept_description,
                correct_answer=self.correct_answer,
            )

            if not result:
                await interaction.followup.send(
                    self.cog.bot.llm_manager.get_error_message()
                )
                return

            # Log attempt and update mastery
            await self.cog.bot.quiz_service.log_attempt_and_update_mastery(
                user_id=self.db_user_id,
                module_id=self.module_id,
                concept_id=self.concept_id,
                question=self.question,
                user_answer=student_answer,
                correct_answer=self.correct_answer,
                result=result,
            )

            # Send feedback
            embed = QuizEmbedBuilder.create_feedback_embed(
                is_pass=result.is_correct,
                is_partial=result.is_partial,
                quality_score=result.quality_score,
                feedback=result.feedback,
                concept_name=self.concept_name,
            )

            await interaction.followup.send(embed=embed)

            logger.info(
                f"Quiz evaluated for {interaction.user.display_name}: "
                f"{self.concept_name} - {'correct' if result.is_correct else 'incorrect'}"
            )

        except Exception as e:
            logger.error(f"Error evaluating quiz answer: {e}", exc_info=True)
            try:
                await interaction.followup.send(ERROR_QUIZ)
            except discord.NotFound:
                pass


class QuizAnswerButton(discord.ui.View):
    """View with a button to open the answer modal."""

    def __init__(
        self,
        cog: "QuizCog",
        db_user_id: int,
        module_id: str,
        concept_id: str,
        concept_name: str,
        concept_description: str,
        question: str,
        correct_answer: Optional[str],
        timeout: float = 600,  # 10 minutes
    ):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.db_user_id = db_user_id
        self.module_id = module_id
        self.concept_id = concept_id
        self.concept_name = concept_name
        self.concept_description = concept_description
        self.question = question
        self.correct_answer = correct_answer
        self.answered = False
        self.original_user_id: Optional[int] = None

    @discord.ui.button(
        label="Answer",
        style=discord.ButtonStyle.primary,
        emoji="✏️",
    )
    async def answer_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """Open the answer modal when clicked."""
        # Only allow the original user to answer
        if self.original_user_id and interaction.user.id != self.original_user_id:
            await interaction.response.send_message(
                "This quiz is for another user!", ephemeral=True
            )
            return

        if self.answered:
            await interaction.response.send_message(
                "You've already answered this question!", ephemeral=True
            )
            return

        modal = QuizAnswerModal(
            cog=self.cog,
            db_user_id=self.db_user_id,
            module_id=self.module_id,
            concept_id=self.concept_id,
            concept_name=self.concept_name,
            concept_description=self.concept_description,
            question=self.question,
            correct_answer=self.correct_answer,
        )
        await interaction.response.send_modal(modal)
        self.answered = True

        # Disable button after answering
        button.disabled = True
        button.label = "Answered"
        button.style = discord.ButtonStyle.secondary
        try:
            await interaction.message.edit(view=self)
        except discord.NotFound:
            pass

    async def on_timeout(self):
        """Disable button on timeout."""
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True
                item.label = "Expired"
                item.style = discord.ButtonStyle.secondary


class QuizCog(commands.Cog):
    """Cog for the /quiz command."""

    def __init__(self, bot: "ChibiBot"):
        self.bot = bot

    async def module_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> List[app_commands.Choice[str]]:
        """Autocomplete for module selection."""
        return await module_autocomplete_choices(self.bot.course, current)

    @app_commands.command(name="quiz", description="Test your knowledge with a quiz question")
    @app_commands.describe(
        module="Module to quiz on (optional - selects based on your progress)",
    )
    @app_commands.autocomplete(module=module_autocomplete)
    @defer_interaction(thinking=True)
    @handle_slash_command_errors(error_message=ERROR_QUIZ, context="/quiz")
    async def quiz(
        self,
        interaction: discord.Interaction,
        module: str = None,
    ):
        """Generate a quiz question."""
        # Get or create user
        user = await get_or_create_user_from_interaction(
            self.bot.user_repo, interaction
        )

        # Select module
        if module:
            module_obj = self.bot.course.get_module(module)
        else:
            module_obj = random.choice(self.bot.course.modules)

        if not module_obj:
            await interaction.followup.send(ERROR_MODULE_NOT_FOUND)
            return

        # Select concept based on mastery level
        concept_obj, selection_reason = await self.bot.quiz_service.select_concept_by_mastery(
            user.id, module_obj
        )

        if not concept_obj:
            await interaction.followup.send(ERROR_NO_CONCEPTS)
            return

        # Generate quiz question
        result = await self.bot.quiz_service.generate_question(concept_obj, module_obj)

        if not result:
            await interaction.followup.send(
                self.bot.llm_manager.get_error_message()
            )
            return

        question_text, correct_answer = result

        # Create answer button view
        view = QuizAnswerButton(
            cog=self,
            db_user_id=user.id,
            module_id=module_obj.id,
            concept_id=concept_obj.id,
            concept_name=concept_obj.name,
            concept_description=concept_obj.description,
            question=question_text,
            correct_answer=correct_answer,
        )
        view.original_user_id = interaction.user.id

        # Send question with answer button
        embed = QuizEmbedBuilder.create_question_embed(
            concept_name=concept_obj.name,
            question_text=question_text,
            module_name=module_obj.name,
            selection_reason=selection_reason,
        )

        await interaction.followup.send(embed=embed, view=view)

        logger.info(
            f"Quiz generated for {interaction.user.display_name}: {concept_obj.name}"
        )


async def setup(bot: "ChibiBot"):
    """Set up the Quiz cog."""
    await bot.add_cog(QuizCog(bot))
