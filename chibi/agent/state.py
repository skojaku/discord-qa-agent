"""State schemas for main agent and sub-agents."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional, TypedDict


@dataclass
class ToolResult:
    """Result returned by a tool.

    Attributes:
        success: Whether the tool execution was successful
        result: Tool-specific result data
        summary: Human-readable summary for main agent context
        metadata: Structured metadata (e.g., quiz score, mastery change)
        error: Error message if execution failed
    """

    success: bool
    result: Any
    summary: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


class AgentState(TypedDict, total=False):
    """State for the main ReAct agent.

    This state is passed through the LangGraph nodes and maintains
    the conversation context and ReAct loop state.
    """

    # User/Channel context
    user_id: str
    user_name: str
    channel_id: str
    guild_id: Optional[str]

    # Discord interaction (for responding)
    discord_message: Any  # discord.Message object

    # User's original message
    user_message: str

    # ReAct loop state
    iteration: int
    max_iterations: int

    # Tool execution
    pending_tool_call: Optional[Dict[str, Any]]  # {name, query, params}
    tool_results: List[ToolResult]
    observations: List[str]  # Tool observations for context

    # Final response
    final_response: Optional[str]
    response_sent: bool


@dataclass
class SubAgentState:
    """Minimal state passed to sub-agents.

    This state is discarded after task completion to prevent
    the main agent's context from overflowing.

    Attributes:
        user_id: Discord user ID
        user_name: Discord username
        task_description: What the sub-agent needs to do
        parameters: Tool-specific parameters extracted from user message
        context_summary: Brief context from main agent (not full history)
        discord_message: The Discord message object for interactions
    """

    user_id: str
    user_name: str
    task_description: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    context_summary: str = ""
    discord_message: Any = None  # discord.Message or discord.Interaction
