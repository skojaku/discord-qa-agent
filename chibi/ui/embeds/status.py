"""Status embed builder for learning progress displays."""

import discord

from ..formatters import create_progress_bar


class StatusEmbedBuilder:
    """Builder for status command embeds."""

    @staticmethod
    def create_base_embed(
        title: str, color: discord.Color = discord.Color.blue()
    ) -> discord.Embed:
        """Create a base embed with common styling.

        Args:
            title: Embed title
            color: Embed color (default: blue)

        Returns:
            Discord Embed
        """
        return discord.Embed(title=title, color=color)

    @staticmethod
    def add_progress_field(
        embed: discord.Embed,
        mastered: int,
        proficient: int,
        total_concepts: int,
    ) -> None:
        """Add overall progress field to embed.

        Args:
            embed: The embed to modify
            mastered: Number of mastered concepts
            proficient: Number of proficient concepts
            total_concepts: Total number of concepts
        """
        progress_pct = (
            (mastered + proficient) / total_concepts * 100
            if total_concepts > 0
            else 0
        )

        embed.add_field(
            name="Overall Progress",
            value=f"**{progress_pct:.1f}%** complete\n"
            f"({mastered + proficient}/{total_concepts} concepts)",
            inline=True,
        )

    @staticmethod
    def add_quiz_stats_field(
        embed: discord.Embed,
        total_quizzes: int,
        correct_quizzes: int,
    ) -> None:
        """Add quiz performance field to embed.

        Args:
            embed: The embed to modify
            total_quizzes: Total quiz attempts
            correct_quizzes: Number of correct attempts
        """
        accuracy = correct_quizzes / total_quizzes * 100 if total_quizzes > 0 else 0

        embed.add_field(
            name="Quiz Performance",
            value=f"**{total_quizzes}** quizzes taken\n"
            f"**{accuracy:.1f}%** accuracy",
            inline=True,
        )

    @staticmethod
    def add_mastery_breakdown_field(
        embed: discord.Embed,
        mastered: int,
        proficient: int,
        learning: int,
        novice: int,
    ) -> None:
        """Add mastery breakdown field with progress bar.

        Args:
            embed: The embed to modify
            mastered: Count of mastered concepts
            proficient: Count of proficient concepts
            learning: Count of learning concepts
            novice: Count of novice concepts
        """
        bar = create_progress_bar(mastered, proficient, learning, novice)

        embed.add_field(
            name="Mastery Levels",
            value=f"```\n{bar}\n```\n"
            f"🏆 Mastered: {mastered}\n"
            f"⭐ Proficient: {proficient}\n"
            f"📖 Learning: {learning}\n"
            f"🌱 Novice: {novice}",
            inline=False,
        )
