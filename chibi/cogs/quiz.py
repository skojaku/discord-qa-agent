"""Quiz command cog for quiz interactions."""

import logging
import random
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional, TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from ..prompts.templates import PromptTemplates

if TYPE_CHECKING:
    from ..bot import ChibiBot

logger = logging.getLogger(__name__)


@dataclass
class PendingQuiz:
    """Represents a pending quiz awaiting student response."""

    user_id: int
    db_user_id: int
    channel_id: int
    message_id: int
    module_id: str
    concept_id: str
    concept_name: str
    concept_description: str
    quiz_format: str
    question: str
    correct_answer: Optional[str]
    created_at: datetime


class QuizCog(commands.Cog):
    """Cog for the /quiz command."""

    def __init__(self, bot: "ChibiBot"):
        self.bot = bot
        self._pending_quizzes: Dict[int, PendingQuiz] = {}  # user_id -> PendingQuiz
        self._quiz_timeout = timedelta(minutes=30)

    async def module_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> List[app_commands.Choice[str]]:
        """Autocomplete for module selection."""
        if not self.bot.course:
            return []

        choices = []
        for module in self.bot.course.modules:
            display_name = f"{module.id}: {module.name}"
            if current.lower() in display_name.lower():
                choices.append(
                    app_commands.Choice(name=display_name[:100], value=module.id)
                )

        return choices[:25]

    async def _select_concept_by_mastery(self, user_id: int, module) -> tuple:
        """Select a concept based on mastery level.

        Priority:
        1. Concepts not yet attempted (novice with 0 attempts)
        2. Concepts with low mastery (learning, novice)
        3. Concepts needing reinforcement (proficient)
        4. Random from mastered (for review)

        Returns:
            Tuple of (concept, selection_reason)
        """
        if not module.concepts:
            return None, ""

        # Get mastery for all concepts in this module
        concept_scores = []
        for concept in module.concepts:
            mastery = await self.bot.repository.get_or_create_mastery(user_id, concept.id)

            # Calculate priority score (lower = higher priority for quizzing)
            if mastery.total_attempts == 0:
                score = 0  # Highest priority: never attempted
                reason = "New concept"
            elif mastery.mastery_level == "novice":
                score = 1
                reason = "Needs practice"
            elif mastery.mastery_level == "learning":
                score = 2
                reason = "Building understanding"
            elif mastery.mastery_level == "proficient":
                score = 3
                reason = "Reinforcement"
            else:  # mastered
                score = 4
                reason = "Review"

            concept_scores.append((concept, score, mastery.total_attempts, reason))

        # Sort by score (ascending), then by attempts (ascending)
        concept_scores.sort(key=lambda x: (x[1], x[2]))

        # Get concepts with the lowest score
        min_score = concept_scores[0][1]
        candidates = [(c, r) for c, s, _, r in concept_scores if s == min_score]

        # Random selection from candidates
        selected = random.choice(candidates)
        return selected[0], selected[1]

    @app_commands.command(name="quiz", description="Test your knowledge with a quiz question")
    @app_commands.describe(
        module="Module to quiz on (optional - selects based on your progress)",
    )
    @app_commands.autocomplete(module=module_autocomplete)
    async def quiz(
        self,
        interaction: discord.Interaction,
        module: str = None,
    ):
        """Generate a quiz question."""
        try:
            await interaction.response.defer(thinking=True)
        except discord.NotFound:
            logger.warning("Interaction expired before defer (network latency)")
            return
        except Exception as e:
            logger.error(f"Failed to defer interaction: {e}")
            return

        try:
            # Get or create user
            user = await self.bot.repository.get_or_create_user(
                discord_id=str(interaction.user.id),
                username=interaction.user.display_name,
            )

            # Select module
            if module:
                module_obj = self.bot.course.get_module(module)
            else:
                module_obj = random.choice(self.bot.course.modules)

            if not module_obj:
                await interaction.followup.send(
                    "Could not find the specified module. Please try again! 📚"
                )
                return

            # Select concept based on mastery level
            concept_obj, selection_reason = await self._select_concept_by_mastery(user.id, module_obj)

            if not concept_obj:
                await interaction.followup.send(
                    "No concepts found for this module. Please try a different module! 📖"
                )
                return

            # Always use free-form format
            quiz_format = "free-form"

            # Generate quiz question
            quiz_prompt = PromptTemplates.get_quiz_prompt(
                concept_name=concept_obj.name,
                concept_description=concept_obj.description,
                quiz_focus=concept_obj.quiz_focus,
                quiz_format=quiz_format,
                module_content=module_obj.content or "",
            )

            response = await self.bot.llm_manager.generate(
                prompt=quiz_prompt,
                max_tokens=self.bot.config.llm.max_tokens,
                temperature=0.8,  # Slightly higher for variety
            )

            if not response:
                await interaction.followup.send(
                    self.bot.llm_manager.get_error_message()
                )
                return

            # Parse correct answer from response if present
            question_text = response.content
            correct_answer = self._extract_correct_answer(question_text, quiz_format)

            # Remove the answer marker from the question shown to student
            question_text = self._clean_question(question_text)

            # Send question
            embed = discord.Embed(
                title=f"📝 Quiz: {concept_obj.name}",
                description=question_text,
                color=discord.Color.blue(),
            )
            embed.set_footer(
                text=f"Module: {module_obj.name} | {selection_reason}\n"
                f"Reply to this message with your answer!"
            )

            message = await interaction.followup.send(embed=embed)

            # Add to conversation history for context
            chat_cog = self.bot.get_cog("ChatCog")
            if chat_cog:
                chat_cog.add_bot_message(interaction.channel_id, f"[Quiz Question] {question_text}")

            # Store pending quiz
            self._pending_quizzes[interaction.user.id] = PendingQuiz(
                user_id=interaction.user.id,
                db_user_id=user.id,
                channel_id=interaction.channel_id,
                message_id=message.id,
                module_id=module_obj.id,
                concept_id=concept_obj.id,
                concept_name=concept_obj.name,
                concept_description=concept_obj.description,
                quiz_format=quiz_format,
                question=question_text,
                correct_answer=correct_answer,
                created_at=datetime.now(),
            )

            logger.info(
                f"Quiz generated for {interaction.user.display_name}: "
                f"{concept_obj.name} ({quiz_format})"
            )

        except Exception as e:
            logger.error(f"Error in /quiz command: {e}", exc_info=True)
            await interaction.followup.send(
                "Oops! Something went wrong while generating your quiz. "
                "Please try again! 🔧"
            )

    def _extract_correct_answer(self, text: str, quiz_format: str) -> Optional[str]:
        """Extract the correct answer from the LLM response."""
        patterns = {
            "multiple-choice": r"\[CORRECT:\s*([A-D])\]",
            "short-answer": r"\[EXPECTED:\s*(.+?)\]",
            "true-false": r"\[CORRECT:\s*(True|False)\]",
            "fill-blank": r"\[ANSWER:\s*(.+?)\]",
        }

        pattern = patterns.get(quiz_format)
        if pattern:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()

        return None

    def _clean_question(self, text: str) -> str:
        """Remove answer markers from question text."""
        # Remove various answer format markers
        patterns = [
            r"\[CORRECT:\s*[A-D]\]",
            r"\[CORRECT:\s*(?:True|False)\]",
            r"\[EXPECTED:\s*.+?\]",
            r"\[ANSWER:\s*.+?\]",
        ]
        for pattern in patterns:
            text = re.sub(pattern, "", text, flags=re.IGNORECASE)
        return text.strip()

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Listen for quiz answers."""
        # Ignore bot messages
        if message.author.bot:
            return

        # Check if user has a pending quiz
        user_id = message.author.id
        if user_id not in self._pending_quizzes:
            return

        pending = self._pending_quizzes[user_id]

        # Check if quiz has expired
        if datetime.now() - pending.created_at > self._quiz_timeout:
            del self._pending_quizzes[user_id]
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

        # Process the answer
        await self._evaluate_answer(message, pending)

        # Remove pending quiz
        del self._pending_quizzes[user_id]

    async def _evaluate_answer(self, message: discord.Message, pending: PendingQuiz):
        """Evaluate a student's quiz answer."""
        student_answer = message.content

        # Show typing indicator
        async with message.channel.typing():
            # Build evaluation prompt
            eval_prompt = PromptTemplates.get_evaluation_prompt(
                question=pending.question,
                student_answer=student_answer,
                concept_name=pending.concept_name,
                concept_description=pending.concept_description,
                correct_answer=pending.correct_answer or "",
            )

            response = await self.bot.llm_manager.generate(
                prompt=eval_prompt,
                max_tokens=self.bot.config.llm.max_tokens,
                temperature=0.3,  # Lower for more consistent evaluation
            )

            if not response:
                await message.reply(self.bot.llm_manager.get_error_message())
                return

            # Parse evaluation response
            eval_text = response.content
            lines = eval_text.strip().split("\n")

            is_correct = False
            is_partial = False
            quality_score = 0
            feedback = eval_text
            result_status = "FAIL"

            if lines:
                first_line = lines[0].upper().strip()
                if first_line == "PASS":
                    is_correct = True
                    result_status = "PASS"
                elif first_line == "PARTIAL":
                    is_partial = True
                    result_status = "PARTIAL"
                else:
                    result_status = "FAIL"

                # Try to get quality score from second line
                if len(lines) > 1:
                    try:
                        quality_score = int(lines[1].strip())
                        quality_score = max(1, min(5, quality_score))  # Clamp 1-5
                        # Feedback starts from line 3
                        feedback = "\n".join(lines[2:]).strip()
                    except ValueError:
                        # No quality score, feedback starts from line 2
                        feedback = "\n".join(lines[1:]).strip()

            # For mastery: count PASS and PARTIAL as correct
            counts_as_correct = is_correct or is_partial

            # Log quiz attempt
            await self.bot.repository.log_quiz_attempt(
                user_id=pending.db_user_id,
                module_id=pending.module_id,
                concept_id=pending.concept_id,
                quiz_format=pending.quiz_format,
                question=pending.question,
                user_answer=student_answer,
                correct_answer=pending.correct_answer,
                is_correct=counts_as_correct,
                llm_feedback=feedback,
                llm_quality_score=quality_score if quality_score > 0 else None,
            )

            # Update mastery
            await self._update_mastery(
                pending.db_user_id,
                pending.concept_id,
                counts_as_correct,
                quality_score,
            )

            # Send feedback with clear pass/fail status
            if result_status == "PASS":
                color = discord.Color.green()
                title = f"✅ PASS (Score: {quality_score}/5)"
            elif result_status == "PARTIAL":
                color = discord.Color.gold()
                title = f"🔶 PARTIAL (Score: {quality_score}/5)"
            else:
                color = discord.Color.red()
                title = f"❌ FAIL (Score: {quality_score}/5)"

            embed = discord.Embed(
                title=title,
                description=feedback if feedback else eval_text,
                color=color,
            )
            embed.set_footer(text=f"Concept: {pending.concept_name}")

            await message.reply(embed=embed)

            # Add to conversation history for context
            chat_cog = self.bot.get_cog("ChatCog")
            if chat_cog:
                chat_cog.add_bot_message(
                    message.channel.id,
                    f"[Quiz Feedback - {result_status}] {feedback if feedback else eval_text}"
                )

            logger.info(
                f"Quiz evaluated for user {message.author.display_name}: "
                f"{pending.concept_name} - {'correct' if is_correct else 'incorrect'}"
            )

    async def _update_mastery(
        self,
        user_id: int,
        concept_id: str,
        is_correct: bool,
        quality_score: int,
    ):
        """Update concept mastery after a quiz attempt."""
        # Get current mastery
        mastery = await self.bot.repository.get_or_create_mastery(user_id, concept_id)

        # Update counts
        new_total = mastery.total_attempts + 1
        new_correct = mastery.correct_attempts + (1 if is_correct else 0)

        # Update average quality score
        if quality_score > 0:
            if mastery.avg_quality_score > 0:
                new_avg = (
                    mastery.avg_quality_score * mastery.total_attempts + quality_score
                ) / new_total
            else:
                new_avg = float(quality_score)
        else:
            new_avg = mastery.avg_quality_score

        # Calculate new mastery level
        new_level = self._calculate_mastery_level(new_total, new_correct, new_avg)

        # Update database
        await self.bot.repository.update_mastery(
            user_id=user_id,
            concept_id=concept_id,
            total_attempts=new_total,
            correct_attempts=new_correct,
            avg_quality_score=new_avg,
            mastery_level=new_level,
        )

    def _calculate_mastery_level(
        self, total: int, correct: int, avg_quality: float
    ) -> str:
        """Calculate mastery level based on performance."""
        config = self.bot.config.mastery

        if total < config.min_attempts_for_mastery:
            return "novice"

        ratio = correct / total if total > 0 else 0

        # Hybrid: both ratio and quality must meet thresholds
        if ratio >= 0.85 and avg_quality >= 4.0:
            return "mastered"
        elif ratio >= 0.6:
            return "proficient"
        elif ratio >= 0.3:
            return "learning"
        else:
            return "novice"


async def setup(bot: "ChibiBot"):
    """Set up the Quiz cog."""
    await bot.add_cog(QuizCog(bot))
