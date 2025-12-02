"""Entry node for parsing Discord messages."""

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..state import MainAgentState

logger = logging.getLogger(__name__)


async def parse_message(state: "MainAgentState") -> dict[str, Any]:
    """Parse incoming Discord message and populate initial state.

    This is the entry point for the agent graph. It extracts
    user information and message content from the Discord message.

    Args:
        state: Current agent state with discord_message

    Returns:
        Updated state fields
    """
    discord_message = state.get("discord_message")

    if discord_message is None:
        logger.warning("No Discord message in state")
        return {
            "detected_intent": None,
            "intent_confidence": 0.0,
            "extracted_params": {},
        }

    # Extract user and channel info
    user_id = str(discord_message.author.id)
    user_name = discord_message.author.display_name
    channel_id = str(discord_message.channel.id)
    guild_id = str(discord_message.guild.id) if discord_message.guild else None

    # Get message content
    content = discord_message.content.strip()

    # Remove bot mention if present
    if discord_message.mentions:
        for mention in discord_message.mentions:
            content = content.replace(f"<@{mention.id}>", "").strip()
            content = content.replace(f"<@!{mention.id}>", "").strip()

    logger.debug(f"Parsed message from {user_name}: {content[:100]}...")

    return {
        "user_id": user_id,
        "user_name": user_name,
        "channel_id": channel_id,
        "guild_id": guild_id,
        "messages": [{"role": "user", "content": content}],
    }
