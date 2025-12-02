"""Main LangGraph StateGraph definition."""

import logging
from typing import TYPE_CHECKING

from langgraph.graph import END, StateGraph

from .memory import ConversationMemory
from .nodes import classify_intent, dispatch_to_tool, format_response, parse_message, should_use_tool
from .nodes.dispatcher import set_dispatcher_dependencies
from .nodes.router import set_router_dependencies
from .state import MainAgentState

if TYPE_CHECKING:
    from ..llm.manager import LLMManager
    from ..tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


class AgentGraph:
    """Wrapper for the LangGraph agent workflow."""

    def __init__(
        self,
        llm_manager: "LLMManager",
        tool_registry: "ToolRegistry",
        max_conversation_history: int = 20,
    ):
        """Initialize the agent graph.

        Args:
            llm_manager: LLM manager for intent classification
            tool_registry: Registry of available tools
            max_conversation_history: Maximum messages to retain per conversation
        """
        self.llm_manager = llm_manager
        self.tool_registry = tool_registry
        self.conversation_memory = ConversationMemory(max_history=max_conversation_history)

        # Set up dependencies for nodes
        set_router_dependencies(llm_manager, tool_registry)
        set_dispatcher_dependencies(tool_registry, self.conversation_memory)

        # Build and compile the graph
        self.graph = self._build_graph()
        logger.info("Agent graph initialized")

    def _build_graph(self) -> StateGraph:
        """Build the LangGraph StateGraph.

        Returns:
            Compiled StateGraph
        """
        # Create the graph with our state type
        graph = StateGraph(MainAgentState)

        # Add nodes
        graph.add_node("entry", parse_message)
        graph.add_node("router", classify_intent)
        graph.add_node("dispatcher", dispatch_to_tool)
        graph.add_node("response", format_response)

        # Set entry point
        graph.set_entry_point("entry")

        # Add edges
        graph.add_edge("entry", "router")

        # Conditional routing from router
        graph.add_conditional_edges(
            "router",
            should_use_tool,
            {
                "use_tool": "dispatcher",
                "direct_response": "response",
            },
        )

        graph.add_edge("dispatcher", "response")
        graph.add_edge("response", END)

        return graph.compile()

    async def invoke(self, discord_message, cleaned_content: str = None) -> dict:
        """Invoke the agent graph with a Discord message.

        Args:
            discord_message: The Discord message that triggered the agent
            cleaned_content: Optional pre-cleaned message content (mentions removed)

        Returns:
            Final state after graph execution
        """
        initial_state = {
            "discord_message": discord_message,
            "cleaned_content": cleaned_content,
            "messages": [],
            "detected_intent": None,
            "intent_confidence": 0.0,
            "extracted_params": {},
            "selected_tool": None,
            "tool_result": None,
            "response_type": "text",
            "response_content": None,
            "conversation_history": [],
        }

        try:
            # Run the graph
            final_state = await self.graph.ainvoke(initial_state)
            return final_state
        except Exception as e:
            logger.error(f"Error invoking agent graph: {e}", exc_info=True)
            # Try to send error response
            try:
                await discord_message.reply(
                    "I encountered an error processing your request. Please try again.",
                    mention_author=False,
                )
            except Exception:
                pass
            return initial_state


def create_agent_graph(
    llm_manager: "LLMManager",
    tool_registry: "ToolRegistry",
    max_conversation_history: int = 20,
) -> AgentGraph:
    """Create and configure an AgentGraph instance.

    Args:
        llm_manager: LLM manager for intent classification
        tool_registry: Registry of available tools
        max_conversation_history: Maximum messages to retain per conversation

    Returns:
        Configured AgentGraph instance
    """
    return AgentGraph(
        llm_manager=llm_manager,
        tool_registry=tool_registry,
        max_conversation_history=max_conversation_history,
    )
