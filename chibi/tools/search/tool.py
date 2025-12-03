"""Search course content tool implementation."""

import logging
from typing import TYPE_CHECKING

from ...agent.state import SubAgentState, ToolResult
from ..base import BaseTool, ToolConfig

if TYPE_CHECKING:
    from ...bot import ChibiBot

logger = logging.getLogger(__name__)


class SearchTool(BaseTool):
    """Tool for searching course content using RAG.

    This tool searches course materials and returns relevant context
    for answering student questions about course concepts.
    """

    async def execute(self, state: SubAgentState) -> ToolResult:
        """Execute the search tool.

        Args:
            state: Sub-agent state with search query

        Returns:
            ToolResult with search results
        """
        try:
            # Get search query from task description or parameters
            query = state.task_description
            if not query and state.parameters:
                query = state.parameters.get("query", "")

            if not query:
                return ToolResult(
                    success=False,
                    result=None,
                    summary="No search query provided",
                    error="Search query is required",
                )

            # Get optional module filter
            module_id = state.parameters.get("module") if state.parameters else None

            # Use SearchAgentService for RAG
            if not self.bot.search_agent:
                return ToolResult(
                    success=False,
                    result=None,
                    summary="Search service not available",
                    error="Search agent not initialized",
                )

            # Get channel_id from discord_message if available
            channel_id = ""
            if state.discord_message:
                channel_id = str(state.discord_message.channel.id)

            # Perform search
            search_result = await self.bot.search_agent.search_for_assistant(
                query=query,
                user_id=state.user_id,
                channel_id=channel_id,
                module_id=module_id,
            )

            if not search_result.has_relevant_content:
                return ToolResult(
                    success=True,
                    result={"query": query, "found": False},
                    summary=f"No relevant content found for: {query}",
                    metadata={"chunk_ids": []},
                )

            # Use synthesized answer if available, otherwise use raw context
            answer = search_result.answer or search_result.raw_context

            return ToolResult(
                success=True,
                result={
                    "query": query,
                    "found": True,
                    "answer": answer,
                    "sources": len(search_result.sources),
                },
                summary=answer[:500] + "..." if len(answer) > 500 else answer,
                metadata={
                    "chunk_ids": search_result.chunk_ids,
                    "has_answer": bool(search_result.answer),
                },
            )

        except Exception as e:
            logger.error(f"Error in SearchTool: {e}", exc_info=True)
            return ToolResult(
                success=False,
                result=None,
                summary="Error searching course content",
                error=str(e),
            )


async def create_tool(bot: "ChibiBot", config: ToolConfig) -> SearchTool:
    """Create a SearchTool instance.

    Args:
        bot: ChibiBot instance
        config: Tool configuration

    Returns:
        Configured SearchTool instance
    """
    return SearchTool(bot, config)
