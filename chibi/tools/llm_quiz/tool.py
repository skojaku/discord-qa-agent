"""LLM Quiz Challenge tool implementation."""

import logging
from typing import TYPE_CHECKING, Optional

import discord

from ...agent.state import SubAgentState, ToolResult
from ...agent.context_manager import ContextType
from ...constants import ERROR_MODULE_NOT_FOUND
from ..base import BaseTool, ToolConfig

if TYPE_CHECKING:
    from ...bot import ChibiBot

logger = logging.getLogger(__name__)

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

    def __init__(
        self,
        tool: "LLMQuizTool",
        user_id: str,
        user_name: str,
        module_id: str,
        module_name: str,
        module_content: Optional[str],
    ):
        super().__init__()
        self.tool = tool
        self.user_id = user_id
        self.user_name = user_name
        self.module_id = module_id
        self.module_name = module_name
        self.module_content = module_content

    async def on_submit(self, interaction: discord.Interaction):
        """Handle modal submission."""
        await interaction.response.defer(thinking=True)

        try:
            # Log the user's question and answer to conversation memory
            self.tool.bot.log_to_conversation(
                user_id=self.user_id,
                channel_id=str(interaction.channel.id),
                role="user",
                content=(
                    f"LLM Quiz Challenge for {self.module_name}:\n"
                    f"My question: {self.question.value}\n"
                    f"My answer: {self.answer.value}"
                ),
            )

            # Get or create user
            user = await self.tool.bot.user_repo.get_or_create(
                discord_id=self.user_id,
                username=self.user_name,
            )

            # Check for similar questions
            similarity_result = await self.tool.bot.similarity_service.check_similarity(
                question=self.question.value,
                module_id=self.module_id,
            )

            if similarity_result.is_similar:
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

                # Log the rejection to conversation memory
                rejected_content = (
                    f"[LLM Quiz Challenge - Question Rejected]\n"
                    f"Reason: Your question is too similar to a previously submitted question. "
                    f"Please try a more unique question!"
                )
                self.tool.bot.log_to_conversation(
                    user_id=self.user_id,
                    channel_id=str(interaction.channel.id),
                    role="assistant",
                    content=rejected_content,
                    metadata={"tool": "llm_quiz", "rejected": True},
                )

                logger.info(
                    f"LLM Quiz rejected for {self.user_name}: "
                    f"similarity {similarity_result.highest_similarity:.2f} "
                    f"(module: {self.module_id})"
                )
                return

            # Get RAG context for the user's question
            rag_context = None
            if self.tool.bot.context_manager:
                try:
                    module_obj = self.tool.bot.course.get_module(self.module_id)
                    if module_obj:
                        context_result = await self.tool.bot.context_manager.get_context_for_llm_quiz(
                            question=self.question.value,
                            module=module_obj,
                        )
                        if context_result.has_relevant_content:
                            rag_context = context_result.context
                            logger.debug(
                                f"RAG context retrieved for LLM quiz: {context_result.total_chunks} chunks"
                            )
                except Exception as e:
                    logger.warning(f"Failed to get RAG context for LLM quiz: {e}")

            # Run the challenge with RAG context
            result = await self.tool.bot.llm_quiz_service.challenge_llm(
                question=self.question.value,
                student_answer=self.answer.value,
                module_content=self.module_content,
                rag_context=rag_context,
            )

            # Log the attempt (requires review if student wins)
            attempt = await self.tool.bot.llm_quiz_service.log_attempt(
                user_id=user.id,
                module_id=self.module_id,
                question=self.question.value,
                student_answer=self.answer.value,
                result=result,
                discord_user_id=self.user_id,
                requires_review=result.student_wins,  # Only require review for wins
            )

            # Only add question to similarity database if student won
            # This prevents failed questions from blocking similar good questions
            if result.student_wins:
                await self.tool.bot.similarity_service.add_question(
                    question_id=attempt.id,
                    question_text=self.question.value,
                    module_id=self.module_id,
                    user_id=user.id,
                )

                # Send notification to admin channel
                await self._notify_admin_channel(
                    interaction=interaction,
                    attempt_id=attempt.id,
                    result=result,
                )

            # Get updated progress
            wins, target = await self.tool.bot.llm_quiz_service.get_module_progress(
                user.id, self.module_id
            )

            # Build response embed
            embed = self._build_result_embed(result, wins, target)
            await interaction.followup.send(embed=embed)

            # Log the challenge result to conversation memory
            outcome = "WIN - You stumped the AI!" if result.student_wins else "LOSE - The AI got it right"
            challenge_content = (
                f"[LLM Quiz Challenge Result - {outcome}]\n"
                f"AI's Answer: {result.llm_answer_summary}\n"
                f"Evaluation: {result.evaluation_summary}\n"
                f"Progress: {wins}/{target} wins for {self.module_name}"
            )
            self.tool.bot.log_to_conversation(
                user_id=self.user_id,
                channel_id=str(interaction.channel.id),
                role="assistant",
                content=challenge_content,
                metadata={"tool": "llm_quiz", "student_wins": result.student_wins},
            )

            logger.info(
                f"LLM Quiz Challenge for {self.user_name}: "
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

        # Show AI's summarized answer
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
            value=correctness_emoji.get(
                result.student_answer_correctness, result.student_answer_correctness
            ),
            inline=True,
        )

        # Show concise summary
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

        return embed

    def _create_progress_bar(self, current: int, target: int) -> str:
        """Create a simple progress bar."""
        filled = min(current, target)
        empty = target - filled
        return "[X]" * filled + "[ ]" * empty

    async def _notify_admin_channel(
        self,
        interaction: discord.Interaction,
        attempt_id: int,
        result,
    ) -> None:
        """Send a review notification to the admin channel with interactive dropdown."""
        from ...ui.views.admin_review import AdminReviewView

        admin_channel_id = self.tool.bot.config.admin_channel_id
        if not admin_channel_id:
            logger.debug("No admin channel configured, skipping review notification")
            return

        try:
            admin_channel = self.tool.bot.get_channel(int(admin_channel_id))
            if not admin_channel:
                logger.warning(f"Admin channel {admin_channel_id} not found")
                return

            # Build review embed
            embed = discord.Embed(
                title="🎯 LLM Quiz Review Request",
                description=f"**{self.user_name}** stumped the AI and needs review!",
                color=discord.Color.gold(),
            )

            embed.add_field(
                name="Student",
                value=f"**{self.user_name}** (<@{self.user_id}>)",
                inline=True,
            )

            embed.add_field(
                name="Module",
                value=self.module_name,
                inline=True,
            )

            embed.add_field(
                name="Attempt ID",
                value=f"`#{attempt_id}`",
                inline=True,
            )

            # Student's question
            question_display = self.question.value
            if len(question_display) > 500:
                question_display = question_display[:497] + "..."
            embed.add_field(
                name="Question",
                value=question_display,
                inline=False,
            )

            # Student's answer
            answer_display = self.answer.value
            if len(answer_display) > 300:
                answer_display = answer_display[:297] + "..."
            embed.add_field(
                name="Student's Answer",
                value=answer_display,
                inline=False,
            )

            # AI's answer
            llm_answer = result.llm_answer_summary or result.llm_answer
            if len(llm_answer) > 300:
                llm_answer = llm_answer[:297] + "..."
            embed.add_field(
                name="AI's Answer",
                value=llm_answer,
                inline=False,
            )

            if result.evaluation_summary:
                eval_display = result.evaluation_summary
                if len(eval_display) > 300:
                    eval_display = eval_display[:297] + "..."
                embed.add_field(
                    name="Evaluation Summary",
                    value=eval_display,
                    inline=False,
                )

            embed.set_footer(text="Select a review decision from the dropdown below")

            # Create the review view with callback
            async def on_review(attempt_id: int, decision: str, inter: discord.Interaction):
                await self._handle_review_decision(attempt_id, decision, inter)

            view = AdminReviewView(attempt_id, on_review)

            await admin_channel.send(embed=embed, view=view)
            logger.info(f"Review notification sent for attempt {attempt_id}")

        except Exception as e:
            logger.error(f"Failed to send admin notification: {e}", exc_info=True)

    async def _handle_review_decision(
        self,
        attempt_id: int,
        decision: str,
        interaction: discord.Interaction,
    ) -> None:
        """Handle admin review decision."""
        from ...database.models import ReviewStatus

        try:
            # Update the attempt in database
            await self.tool.bot.llm_quiz_repo.update_review_status(
                attempt_id=attempt_id,
                review_status=decision,
                reviewed_by=str(interaction.user.id),
            )

            # Get status display
            status_emoji = {
                ReviewStatus.APPROVED: "✅",
                ReviewStatus.APPROVED_WITH_BONUS: "🌟",
                ReviewStatus.REJECTED_CONTENT_MISMATCH: "❌",
                ReviewStatus.REJECTED_HEAVY_MATH: "🔢",
                ReviewStatus.REJECTED_DEADLINE_PASSED: "⏰",
            }

            emoji = status_emoji.get(decision, "✅")
            await interaction.response.send_message(
                f"{emoji} Review submitted: **{decision}** for attempt #{attempt_id}",
                ephemeral=True,
            )

            # Update the original message to show it's been reviewed
            try:
                original_embed = interaction.message.embeds[0]
                original_embed.color = discord.Color.green() if "approved" in decision.lower() else discord.Color.red()
                original_embed.set_footer(text=f"Reviewed by {interaction.user.display_name}: {decision}")

                # Disable the view
                view = discord.ui.View()
                await interaction.message.edit(embed=original_embed, view=view)
            except Exception as e:
                logger.warning(f"Could not update review message: {e}")

            # Notify the student via DM if they won and it was approved
            if decision in [ReviewStatus.APPROVED, ReviewStatus.APPROVED_WITH_BONUS]:
                await self._notify_student_approval(attempt_id, decision)

            logger.info(f"Admin {interaction.user} reviewed attempt {attempt_id}: {decision}")

        except Exception as e:
            logger.error(f"Error handling review decision: {e}", exc_info=True)
            await interaction.response.send_message(
                f"❌ Error processing review: {str(e)}",
                ephemeral=True,
            )

    async def _notify_student_approval(self, attempt_id: int, decision: str) -> None:
        """Notify student that their submission was approved."""
        from ...database.models import ReviewStatus

        try:
            # Get the attempt to find the student
            attempt = await self.tool.bot.llm_quiz_repo.get_by_id(attempt_id)
            if not attempt or not attempt.discord_user_id:
                return

            user = self.tool.bot.get_user(int(attempt.discord_user_id))
            if not user:
                user = await self.tool.bot.fetch_user(int(attempt.discord_user_id))

            if not user:
                logger.warning(f"Could not find user {attempt.discord_user_id} to notify")
                return

            # Build notification message
            if decision == ReviewStatus.APPROVED_WITH_BONUS:
                message = (
                    f"🌟 **Great news!** Your LLM Quiz submission has been approved with bonus points!\n\n"
                    f"Your question successfully stumped the AI and was particularly impressive."
                )
            else:
                message = (
                    f"✅ **Your LLM Quiz submission has been approved!**\n\n"
                    f"Your question successfully stumped the AI."
                )

            await user.send(message)
            logger.info(f"Sent approval notification to user {attempt.discord_user_id}")

        except discord.Forbidden:
            logger.warning(f"Cannot DM user {attempt.discord_user_id} - DMs disabled")
        except Exception as e:
            logger.error(f"Error notifying student: {e}", exc_info=True)


