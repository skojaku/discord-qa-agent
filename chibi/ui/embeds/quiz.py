"""Quiz embed builder for quiz questions and feedback."""

import discord


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
