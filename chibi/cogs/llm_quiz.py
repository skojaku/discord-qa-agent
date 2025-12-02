"""LLM Quiz Challenge cog - stump the AI!"""

import logging
from typing import List, Optional, TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from ..constants import ERROR_MODULE_NOT_FOUND
from ..database.models import ReviewStatus
from ..ui.views.admin_review import (
    AdminReviewView,
    build_review_request_embed,
    get_review_status_display,
)
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

            # Check for similar questions (before running expensive challenge)
            similarity_result = await self.cog.bot.similarity_service.check_similarity(
                question=self.question.value,
                module_id=self.module_id,
            )

            if similarity_result.is_similar:
                # Reject the question - too similar to existing one
                embed = discord.Embed(
                    title="Question Too Similar",
                    description=(
                        "Your question is too similar to one already submitted "
                        "for this module. Please try a more unique question!"
                    ),
                    color=discord.Color.orange(),
                )
                embed.add_field(
                    name="Module",
                    value=self.module_name,
                    inline=True,
                )
                await interaction.followup.send(embed=embed)
                logger.info(
                    f"LLM Quiz rejected for {interaction.user.display_name}: "
                    f"similarity {similarity_result.highest_similarity:.2f} "
                    f"(module: {self.module_id})"
                )
                return

            # Run the challenge
            result = await self.cog.bot.llm_quiz_service.challenge_llm(
                question=self.question.value,
                student_answer=self.answer.value,
                module_content=self.module_content,
            )

            # Log the attempt with review workflow enabled for wins
            attempt = await self.cog.bot.llm_quiz_service.log_attempt(
                user_id=user.id,
                module_id=self.module_id,
                question=self.question.value,
                student_answer=self.answer.value,
                result=result,
                discord_user_id=str(interaction.user.id),
                requires_review=True,  # Enable admin review for wins
            )

            # Add question to similarity database
            await self.cog.bot.similarity_service.add_question(
                question_id=attempt.id,
                question_text=self.question.value,
                module_id=self.module_id,
                user_id=user.id,
            )

            # Get updated progress (only counts approved wins)
            wins, target = await self.cog.bot.llm_quiz_service.get_module_progress(
                user.id, self.module_id
            )

            # Build response embed
            embed = self._build_result_embed(result, wins, target, attempt.review_status)
            await interaction.followup.send(embed=embed)

            # If student wins and needs review, send to admin channel
            if result.student_wins and attempt.review_status == ReviewStatus.PENDING:
                await self._send_admin_review_request(
                    interaction, attempt, user.username
                )

            logger.info(
                f"LLM Quiz Challenge for {interaction.user.display_name}: "
                f"{'WIN (pending review)' if result.student_wins else 'LOSE'} (module: {self.module_id})"
            )

        except Exception as e:
            logger.error(f"Error in LLM Quiz Challenge: {e}", exc_info=True)
            try:
                await interaction.followup.send(ERROR_LLM_QUIZ)
            except discord.NotFound:
                pass

    def _build_result_embed(
        self, result, wins: int, target: int, review_status: str = ReviewStatus.AUTO_APPROVED
    ) -> discord.Embed:
        """Build the result embed."""
        if result.student_wins:
            if review_status == ReviewStatus.PENDING:
                color = discord.Color.gold()
                title = "You stumped the AI! (Pending Review)"
            else:
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

        # Show AI's summarized answer with reasoning
        llm_summary = result.llm_answer_summary or result.llm_answer
        if len(llm_summary) > 300:
            llm_summary = llm_summary[:297] + "..."

        embed.add_field(
            name="AI's Answer",
            value=llm_summary,
            inline=False,
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

        # Show concise summary instead of full explanation
        summary_display = result.evaluation_summary or "Evaluation complete."
        if len(summary_display) > 300:
            summary_display = summary_display[:297] + "..."

        embed.add_field(
            name="Evaluation",
            value=summary_display,
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

        # Add pending review notice if applicable
        if review_status == ReviewStatus.PENDING:
            embed.add_field(
                name="Review Status",
                value="Your submission is pending admin review. You'll receive a DM once it's approved or rejected.",
                inline=False,
            )

        return embed

    def _create_progress_bar(self, current: int, target: int) -> str:
        """Create a simple progress bar."""
        filled = min(current, target)
        empty = target - filled
        return "🟩" * filled + "⬜" * empty

    async def _send_admin_review_request(
        self,
        interaction: discord.Interaction,
        attempt,
        student_username: str,
    ):
        """Send a review request to the admin channel."""
        admin_channel_id = self.cog.bot.config.discord.admin_channel_id
        if not admin_channel_id:
            logger.warning("Admin channel not configured - skipping review request")
            return

        try:
            admin_channel = self.cog.bot.get_channel(admin_channel_id)
            if not admin_channel:
                admin_channel = await self.cog.bot.fetch_channel(admin_channel_id)

            if not admin_channel:
                logger.error(f"Could not find admin channel: {admin_channel_id}")
                return

            # Build review embed
            embed = build_review_request_embed(
                attempt=attempt,
                student_username=student_username,
                module_name=self.module_name,
            )

            # Create review view with callback
            view = AdminReviewView(
                attempt_id=attempt.id,
                on_review_callback=self.cog.handle_review_decision,
            )

            await admin_channel.send(embed=embed, view=view)
            logger.info(f"Sent review request for attempt #{attempt.id} to admin channel")

        except Exception as e:
            logger.error(f"Failed to send admin review request: {e}", exc_info=True)


class LLMQuizCog(commands.Cog):
    """Cog for the /llm-quiz command."""

    def __init__(self, bot: "ChibiBot"):
        self.bot = bot

    async def module_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> List[app_commands.Choice[str]]:
        """Autocomplete for module selection."""
        return await module_autocomplete_choices(self.bot.course, current)

    async def handle_review_decision(
        self,
        attempt_id: int,
        review_status: str,
        interaction: discord.Interaction,
    ):
        """Handle admin review decision for an LLM quiz attempt.

        Args:
            attempt_id: The attempt ID to review
            review_status: The selected review status
            interaction: The Discord interaction from the admin
        """
        await interaction.response.defer()

        try:
            # Update the review status in database
            attempt = await self.bot.llm_quiz_repo.update_review_status(
                attempt_id=attempt_id,
                review_status=review_status,
                reviewed_by=str(interaction.user.id),
            )

            if not attempt:
                await interaction.followup.send(
                    f"Could not find attempt #{attempt_id}.",
                    ephemeral=True,
                )
                return

            # Get status display info
            emoji, status_text = get_review_status_display(review_status)

            # Update the original message to show the decision
            embed = interaction.message.embeds[0] if interaction.message.embeds else None
            if embed:
                # Update the embed color and add review decision field
                if review_status in ReviewStatus.APPROVED_STATUSES:
                    embed.color = discord.Color.green()
                else:
                    embed.color = discord.Color.red()

                embed.add_field(
                    name="Review Decision",
                    value=f"{emoji} **{status_text}**\nReviewed by: {interaction.user.mention}",
                    inline=False,
                )

                # Disable the view (remove dropdown)
                await interaction.message.edit(embed=embed, view=None)

            # Send response to admin
            await interaction.followup.send(
                f"{emoji} Attempt #{attempt_id} marked as **{status_text}**",
                ephemeral=True,
            )

            # Send DM to student
            await self._send_student_notification(attempt, review_status)

            logger.info(
                f"Admin {interaction.user.display_name} reviewed attempt #{attempt_id}: {status_text}"
            )

        except Exception as e:
            logger.error(f"Error handling review decision: {e}", exc_info=True)
            try:
                await interaction.followup.send(
                    "An error occurred while processing the review.",
                    ephemeral=True,
                )
            except discord.NotFound:
                pass

    async def _send_student_notification(self, attempt, review_status: str):
        """Send DM notification to student about review decision.

        Args:
            attempt: The reviewed attempt
            review_status: The review decision status
        """
        if not attempt.discord_user_id:
            logger.warning(f"No Discord user ID for attempt #{attempt.id}")
            return

        try:
            # Fetch the user
            user = await self.bot.fetch_user(int(attempt.discord_user_id))
            if not user:
                logger.warning(f"Could not find user {attempt.discord_user_id}")
                return

            # Get module name
            module = self.bot.course.get_module(attempt.module_id)
            module_name = module.name if module else attempt.module_id

            # Get status display
            emoji, status_text = get_review_status_display(review_status)

            # Build DM embed
            if review_status in ReviewStatus.APPROVED_STATUSES:
                color = discord.Color.green()
                title = "Your LLM Quiz Submission Was Approved!"
                description = "Great job! Your question has been reviewed and approved."
                if review_status == ReviewStatus.APPROVED_WITH_BONUS:
                    description = "Excellent work! Your question was exceptional and has been approved with bonus points!"
            else:
                color = discord.Color.red()
                title = "Your LLM Quiz Submission Was Rejected"
                rejection_reasons = {
                    ReviewStatus.REJECTED_CONTENT_MISMATCH: "The question didn't match the expected module content.",
                    ReviewStatus.REJECTED_HEAVY_MATH: "The question requires heavy mathematical computation that isn't appropriate for this quiz.",
                    ReviewStatus.REJECTED_DEADLINE_PASSED: "The submission deadline has passed.",
                }
                description = rejection_reasons.get(
                    review_status,
                    "Your submission was not accepted."
                )

            embed = discord.Embed(
                title=title,
                description=description,
                color=color,
            )

            embed.add_field(
                name="Module",
                value=module_name,
                inline=True,
            )

            embed.add_field(
                name="Status",
                value=f"{emoji} {status_text}",
                inline=True,
            )

            # Truncate question if too long
            question_display = attempt.question
            if len(question_display) > 200:
                question_display = question_display[:197] + "..."

            embed.add_field(
                name="Your Question",
                value=question_display,
                inline=False,
            )

            # Add encouragement for rejections
            if review_status in ReviewStatus.REJECTED_STATUSES:
                embed.set_footer(text="Don't give up! Try submitting a different question.")

            # Send DM
            await user.send(embed=embed)
            logger.info(f"Sent notification DM to user {attempt.discord_user_id}")

        except discord.Forbidden:
            logger.warning(f"Cannot send DM to user {attempt.discord_user_id} - DMs disabled")
        except Exception as e:
            logger.error(f"Failed to send student notification: {e}", exc_info=True)

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
