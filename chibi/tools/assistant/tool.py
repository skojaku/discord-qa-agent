"""Assistant tool implementation - default helpful assistant with RAG."""

import logging
import re
from typing import TYPE_CHECKING

import discord

from ...agent.state import SubAgentState, ToolResult
from ...agent.context_manager import ContextType
from ..base import BaseTool, ToolConfig

if TYPE_CHECKING:
    from ...bot import ChibiBot

logger = logging.getLogger(__name__)

# Patterns that indicate conversational/non-course queries (skip RAG)
SKIP_RAG_PATTERNS = [
    r"^(hi|hello|hey|yo|sup)\b",  # Greetings
    r"^(thanks|thank you|thx)\b",  # Thanks
    r"^(bye|goodbye|see you)\b",  # Farewells
    r"(your name|who are you|what are you)\b",  # Identity questions
    r"^(how are you|how do you do)\b",  # Small talk
    r"^(good morning|good afternoon|good evening|good night)\b",  # Time greetings
]

# Patterns that indicate course-related queries (use RAG)
USE_RAG_PATTERNS = [
    r"\b(explain|describe|what is|what are|how does|how do|why)\b",
    r"\b(module|concept|topic|lesson|chapter)\b",
    r"\b(learn|understand|study|teach)\b",
    r"\b(example|definition|meaning)\b",
    r"\b(network|graph|node|edge|algorithm)\b",  # Common course terms
]


ASSISTANT_SYSTEM_PROMPT = """You are Chibi, a friendly and helpful AI tutor assistant.
Your role is to help students learn and understand course material.

Guidelines:
- Be encouraging and supportive
- Explain concepts clearly and concisely
- Use examples when helpful
- If you're not sure about something, say so
- Keep responses focused and not too long (under 500 words)
- Base your answers on the provided context when available
- If the context doesn't contain relevant information, provide general guidance and suggest checking the course materials
- Always cite which module the information comes from when using context

Available course modules:
{module_list}

{context}
"""


