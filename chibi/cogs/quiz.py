"""Quiz command cog for quiz interactions."""

import logging
import random
from datetime import datetime
from typing import List, Optional, TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from ..constants import (
    ERROR_MODULE_NOT_FOUND,
    ERROR_NO_CONCEPTS,
    ERROR_QUIZ,
    QUIZ_TIMEOUT_MINUTES,
)
from ..services import PendingQuiz, PendingQuizManager
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


class QuizCog(commands.Cog):
    """Cog for the /quiz command."""

    def __init__(self, bot: "ChibiBot"):
        self.bot = bot
        self._quiz_manager = PendingQuizManager(timeout_minutes=QUIZ_TIMEOUT_MINUTES)

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

        # Send question
        embed = QuizEmbedBuilder.create_question_embed(
            concept_name=concept_obj.name,
            question_text=question_text,
            module_name=module_obj.name,
            selection_reason=selection_reason,
        )

        message = await interaction.followup.send(embed=embed)

        # Store pending quiz (thread-safe)
        pending = PendingQuiz(
            user_id=interaction.user.id,
            db_user_id=user.id,
            channel_id=interaction.channel_id,
            message_id=message.id,
            module_id=module_obj.id,
            concept_id=concept_obj.id,
            concept_name=concept_obj.name,
            concept_description=concept_obj.description,
            question=question_text,
            correct_answer=correct_answer,
            created_at=datetime.now(),
        )
        await self._quiz_manager.add(pending)

        logger.info(
            f"Quiz generated for {interaction.user.display_name}: {concept_obj.name}"
        )

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Listen for quiz answers."""
        if message.author.bot:
            return

        user_id = message.author.id

        # Check if user has a pending quiz (thread-safe, handles expiration)
        pending = await self._quiz_manager.get(user_id)
        if pending is None:
            return

        # Check if message is in the same channel (or DM)
        is_same_channel = message.channel.id == pending.channel_id
        is_dm = isinstance(message.channel, discord.DMChannel)

        if not (is_same_channel or is_dm):
            return

        # Check if it's a reply to the quiz message or just any message in DM
        is_reply = (
            message.reference
            and message.reference.message_id == pending.message_id
        )

        # In DMs, accept any message. In channels, require reply
        if not is_dm and not is_reply:
            return

        # Remove pending quiz before processing to prevent double-evaluation
        await self._quiz_manager.remove(user_id)

        # Process the answer
        await self._evaluate_answer(message, pending)

    async def _evaluate_answer(self, message: discord.Message, pending: PendingQuiz):
        """Evaluate a student's quiz answer."""
        student_answer = message.content

        async with message.channel.typing():
            # Evaluate the answer
            result = await self.bot.quiz_service.evaluate_answer(
                question=pending.question,
                student_answer=student_answer,
                concept_name=pending.concept_name,
                concept_description=pending.concept_description,
                correct_answer=pending.correct_answer,
            )

            if not result:
                await message.reply(self.bot.llm_manager.get_error_message())
                return

            # Log attempt and update mastery
            await self.bot.quiz_service.log_attempt_and_update_mastery(
                user_id=pending.db_user_id,
                module_id=pending.module_id,
                concept_id=pending.concept_id,
                question=pending.question,
                user_answer=student_answer,
                correct_answer=pending.correct_answer,
                result=result,
            )

            # Send feedback
            embed = QuizEmbedBuilder.create_feedback_embed(
                is_pass=result.is_correct,
                is_partial=result.is_partial,
                quality_score=result.quality_score,
                feedback=result.feedback,
                concept_name=pending.concept_name,
            )

            await message.reply(embed=embed)

            logger.info(
                f"Quiz evaluated for {message.author.display_name}: "
                f"{pending.concept_name} - {'correct' if result.is_correct else 'incorrect'}"
            )


async def setup(bot: "ChibiBot"):
    """Set up the Quiz cog."""
    await bot.add_cog(QuizCog(bot))
