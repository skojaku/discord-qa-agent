"""Dispatcher node for tool invocation."""

import logging
from typing import TYPE_CHECKING, Any

from ..state import SubAgentState, ToolResult

if TYPE_CHECKING:
    from ...tools.registry import ToolRegistry
    from ..memory import ConversationMemory
    from ..state import MainAgentState

logger = logging.getLogger(__name__)

# Global references set during graph creation
_tool_registry: "ToolRegistry" = None
_conversation_memory: "ConversationMemory" = None


def set_dispatcher_dependencies(
    tool_registry: "ToolRegistry",
    conversation_memory: "ConversationMemory",
) -> None:
    """Set the dependencies for the dispatcher node.

    Called during graph creation to inject dependencies.

    Args:
        tool_registry: Registry of available tools
        conversation_memory: Conversation memory manager
    """
    global _tool_registry, _conversation_memory
    _tool_registry = tool_registry
    _conversation_memory = conversation_memory


async def dispatch_to_tool(state: "MainAgentState") -> dict[str, Any]:
    """Invoke the selected tool with minimal sub-agent state.

    Creates a SubAgentState with minimal context and invokes
    the appropriate tool. The sub-agent state is discarded after
    execution - only the ToolResult flows back to the main agent.

    Args:
        state: Current agent state with selected tool

    Returns:
        Updated state fields with tool result
    """
    if _tool_registry is None:
        logger.error("Tool registry not set")
        return {
            "tool_result": ToolResult(
                success=False,
                result=None,
                summary="Internal error: Tool registry not available",
                error="Tool registry not initialized",
            )
        }

    selected_tool = state.get("selected_tool", "assistant")
    tool = _tool_registry.get_tool(selected_tool)

    if tool is None:
        logger.warning(f"Tool not found: {selected_tool}, falling back to assistant")
        tool = _tool_registry.get_tool("assistant")

    if tool is None:
        return {
            "tool_result": ToolResult(
                success=False,
                result=None,
                summary="No tool available to handle this request",
                error="Tool not found",
            )
        }

    # Build minimal sub-agent state
    user_id = state.get("user_id", "")
    user_name = state.get("user_name", "")
    channel_id = state.get("channel_id", "")
    messages = state.get("messages", [])
    task_description = messages[-1].get("content", "") if messages else ""

    # Get brief context summary (not full history)
    context_summary = ""
    if _conversation_memory:
        context_summary = _conversation_memory.get_context_summary(
            user_id=user_id,
            channel_id=channel_id,
            max_messages=3,
        )

    sub_state = SubAgentState(
        user_id=user_id,
        user_name=user_name,
        task_description=task_description,
        parameters=state.get("extracted_params", {}),
        context_summary=context_summary,
        discord_message=state.get("discord_message"),
    )

    logger.info(f"Dispatching to tool: {tool.name}")

    try:
        # Execute tool - sub_state is discarded after this
        result = await tool.execute(sub_state)

        # Log the interaction to conversation memory
        if _conversation_memory and result.success:
            _conversation_memory.add_message(
                user_id=user_id,
                channel_id=channel_id,
                role="user",
                content=task_description,
            )
            _conversation_memory.add_message(
                user_id=user_id,
                channel_id=channel_id,
                role="assistant",
                content=result.summary,
                metadata={
                    "tool": tool.name,
                    "result_metadata": result.metadata,
                },
            )

        return {"tool_result": result}

    except Exception as e:
        logger.error(f"Error executing tool {tool.name}: {e}", exc_info=True)
        return {
            "tool_result": ToolResult(
                success=False,
                result=None,
                summary=f"Error executing {tool.name}",
                error=str(e),
            )
        }