class LLMQuizTool(BaseTool):
    """LLM Quiz Challenge tool - stump the AI!

    This tool allows students to create challenging questions
    to try to stump the LLM and earn points.
    """

    async def execute(self, state: SubAgentState) -> ToolResult:
        """Execute the LLM Quiz Challenge tool.

        Args:
            state: Sub-agent state with task description and parameters

        Returns:
            ToolResult indicating modal was shown
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

            # Get module from parameters
            module_id = state.parameters.get("module")
            if not module_id:
                # Build list of available modules
                module_list = ", ".join(
                    f"`{m.id}`" for m in self.bot.course.modules[:5]
                )
                if len(self.bot.course.modules) > 5:
                    module_list += f", ... ({len(self.bot.course.modules)} total)"

                await discord_message.reply(
                    f"Please specify a module to challenge the AI on!\n\n"
                    f"**Available modules:** {module_list}\n\n"
                    f"**Examples:**\n"
                    f"• \"LLM quiz on module-1\"\n"
                    f"• \"Challenge the AI on m02\"\n"
                    f"• Use `/modules` to see all available modules",
                    mention_author=False,
                )
                return ToolResult(
                    success=True,  # Mark as success since we sent a helpful response
                    result=None,
                    summary="Prompted user to specify module",
                    metadata={"response_sent": True},
                )

            module_obj = self.bot.course.get_module(module_id)
            if not module_obj:
                # Build list of available modules
                module_list = ", ".join(
                    f"`{m.id}`" for m in self.bot.course.modules[:5]
                )
                if len(self.bot.course.modules) > 5:
                    module_list += f", ... ({len(self.bot.course.modules)} total)"

                await discord_message.reply(
                    f"Module `{module_id}` not found.\n\n"
                    f"**Available modules:** {module_list}\n\n"
                    f"Use `/modules` to see all available modules.",
                    mention_author=False,
                )
                return ToolResult(
                    success=True,  # Mark as success since we sent a helpful response
                    result=None,
                    summary=f"Module {module_id} not found - showed available modules",
                    metadata={"response_sent": True},
                )

            # For natural language routing, we need to show a modal
            # But modals require an Interaction, not a Message
            # So we'll create a button that opens the modal
            view = LLMQuizStartButton(
                tool=self,
                user_id=state.user_id,
                user_name=state.user_name,
                module_id=module_obj.id,
                module_name=module_obj.name,
                module_content=module_obj.content,
            )
            view.original_user_id = int(state.user_id)

            embed = discord.Embed(
                title="LLM Quiz Challenge",
                description=f"Challenge the AI on **{module_obj.name}**!\n\n"
                "Click the button below to submit your challenging question.",
                color=discord.Color.blue(),
            )

            await discord_message.reply(embed=embed, view=view, mention_author=False)

            return ToolResult(
                success=True,
                result=None,
                summary=f"LLM Quiz Challenge started for {module_obj.name}",
                metadata={
                    "module_id": module_obj.id,
                    "response_sent": True,
                },
            )

        except Exception as e:
            logger.error(f"Error in LLMQuizTool: {e}", exc_info=True)
            return ToolResult(
                success=False,
                result=None,
                summary="Error starting LLM Quiz Challenge",
                error=str(e),
            )


class LLMQuizStartButton(discord.ui.View):
    """View with a button to start the LLM Quiz Challenge."""

    def __init__(
        self,
        tool: "LLMQuizTool",
        user_id: str,
        user_name: str,
        module_id: str,
        module_name: str,
        module_content: Optional[str],
        timeout: float = 300,
    ):
        super().__init__(timeout=timeout)
        self.tool = tool
        self.user_id = user_id
        self.user_name = user_name
        self.module_id = module_id
        self.module_name = module_name
        self.module_content = module_content
        self.original_user_id: Optional[int] = None
        self.started = False

    @discord.ui.button(
        label="Start Challenge",
        style=discord.ButtonStyle.primary,
        emoji="🎯",
    )
    async def start_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """Open the challenge modal when clicked."""
        if self.original_user_id and interaction.user.id != self.original_user_id:
            await interaction.response.send_message(
                "This challenge is for another user!", ephemeral=True
            )
            return

        if self.started:
            await interaction.response.send_message(
                "You've already started this challenge!", ephemeral=True
            )
            return

        modal = LLMQuizModal(
            tool=self.tool,
            user_id=self.user_id,
            user_name=self.user_name,
            module_id=self.module_id,
            module_name=self.module_name,
            module_content=self.module_content,
        )
        await interaction.response.send_modal(modal)
        self.started = True

        button.disabled = True
        button.label = "Challenge Started"
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


async def create_tool(bot: "ChibiBot", config: ToolConfig) -> LLMQuizTool:
    """Create a LLMQuizTool instance.

    Args:
        bot: ChibiBot instance
        config: Tool configuration

    Returns:
        Configured LLMQuizTool instance
    """
    return LLMQuizTool(bot, config)
