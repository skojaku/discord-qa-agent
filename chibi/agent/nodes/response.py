"""Response node for formatting tool results."""

import logging
from typing import TYPE_CHECKING, Any

import discord

if TYPE_CHECKING:
    from ..state import MainAgentState

logger = logging.getLogger(__name__)


async def format_response(state: "MainAgentState") -> dict[str, Any]:
    """Format tool result for Discord output.

    Takes the ToolResult from the dispatcher and formats it
    appropriately for sending back to Discord.

    Args:
        state: Current agent state with tool result

    Returns:
        Updated state fields with response content
    """
    tool_result = state.get("tool_result")
    discord_message = state.get("discord_message")

    if tool_result is None:
        return {
            "response_type": "text",
            "response_content": "I'm not sure how to help with that. Could you rephrase your question?",
        }

    # Check if the tool already sent a response (e.g., modal interactions)
    if tool_result.metadata.get("response_sent", False):
        logger.debug("Tool already sent response, skipping format_response")
        return {
            "response_type": "none",
            "response_content": None,
        }

    # Handle errors
    if not tool_result.success:
        error_msg = tool_result.error or "An error occurred"
        logger.warning(f"Tool execution failed: {error_msg}")

        if discord_message:
            try:
                await discord_message.reply(
                    f"Sorry, something went wrong: {error_msg}",
                    mention_author=False,
                )
            except Exception as e:
                logger.error(f"Failed to send error response: {e}")

        return {
            "response_type": "text",
            "response_content": f"Error: {error_msg}",
        }

    # Check response type from metadata
    response_type = tool_result.metadata.get("response_type", "text")
    result = tool_result.result

    if response_type == "embed" and isinstance(result, discord.Embed):
        # Tool returned a Discord embed
        if discord_message:
            try:
                await discord_message.reply(embed=result, mention_author=False)
            except Exception as e:
                logger.error(f"Failed to send embed response: {e}")

        return {
            "response_type": "embed",
            "response_content": result,
        }

    elif response_type == "modal":
        # Modal was already shown by the tool
        return {
            "response_type": "modal",
            "response_content": None,
        }

    else:
        # Default: text response
        text_content = str(result) if result else tool_result.summary

        if discord_message:
            try:
                # Split long messages
                if len(text_content) > 2000:
                    chunks = [text_content[i : i + 2000] for i in range(0, len(text_content), 2000)]
                    for i, chunk in enumerate(chunks):
                        if i == 0:
                            await discord_message.reply(chunk, mention_author=False)
                        else:
                            await discord_message.channel.send(chunk)
                else:
                    await discord_message.reply(text_content, mention_author=False)
            except Exception as e:
                logger.error(f"Failed to send text response: {e}")

        return {
            "response_type": "text",
            "response_content": text_content,
        }
