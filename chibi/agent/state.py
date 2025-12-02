"""State schemas for main agent and sub-agents."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional, TypedDict

from langgraph.graph import MessagesState


@dataclass
class ToolResult:
    """Result returned by a sub-agent tool.

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


class MainAgentState(TypedDict, total=False):
    """State for the main orchestrating agent.

    This state is passed through the LangGraph nodes and maintains
    the full conversation context with the user.
    """

    # Message content
    messages: List[Dict[str, str]]

    # User/Channel context
    user_id: str
    user_name: str
    channel_id: str
    guild_id: Optional[str]

    # Discord interaction (for responding)
    discord_message: Any  # discord.Message object

    # Intent routing
    detected_intent: Optional[str]  # "quiz", "llm_quiz", "status", "assistant"
    intent_confidence: float
    extracted_params: Dict[str, Any]

    # Tool execution
    selected_tool: Optional[str]
    tool_result: Optional[ToolResult]

    # Response
    response_type: Literal["embed", "text", "modal"]
    response_content: Optional[Any]

    # Conversation history (main agent keeps this)
    conversation_history: List[Dict[str, str]]


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
