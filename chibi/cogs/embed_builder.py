"""Embed builder utilities for Discord embeds."""

import discord

from ..constants import MASTERY_EMOJI, PROGRESS_BAR_LENGTH


class StatusEmbedBuilder:
    """Builder for status command embeds."""

    @staticmethod
    def create_base_embed(title: str, color: discord.Color = discord.Color.blue()) -> discord.Embed:
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
        bar = StatusEmbedBuilder.create_progress_bar(mastered, proficient, learning, novice)

        embed.add_field(
            name="Mastery Levels",
            value=f"```\n{bar}\n```\n"
            f"🏆 Mastered: {mastered}\n"
            f"⭐ Proficient: {proficient}\n"
            f"📖 Learning: {learning}\n"
            f"🌱 Novice: {novice}",
            inline=False,
        )

    @staticmethod
    def create_progress_bar(
        mastered: int,
        proficient: int,
        learning: int,
        novice: int,
    ) -> str:
        """Create a visual progress bar.

        Args:
            mastered: Count of mastered concepts
            proficient: Count of proficient concepts
            learning: Count of learning concepts
            novice: Count of novice concepts

        Returns:
            ASCII progress bar string
        """
        total = mastered + proficient + learning + novice
        if total == 0:
            return "[ No data yet ]"

        m_len = int(mastered / total * PROGRESS_BAR_LENGTH)
        p_len = int(proficient / total * PROGRESS_BAR_LENGTH)
        l_len = int(learning / total * PROGRESS_BAR_LENGTH)
        n_len = PROGRESS_BAR_LENGTH - m_len - p_len - l_len

        return (
            "["
            + "█" * m_len
            + "▓" * p_len
            + "▒" * l_len
            + "░" * n_len
            + "]"
        )

    @staticmethod
    def get_mastery_emoji(level: str) -> str:
        """Get emoji for mastery level.

        Args:
            level: Mastery level string

        Returns:
            Emoji string
        """
        return MASTERY_EMOJI.get(level, "⬜")


class QuizEmbedBuilder:
    """Builder for quiz-related embeds."""

    @staticmethod
    def create_question_embed(
        concept_name: str,
        question_text: str,
        module_name: str,
        selection_reason: str,
    ) -> discord.Embed:
        """Create quiz question embed.

        Args:
            concept_name: Name of the concept being tested
            question_text: The quiz question
            module_name: Name of the module
            selection_reason: Reason for concept selection

        Returns:
            Discord Embed for the quiz question
        """
        embed = discord.Embed(
            title=f"📝 Quiz: {concept_name}",
            description=question_text,
            color=discord.Color.blue(),
        )
        embed.set_footer(
            text=f"Module: {module_name} | {selection_reason}\n"
            f"Reply to this message with your answer!"
        )
        return embed

    @staticmethod
    def create_feedback_embed(
        is_pass: bool,
        is_partial: bool,
        quality_score: int,
        feedback: str,
        concept_name: str,
    ) -> discord.Embed:
        """Create quiz feedback embed.

        Args:
            is_pass: Whether the answer passed
            is_partial: Whether the answer was partial
            quality_score: Quality score (1-5)
            feedback: Feedback text
            concept_name: Name of the concept

        Returns:
            Discord Embed for the feedback
        """
        if is_pass:
            color = discord.Color.green()
            title = f"✅ PASS (Score: {quality_score}/5)"
        elif is_partial:
            color = discord.Color.gold()
            title = f"🔶 PARTIAL (Score: {quality_score}/5)"
        else:
            color = discord.Color.red()
            title = f"❌ FAIL (Score: {quality_score}/5)"

        embed = discord.Embed(
            title=title,
            description=feedback,
            color=color,
        )
        embed.set_footer(text=f"Concept: {concept_name}")

        return embed