class AssistantTool(BaseTool):
    """Default assistant tool for general questions.

    This tool handles general questions about course content,
    using RAG (Retrieval-Augmented Generation) to provide
    relevant context from indexed course materials.
    """

    async def execute(self, state: SubAgentState) -> ToolResult:
        """Execute the assistant tool.

        Args:
            state: Sub-agent state with task description and parameters

        Returns:
            ToolResult with assistant response
        """
        try:
            discord_message = state.discord_message
            if discord_message is None:
                return ToolResult(
                    success=False,
                    result=None,
                    summary="No Discord context available",
                    error="Discord message not provided",
                )

            user_question = state.task_description

            # Only use RAG for course-related questions
            if self._should_use_rag(user_question):
                context = await self._build_context_with_rag(user_question)
                logger.debug(f"Using RAG for query: {user_question[:50]}...")
            else:
                context = ""
                logger.debug(f"Skipping RAG for conversational query: {user_question[:50]}...")

            # Build module list
            module_list = "\n".join(
                f"- {m.name}: {m.description or 'No description'}"
                for m in self.bot.course.modules
            )

            # Build system prompt
            system_prompt = ASSISTANT_SYSTEM_PROMPT.format(
                module_list=module_list,
                context=context,
            )

            # Add conversation context if available
            prompt = user_question
            if state.context_summary:
                prompt = f"Recent conversation:\n{state.context_summary}\n\nCurrent question: {user_question}"

            # Generate response using LLM
            response = await self.bot.llm_manager.generate(
                prompt=prompt,
                system_prompt=system_prompt,
                max_tokens=1024,
                temperature=0.7,
            )

            if not response or not response.content:
                return ToolResult(
                    success=False,
                    result=None,
                    summary="Failed to generate response",
                    error="LLM error",
                )

            answer = response.content.strip()

            # Split long responses
            if len(answer) > 2000:
                chunks = [answer[i : i + 2000] for i in range(0, len(answer), 2000)]
                for i, chunk in enumerate(chunks):
                    if i == 0:
                        await discord_message.reply(chunk, mention_author=False)
                    else:
                        await discord_message.channel.send(chunk)
            else:
                await discord_message.reply(answer, mention_author=False)

            logger.info(f"Assistant responded to {state.user_name}")

            return ToolResult(
                success=True,
                result=answer,
                summary=f"Answered question about: {user_question[:50]}...",
                metadata={
                    "response_sent": True,
                    "used_rag": bool(context),
                },
            )

        except Exception as e:
            logger.error(f"Error in AssistantTool: {e}", exc_info=True)
            return ToolResult(
                success=False,
                result=None,
                summary="Error generating response",
                error=str(e),
            )

    def _should_use_rag(self, query: str) -> bool:
        """Determine if RAG should be used for this query.

        Skips RAG for simple conversational queries (greetings, thanks, etc.)
        and uses RAG for course-related questions.

        Args:
            query: The user's question

        Returns:
            True if RAG should be used, False otherwise
        """
        query_lower = query.lower().strip()

        # Very short queries are usually conversational
        if len(query_lower.split()) <= 3:
            # Check if it matches skip patterns
            for pattern in SKIP_RAG_PATTERNS:
                if re.search(pattern, query_lower, re.IGNORECASE):
                    logger.debug(f"Skipping RAG: matches skip pattern '{pattern}'")
                    return False

        # Check if query matches explicit skip patterns
        for pattern in SKIP_RAG_PATTERNS:
            if re.search(pattern, query_lower, re.IGNORECASE):
                # But if it also has course keywords, still use RAG
                for rag_pattern in USE_RAG_PATTERNS:
                    if re.search(rag_pattern, query_lower, re.IGNORECASE):
                        return True
                logger.debug(f"Skipping RAG: matches skip pattern '{pattern}'")
                return False

        # Check if query has course-related keywords
        for pattern in USE_RAG_PATTERNS:
            if re.search(pattern, query_lower, re.IGNORECASE):
                return True

        # For medium-length queries (4-10 words), use RAG by default
        # For very short queries without course keywords, skip RAG
        word_count = len(query_lower.split())
        if word_count <= 5:
            logger.debug(f"Skipping RAG: short query without course keywords")
            return False

        # Default: use RAG for longer queries
        return True

    async def _build_context_with_rag(self, query: str) -> str:
        """Build context using the context manager.

        Uses the centralized context manager for semantic search
        to find relevant content from indexed course materials.

        Args:
            query: The user's question

        Returns:
            Context string with relevant content
        """
        # Use context manager if available
        if self.bot.context_manager is None:
            logger.warning("Context manager not available, falling back to basic context")
            return self._build_fallback_context()

        try:
            # Get context from context manager
            context_result = await self.bot.context_manager.get_context_for_assistant(
                question=query,
            )

            if not context_result.has_relevant_content:
                logger.debug(f"No relevant context for query: {query[:50]}")
                return self._build_fallback_context()

            # Format context with source attribution
            context = f"Relevant course content (retrieved based on your question):\n\n{context_result.context}"

            # Add source attribution
            if context_result.source_names:
                context += f"\n\n(Sources: {', '.join(context_result.source_names)})"

            logger.info(
                f"Context manager retrieved {context_result.total_chunks} chunks "
                f"from {len(context_result.source_names)} sources"
            )

            return context

        except Exception as e:
            logger.error(f"Context retrieval error: {e}", exc_info=True)
            return self._build_fallback_context()

    def _build_fallback_context(self) -> str:
        """Build basic context when RAG is not available.

        Returns:
            Basic course overview context
        """
        context_parts = []

        # Add course overview
        context_parts.append(
            f"Course: {self.bot.course.name}\n"
            f"Description: {self.bot.course.description or 'No description'}"
        )

        # Add module list with descriptions
        for module in self.bot.course.modules[:5]:  # Limit to first 5
            module_info = f"\nModule: {module.name}"
            if module.description:
                module_info += f"\n{module.description}"
            context_parts.append(module_info)

        # Add concept list
        all_concepts = self.bot.course.get_all_concepts()
        if all_concepts:
            concept_names = [c.name for c in list(all_concepts.values())[:15]]
            context_parts.append(
                f"\nKey concepts include: {', '.join(concept_names)}"
            )

        return "Course overview:\n" + "\n".join(context_parts)


async def create_tool(bot: "ChibiBot", config: ToolConfig) -> AssistantTool:
    """Create an AssistantTool instance.

    Args:
        bot: ChibiBot instance
        config: Tool configuration

    Returns:
        Configured AssistantTool instance
    """
    return AssistantTool(bot, config)
