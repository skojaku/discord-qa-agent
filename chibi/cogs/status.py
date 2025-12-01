"""Status command cog for learning progress tracking."""

import logging
from typing import Literal, TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

if TYPE_CHECKING:
    from ..bot import ChibiBot

logger = logging.getLogger(__name__)


class StatusCog(commands.Cog):
    """Cog for the /status command."""

    def __init__(self, bot: "ChibiBot"):
        self.bot = bot

    @app_commands.command(name="status", description="View your learning progress")
    @app_commands.describe(
        view="What kind of status to show",
    )
    async def status(
        self,
        interaction: discord.Interaction,
        view: Literal["summary", "detailed", "recent", "concepts"] = "summary",
    ):
        """Show learning status and progress."""
        await interaction.response.defer(thinking=True)

        try:
            # Get or create user
            user = await self.bot.repository.get_or_create_user(
                discord_id=str(interaction.user.id),
                username=interaction.user.display_name,
            )

            if view == "summary":
                embed = await self._build_summary_embed(user.id, interaction.user)
            elif view == "detailed":
                embed = await self._build_detailed_embed(user.id, interaction.user)
            elif view == "recent":
                embed = await self._build_recent_embed(user.id, interaction.user)
            elif view == "concepts":
                embed = await self._build_concepts_embed(user.id, interaction.user)
            else:
                embed = await self._build_summary_embed(user.id, interaction.user)

            await interaction.followup.send(embed=embed)

        except Exception as e:
            logger.error(f"Error in /status command: {e}", exc_info=True)
            await interaction.followup.send(
                "Oops! Something went wrong while fetching your status. "
                "Please try again! 🔧"
            )

    async def _build_summary_embed(
        self, user_id: int, discord_user: discord.User
    ) -> discord.Embed:
        """Build summary status embed."""
        summary = await self.bot.repository.get_mastery_summary(user_id)

        total_concepts = len(self.bot.course.get_all_concepts())
        concepts_started = (
            summary.get("novice", 0)
            + summary.get("learning", 0)
            + summary.get("proficient", 0)
            + summary.get("mastered", 0)
        )

        embed = discord.Embed(
            title=f"📊 Learning Progress - {discord_user.display_name}",
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

        # Quiz stats
        total_quizzes = summary.get("total_quiz_attempts", 0)
        correct = summary.get("total_correct", 0)
        accuracy = correct / total_quizzes * 100 if total_quizzes > 0 else 0

        embed.add_field(
            name="Quiz Performance",
            value=f"**{total_quizzes}** quizzes taken\n"
            f"**{accuracy:.1f}%** accuracy",
            inline=True,
        )

        # Mastery breakdown
        mastery_bar = self._create_progress_bar(
            mastered, proficient, summary.get("learning", 0), summary.get("novice", 0)
        )
        embed.add_field(
            name="Mastery Levels",
            value=f"```\n{mastery_bar}\n```\n"
            f"🏆 Mastered: {mastered}\n"
            f"⭐ Proficient: {proficient}\n"
            f"📖 Learning: {summary.get('learning', 0)}\n"
            f"🌱 Novice: {summary.get('novice', 0)}",
            inline=False,
        )

        embed.set_footer(text="Use /status detailed for more info | /status concepts for concept breakdown")

        return embed

    async def _build_detailed_embed(
        self, user_id: int, discord_user: discord.User
    ) -> discord.Embed:
        """Build detailed status embed with module breakdown."""
        embed = discord.Embed(
            title=f"📈 Detailed Progress - {discord_user.display_name}",
            color=discord.Color.blue(),
        )

        # Get all mastery records
        mastery_records = await self.bot.repository.get_user_mastery_all(user_id)
        mastery_by_concept = {m.concept_id: m for m in mastery_records}

        # Group by module
        for module in self.bot.course.modules:
            module_concepts = []
            for concept in module.concepts:
                mastery = mastery_by_concept.get(concept.id)
                if mastery:
                    emoji = self._get_mastery_emoji(mastery.mastery_level)
                    accuracy = (
                        mastery.correct_attempts / mastery.total_attempts * 100
                        if mastery.total_attempts > 0
                        else 0
                    )
                    module_concepts.append(
                        f"{emoji} {concept.name} ({accuracy:.0f}% - {mastery.total_attempts} attempts)"
                    )
                else:
                    module_concepts.append(f"⬜ {concept.name} (not started)")

            if module_concepts:
                embed.add_field(
                    name=f"📚 {module.name}",
                    value="\n".join(module_concepts[:10]),  # Limit to 10
                    inline=False,
                )

        embed.set_footer(text="Use /quiz to practice concepts")

        return embed

    async def _build_recent_embed(
        self, user_id: int, discord_user: discord.User
    ) -> discord.Embed:
        """Build recent activity embed."""
        embed = discord.Embed(
            title=f"🕐 Recent Activity - {discord_user.display_name}",
            color=discord.Color.blue(),
        )

        # Recent quiz attempts
        recent_quizzes = await self.bot.repository.get_recent_quiz_attempts(
            user_id, limit=5
        )

        if recent_quizzes:
            quiz_lines = []
            for quiz in recent_quizzes:
                emoji = "✅" if quiz.is_correct else "❌"
                time_str = quiz.created_at.strftime("%m/%d %H:%M") if quiz.created_at else "Unknown"
                quiz_lines.append(
                    f"{emoji} **{quiz.concept_id}** ({quiz.quiz_format}) - {time_str}"
                )

            embed.add_field(
                name="Recent Quizzes",
                value="\n".join(quiz_lines),
                inline=False,
            )
        else:
            embed.add_field(
                name="Recent Quizzes",
                value="No quiz attempts yet. Try /quiz to get started! 📝",
                inline=False,
            )

        # Recent interactions
        recent_interactions = await self.bot.repository.get_recent_interactions(
            user_id, limit=5
        )

        if recent_interactions:
            interaction_lines = []
            for interaction in recent_interactions:
                time_str = (
                    interaction.created_at.strftime("%m/%d %H:%M")
                    if interaction.created_at
                    else "Unknown"
                )
                question_preview = (
                    interaction.question[:50] + "..."
                    if len(interaction.question) > 50
                    else interaction.question
                )
                interaction_lines.append(
                    f"💬 **{interaction.module_id}**: {question_preview} - {time_str}"
                )

            embed.add_field(
                name="Recent Questions",
                value="\n".join(interaction_lines),
                inline=False,
            )
        else:
            embed.add_field(
                name="Recent Questions",
                value="No questions asked yet. Try /ask to learn! 🤔",
                inline=False,
            )

        return embed

    async def _build_concepts_embed(
        self, user_id: int, discord_user: discord.User
    ) -> discord.Embed:
        """Build concepts mastery embed."""
        embed = discord.Embed(
            title=f"🎯 Concept Mastery - {discord_user.display_name}",
            color=discord.Color.blue(),
        )

        # Get all mastery records
        mastery_records = await self.bot.repository.get_user_mastery_all(user_id)

        if not mastery_records:
            embed.description = (
                "You haven't started any concepts yet!\n\n"
                "Use `/quiz` to start practicing and track your progress. 🚀"
            )
            return embed

        # Group by mastery level
        levels = {
            "mastered": [],
            "proficient": [],
            "learning": [],
            "novice": [],
        }

        all_concepts = self.bot.course.get_all_concepts()

        for mastery in mastery_records:
            concept = all_concepts.get(mastery.concept_id)
            if concept:
                levels[mastery.mastery_level].append(
                    f"**{concept.name}** ({mastery.correct_attempts}/{mastery.total_attempts})"
                )

        # Add fields for each level
        level_info = [
            ("🏆 Mastered", "mastered"),
            ("⭐ Proficient", "proficient"),
            ("📖 Learning", "learning"),
            ("🌱 Novice", "novice"),
        ]

        for title, level in level_info:
            concepts = levels[level]
            if concepts:
                embed.add_field(
                    name=f"{title} ({len(concepts)})",
                    value="\n".join(concepts[:8]),  # Limit to 8 per level
                    inline=False,
                )

        embed.set_footer(text="Keep practicing to level up your concepts! 💪")

        return embed

    def _get_mastery_emoji(self, level: str) -> str:
        """Get emoji for mastery level."""
        return {
            "mastered": "🏆",
            "proficient": "⭐",
            "learning": "📖",
            "novice": "🌱",
        }.get(level, "⬜")

    def _create_progress_bar(
        self, mastered: int, proficient: int, learning: int, novice: int
    ) -> str:
        """Create a visual progress bar."""
        total = mastered + proficient + learning + novice
        if total == 0:
            return "[ No data yet ]"

        bar_length = 20
        m_len = int(mastered / total * bar_length)
        p_len = int(proficient / total * bar_length)
        l_len = int(learning / total * bar_length)
        n_len = bar_length - m_len - p_len - l_len

        return (
            "["
            + "█" * m_len
            + "▓" * p_len
            + "▒" * l_len
            + "░" * n_len
            + "]"
        )


async def setup(bot: "ChibiBot"):
    """Set up the Status cog."""
    await bot.add_cog(StatusCog(bot))
