"""
Confirmation view for explain content creation.

Provides Yes/No buttons to confirm posting educational content.
"""

import logging
from typing import TYPE_CHECKING

import discord

if TYPE_CHECKING:
    from ...services.explain_service import ExplainService

logger = logging.getLogger(__name__)


class ExplainConfirmView(discord.ui.View):
    """View with Yes/No buttons for confirming content posting."""

    def __init__(
        self,
        explain_service: "ExplainService",
        thread: discord.Thread,
        timeout: float = 600,
    ):
        """
        Initialize the confirm view.

        Args:
            explain_service: ExplainService instance
            thread: Discord thread where conversation happened
            timeout: View timeout in seconds (default 10 minutes)
        """
        super().__init__(timeout=timeout)
        self.explain_service = explain_service
        self.thread = thread

    @discord.ui.button(
        label="Yes, Post It!",
        style=discord.ButtonStyle.success,
        emoji="✅",
    )
    async def confirm_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """Handle Yes button click - generate and post content."""
        # Defer the interaction immediately
        await interaction.response.defer()

        # Get the session
        session = self.explain_service.get_active_session(self.thread.id)
        if not session:
            await interaction.followup.send(
                "❌ Session not found. Please start a new `/explain` command.",
                ephemeral=True,
            )
            return

        try:
            # Disable buttons
            for child in self.children:
                child.disabled = True
            await interaction.message.edit(view=self)

            # Show progress
            progress_embed = discord.Embed(
                title="🔄 Generating Content...",
                description=(
                    "Creating educational content based on our conversation.\n"
                    "This may take a moment..."
                ),
                color=discord.Color.blue(),
            )
            await interaction.followup.send(embed=progress_embed)

            # Generate content
            content = await self.explain_service.generate_educational_content(
                thread=self.thread,
                session=session,
            )

            # Post to output channel
            output_thread = await self.explain_service.post_to_output_channel(
                bot=interaction.client,
                session=session,
                content=content,
            )

            if output_thread:
                # Success
                success_embed = discord.Embed(
                    title="✅ Content Posted Successfully!",
                    description=(
                        f"Educational content about **{session.topic}** has been posted.\n\n"
                        f"🔗 [View in AI Tutor Channel]({output_thread.jump_url})"
                    ),
                    color=discord.Color.green(),
                )
                await interaction.followup.send(embed=success_embed)

                # Archive this admin thread
                await self.explain_service.archive_admin_thread(self.thread)

                # Clean up session
                self.explain_service.remove_session(self.thread.id)

                logger.info(
                    f"Successfully posted content for session {self.thread.id}"
                )
            else:
                # Failed to post
                error_embed = discord.Embed(
                    title="❌ Failed to Post Content",
                    description=(
                        "There was an error posting to the output channel. "
                        "Please check the configuration and try again."
                    ),
                    color=discord.Color.red(),
                )
                await interaction.followup.send(embed=error_embed)

        except Exception as e:
            logger.error(f"Error in explain confirm: {e}", exc_info=True)
            error_embed = discord.Embed(
                title="❌ Error",
                description=f"An error occurred while generating or posting content: {str(e)}",
                color=discord.Color.red(),
            )
            await interaction.followup.send(embed=error_embed)

    @discord.ui.button(
        label="No, Continue Editing",
        style=discord.ButtonStyle.secondary,
        emoji="✏️",
    )
    async def cancel_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """Handle No button click - continue conversation."""
        await interaction.response.defer()

        # Disable buttons
        for child in self.children:
            child.disabled = True
        await interaction.message.edit(view=self)

        # Send continuation message
        embed = discord.Embed(
            title="📝 Continuing Conversation",
            description=(
                "No problem! Feel free to provide more details, ask questions, "
                "or make any changes. When you're ready to post, just let me know!"
            ),
            color=discord.Color.blue(),
        )
        await interaction.followup.send(embed=embed)

        logger.info(f"User chose to continue editing in thread {self.thread.id}")

    async def on_timeout(self):
        """Handle view timeout."""
        try:
            # Disable all buttons
            for child in self.children:
                child.disabled = True
            # Note: Can't edit message here without storing message reference
            logger.info(f"Explain confirm view timed out for thread {self.thread.id}")
        except Exception as e:
            logger.error(f"Error in timeout handler: {e}")
