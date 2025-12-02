"""Quiz tool implementation."""

import logging
import random
from typing import TYPE_CHECKING, Any, Optional

import discord

from ...agent.state import SubAgentState, ToolResult
from ...agent.context_manager import ContextType
from ...constants import ERROR_MODULE_NOT_FOUND, ERROR_NO_CONCEPTS, ERROR_QUIZ
from ...ui.embeds import QuizEmbedBuilder
from ..base import BaseTool, ToolConfig

if TYPE_CHECKING:
    from ...bot import ChibiBot

logger = logging.getLogger(__name__)


class QuizAnswerModal(discord.ui.Modal, title="Quiz"):
    """Modal for submitting a quiz answer."""

    def __init__(
        self,
        tool: "QuizTool",
        db_user_id: int,
        module_id: str,
        concept_id: str,
        concept_name: str,
        concept_description: str,
        question: str,
        correct_answer: Optional[str],
        rag_context: Optional[str] = None,
    ):
        super().__init__()
        self.tool = tool
        self.db_user_id = db_user_id
        self.module_id = module_id
        self.concept_id = concept_id
        self.concept_name = concept_name
        self.concept_description = concept_description
        self.question = question
        self.correct_answer = correct_answer
        self.rag_context = rag_context  # RAG context for evaluation

        # Add question as read-only text display
        question_display = question[:2000] if len(question) > 2000 else question
        self.add_item(discord.ui.TextDisplay(f"**Question:**\n{question_display}"))

        # Add answer input field
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

            # Evaluate the answer with RAG context
            result = await self.tool.bot.quiz_service.evaluate_answer(
                question=self.question,
                student_answer=student_answer,
                concept_name=self.concept_name,
                concept_description=self.concept_description,
                correct_answer=self.correct_answer,
                context=self.rag_context,
            )

            if not result:
                await interaction.followup.send(
                    self.tool.bot.llm_manager.get_error_message()
                )
                return

            # Log attempt and update mastery
            await self.tool.bot.quiz_service.log_attempt_and_update_mastery(
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

            # Log the user's answer and feedback to conversation memory
            status = "PASS" if result.is_correct else ("PARTIAL" if result.is_partial else "FAIL")
            feedback_content = (
                f"[User's Quiz Answer]\n"
                f"Question: {self.question}\n"
                f"User's Answer: {student_answer}\n\n"
                f"[Quiz Feedback - {status} (Score: {result.quality_score}/5)]\n"
                f"Concept: {self.concept_name}\n"
                f"Feedback: {result.feedback}"
            )
            self.tool.bot.log_to_conversation(
                user_id=str(interaction.user.id),
                channel_id=str(interaction.channel.id),
                role="assistant",
                content=feedback_content,
                metadata={"tool": "quiz", "type": "feedback", "is_correct": result.is_correct},
            )

            logger.info(
                f"Quiz evaluated for user {self.db_user_id}: "
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
        tool: "QuizTool",
        db_user_id: int,
        module_id: str,
        concept_id: str,
        concept_name: str,
        concept_description: str,
        question: str,
        correct_answer: Optional[str],
        rag_context: Optional[str] = None,
        timeout: float = 600,  # 10 minutes
    ):
        super().__init__(timeout=timeout)
        self.tool = tool
        self.db_user_id = db_user_id
        self.module_id = module_id
        self.concept_id = concept_id
        self.concept_name = concept_name
        self.concept_description = concept_description
        self.question = question
        self.correct_answer = correct_answer
        self.rag_context = rag_context  # RAG context for evaluation
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
            tool=self.tool,
            db_user_id=self.db_user_id,
            module_id=self.module_id,
            concept_id=self.concept_id,
            concept_name=self.concept_name,
            concept_description=self.concept_description,
            question=self.question,
            correct_answer=self.correct_answer,
            rag_context=self.rag_context,
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


class QuizTool(BaseTool):
    """Quiz tool - generates and evaluates quiz questions.

    This tool wraps the existing QuizService to generate questions
    based on the user's mastery level and evaluate their answers.
    """

    async def execute(self, state: SubAgentState) -> ToolResult:
        """Execute the quiz tool.

        Args:
            state: Sub-agent state with task description and parameters

        Returns:
            ToolResult with quiz question or error
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

            # Get module from parameters or select randomly
            module_id = state.parameters.get("module")
            if module_id:
                module_obj = self.bot.course.get_module(module_id)
            else:
                module_obj = random.choice(self.bot.course.modules)

            if not module_obj:
                await discord_message.reply(ERROR_MODULE_NOT_FOUND, mention_author=False)
                return ToolResult(
                    success=False,
                    result=None,
                    summary="Module not found",
                    error=ERROR_MODULE_NOT_FOUND,
                )

            # Select concept based on mastery level
            concept_obj, selection_reason = await self.bot.quiz_service.select_concept_by_mastery(
                user.id, module_obj
            )

            if not concept_obj:
                await discord_message.reply(ERROR_NO_CONCEPTS, mention_author=False)
                return ToolResult(
                    success=False,
                    result=None,
                    summary="No concepts available",
                    error=ERROR_NO_CONCEPTS,
                )

            # Get context from context manager for quiz generation
            rag_context = None
            if self.bot.context_manager:
                try:
                    context_result = await self.bot.context_manager.get_context_for_quiz(
                        concept=concept_obj,
                        module=module_obj,
                    )
                    if context_result.has_relevant_content:
                        rag_context = context_result.context
                        logger.debug(
                            f"RAG context retrieved for quiz: {context_result.total_chunks} chunks"
                        )
                except Exception as e:
                    logger.warning(f"Failed to get RAG context for quiz: {e}")

            # Generate quiz question with RAG context
            result = await self.bot.quiz_service.generate_question(
                concept_obj, module_obj, context=rag_context
            )

            if not result:
                error_msg = self.bot.llm_manager.get_error_message()
                await discord_message.reply(error_msg, mention_author=False)
                return ToolResult(
                    success=False,
                    result=None,
                    summary="Failed to generate question",
                    error="LLM error",
                )

            question_text, correct_answer = result

            # Create answer button view with RAG context for evaluation
            view = QuizAnswerButton(
                tool=self,
                db_user_id=user.id,
                module_id=module_obj.id,
                concept_id=concept_obj.id,
                concept_name=concept_obj.name,
                concept_description=concept_obj.description,
                question=question_text,
                correct_answer=correct_answer,
                rag_context=rag_context,
            )
            view.original_user_id = int(state.user_id)

            # Send question with answer button
            embed = QuizEmbedBuilder.create_question_embed(
                concept_name=concept_obj.name,
                question_text=question_text,
                module_name=module_obj.name,
                selection_reason=selection_reason,
            )

            await discord_message.reply(embed=embed, view=view, mention_author=False)

            logger.info(f"Quiz generated for {state.user_name}: {concept_obj.name}")

            # Log the question to conversation memory for context
            displayed_content = (
                f"[Quiz Question - {concept_obj.name}]\n"
                f"Module: {module_obj.name}\n"
                f"Question: {question_text}"
            )
            self.bot.log_to_conversation(
                user_id=state.user_id,
                channel_id=str(discord_message.channel.id),
                role="assistant",
                content=displayed_content,
                metadata={"tool": "quiz", "type": "question"},
            )

            return ToolResult(
                success=True,
                result={"question": question_text, "concept": concept_obj.name},
                summary=displayed_content,
                metadata={
                    "db_user_id": user.id,
                    "module_id": module_obj.id,
                    "concept_id": concept_obj.id,
                    "response_sent": True,  # Indicate response was already sent
                },
            )

        except Exception as e:
            logger.error(f"Error in QuizTool: {e}", exc_info=True)
            return ToolResult(
                success=False,
                result=None,
                summary="Error generating quiz",
                error=str(e),
            )


async def create_tool(bot: "ChibiBot", config: ToolConfig) -> QuizTool:
    """Create a QuizTool instance.

    Args:
        bot: ChibiBot instance
        config: Tool configuration

    Returns:
        Configured QuizTool instance
    """
    return QuizTool(bot, config)
