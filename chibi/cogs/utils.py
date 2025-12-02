"""Common utilities for Discord cogs."""

import functools
import logging
from typing import Callable, List, TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from ..constants import (
    DISCORD_AUTOCOMPLETE_LIMIT,
    DISCORD_CHUNK_SIZE,
    DISCORD_MESSAGE_LIMIT,
    ERROR_GENERIC,
)

if TYPE_CHECKING:
    from ..database.models import User
    from ..database.repositories import UserRepository
    from ..content.course import Course

logger = logging.getLogger(__name__)


def defer_interaction(thinking: bool = True):
    """Decorator to handle interaction deferral with error handling.

    This decorator wraps Discord slash command handlers to:
    1. Defer the interaction response to prevent timeout
    2. Handle NotFound errors (expired interactions)
    3. Handle other deferral errors gracefully

    Args:
        thinking: Whether to show "thinking" indicator (default: True)

    Usage:
        @app_commands.command(name="example")
        @defer_interaction(thinking=True)
        async def example(self, interaction: discord.Interaction):
            # Interaction is already deferred at this point
            await interaction.followup.send("Response")
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(self, interaction: discord.Interaction, *args, **kwargs):
            try:
                await interaction.response.defer(thinking=thinking)
            except discord.NotFound:
                logger.warning("Interaction expired before defer (network latency)")
                return
            except Exception as e:
                logger.error(f"Failed to defer interaction: {e}")
                return

            return await func(self, interaction, *args, **kwargs)
        return wrapper
    return decorator


async def get_or_create_user_from_interaction(
    user_repo: "UserRepository",
    interaction: discord.Interaction,
) -> "User":
    """Get or create a user from a Discord interaction.

    Args:
        user_repo: The user repository
        interaction: The Discord interaction

    Returns:
        The User model instance
    """
    return await user_repo.get_or_create(
        discord_id=str(interaction.user.id),
        username=interaction.user.display_name,
    )


async def send_chunked_response(
    interaction: discord.Interaction,
    content: str,
) -> None:
    """Send a response, splitting into chunks if too long for Discord.

    Args:
        interaction: The Discord interaction (must be deferred)
        content: The content to send
    """
    if len(content) <= DISCORD_MESSAGE_LIMIT:
        await interaction.followup.send(content)
        return

    chunks = [content[i:i + DISCORD_CHUNK_SIZE] for i in range(0, len(content), DISCORD_CHUNK_SIZE)]
    for chunk in chunks:
        await interaction.followup.send(chunk)


async def module_autocomplete_choices(
    course: "Course",
    current: str,
) -> List[app_commands.Choice[str]]:
    """Generate autocomplete choices for module selection.

    Args:
        course: The course instance containing modules
        current: The current user input for filtering

    Returns:
        List of Discord Choice objects for autocomplete
    """
    if not course:
        return []

    choices = []
    for module in course.modules:
        display_name = f"{module.id}: {module.name}"
        if current.lower() in display_name.lower():
            choices.append(
                app_commands.Choice(name=display_name[:100], value=module.id)
            )

    return choices[:DISCORD_AUTOCOMPLETE_LIMIT]


def handle_slash_command_errors(
    error_message: str = ERROR_GENERIC,
    context: str = "",
):
    """Decorator for standardized error handling in slash commands.

    Wraps slash command handlers to catch exceptions and send
    user-friendly error messages.

    Args:
        error_message: Error message to display to the user
        context: Context string for logging

    Usage:
        @app_commands.command(name="example")
        @defer_interaction(thinking=True)
        @handle_slash_command_errors(error_message="Failed!", context="/example")
        async def example(self, interaction: discord.Interaction):
            # Command implementation
            pass
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(self, interaction: discord.Interaction, *args, **kwargs):
            try:
                return await func(self, interaction, *args, **kwargs)
            except discord.NotFound:
                logger.warning(f"Interaction expired in {context or func.__name__}")
            except Exception as e:
                logger.error(
                    f"Error in {context or func.__name__}: {e}",
                    exc_info=True
                )
                try:
                    await interaction.followup.send(error_message)
                except discord.NotFound:
                    pass
        return wrapper
    return decorator


def handle_prefix_command_errors(
    error_message: str = ERROR_GENERIC,
    context: str = "",
):
    """Decorator for standardized error handling in prefix commands.

    Wraps prefix command handlers to catch exceptions and send
    user-friendly error messages.

    Args:
        error_message: Error message to display to the user
        context: Context string for logging

    Usage:
        @commands.command(name="example")
        @handle_prefix_command_errors(error_message="Failed!", context="!example")
        async def example(self, ctx: commands.Context):
            # Command implementation
            pass
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(self, ctx: commands.Context, *args, **kwargs):
            try:
                return await func(self, ctx, *args, **kwargs)
            except Exception as e:
                logger.error(
                    f"Error in {context or func.__name__}: {e}",
                    exc_info=True
                )
                await ctx.send(error_message)
        return wrapper
    return decorator
