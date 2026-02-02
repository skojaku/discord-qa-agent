"""
Explain command cog for creating educational content through conversation.

Provides /explain slash command for admins to create educational content
through a conversational process, then post to AI tutor channel.
"""

import logging
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from .utils import defer_interaction, handle_slash_command_errors

if TYPE_CHECKING:
    from ..bot import ChibiBot

logger = logging.getLogger(__name__)

ERROR_EXPLAIN = "Oops! Something went wrong starting the explanation session. Please try again!"
ERROR_NO_CHANNEL = (
    "The admin channel for `/explain` has not been configured. "
    "Please set EXPLAIN_ADMIN_CHANNEL_ID in your environment variables."
)


class ExplainCog(commands.Cog):
    """Cog for the /explain command."""

    def __init__(self, bot: "ChibiBot"):
        """
        Initialize the explain cog.

        Args:
            bot: The bot instance
        """
        self.bot = bot

    @app_commands.command(
        name="explain",
        description="Create educational content through conversation with the AI tutor",
    )
    @app_commands.describe(
        topic="The main concept or topic to explain (e.g., 'network centrality')",
        context="Additional context: audience, focus, or specific aspects to cover",
    )
    @app_commands.checks.has_permissions(administrator=True)
    @defer_interaction(thinking=True)
    @handle_slash_command_errors(error_message=ERROR_EXPLAIN, context="/explain")
    async def explain(
        self,
        interaction: discord.Interaction,
        topic: str,
        context: str = "",
    ):
        """
        Start an explanation content creation session.

        Args:
            interaction: Discord interaction
            topic: The topic to explain
            context: Additional context about the explanation
        """
        # Validate that explain service is available
        if not hasattr(self.bot, "explain_service") or not self.bot.explain_service:
            await interaction.followup.send(
                "❌ The explain feature is not properly configured. "
                "Please contact an administrator.",
                ephemeral=True,
            )
            return

        explain_service = self.bot.explain_service

        # Validate admin channel is configured
        if not explain_service.admin_channel_id:
            await interaction.followup.send(ERROR_NO_CHANNEL, ephemeral=True)
            return

        # Get the admin channel
        admin_channel = self.bot.get_channel(explain_service.admin_channel_id)
        if not admin_channel:
            await interaction.followup.send(
                f"❌ Admin channel (ID: {explain_service.admin_channel_id}) not found. "
                "Please check the configuration.",
                ephemeral=True,
            )
            return

        # Verify it's a text channel
        if not isinstance(admin_channel, discord.TextChannel):
            await interaction.followup.send(
                "❌ The configured admin channel is not a text channel.",
                ephemeral=True,
            )
            return

        try:
            # Create thread in admin channel
            thread_name = f"✨ {topic}"
            if len(thread_name) > 100:  # Discord thread name limit
                thread_name = thread_name[:97] + "..."

            thread = await admin_channel.create_thread(
                name=thread_name,
                type=discord.ChannelType.private_thread,  # Private thread
                auto_archive_duration=1440,  # 24 hours
            )

            # Generate initial bot message
            initial_message = await explain_service.generate_initial_message(
                topic=topic, context=context or "No specific context provided"
            )

            # Create session
            session = explain_service.create_session(
                thread_id=thread.id,
                topic=topic,
                context=context,
                admin_user_id=interaction.user.id,
                admin_channel_id=admin_channel.id,
            )

            # Send initial message in thread
            intro_embed = discord.Embed(
                title=f"📚 Creating Content: {topic}",
                description=(
                    f"**Topic:** {topic}\n"
                    f"**Context:** {context or 'General explanation'}\n\n"
                    "Let's work together to create great educational content!"
                ),
                color=discord.Color.blue(),
            )
            await thread.send(embed=intro_embed)
            await thread.send(initial_message)

            # Confirm to user
            success_embed = discord.Embed(
                title="✅ Explanation Session Started!",
                description=(
                    f"I've created a private thread to work on this content.\n\n"
                    f"🔗 [Go to Thread]({thread.jump_url})\n\n"
                    "I'll ask you some questions to understand what you need. "
                    "When we're done, I'll generate and post the content to the AI Tutor channel."
                ),
                color=discord.Color.green(),
            )
            await interaction.followup.send(embed=success_embed, ephemeral=True)

            logger.info(
                f"Started explain session: thread={thread.id}, "
                f"topic='{topic}', user={interaction.user.id}"
            )

        except discord.Forbidden:
            await interaction.followup.send(
                "❌ I don't have permission to create threads in the admin channel. "
                "Please check my permissions.",
                ephemeral=True,
            )
        except Exception as e:
            logger.error(f"Error creating explain thread: {e}", exc_info=True)
            await interaction.followup.send(
                f"❌ An error occurred while creating the thread: {str(e)}",
                ephemeral=True,
            )

    @explain.error
    async def explain_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ):
        """Handle errors for the explain command."""
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                "❌ You need administrator permissions to use the `/explain` command.",
                ephemeral=True,
            )
        else:
            logger.error(f"Unhandled error in /explain: {error}", exc_info=True)
            # The handle_slash_command_errors decorator should catch most errors
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    ERROR_EXPLAIN,
                    ephemeral=True,
                )


async def setup(bot: "ChibiBot"):
    """
    Load the ExplainCog.

    Args:
        bot: The bot instance
    """
    await bot.add_cog(ExplainCog(bot))
    logger.info("ExplainCog loaded")
