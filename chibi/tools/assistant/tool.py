"""Assistant tool implementation with ReAct framework for intelligent RAG usage."""

import logging
import re
from typing import TYPE_CHECKING, Optional, Tuple

import discord

from ...agent.state import SubAgentState, ToolResult
from ..base import BaseTool, ToolConfig

if TYPE_CHECKING:
    from ...bot import ChibiBot

logger = logging.getLogger(__name__)

# Maximum iterations for ReAct loop to prevent infinite loops
MAX_REACT_ITERATIONS = 3

REACT_SYSTEM_PROMPT = """You are Chibi, a friendly and helpful AI tutor assistant.
Your role is to help students learn and understand course material.

You have access to a tool to search course content when needed:

**Tool: search_course_content**
Use this to find relevant information from the course materials.
Call it by writing: <tool>search_course_content</tool><query>your search query</query>

WHEN TO USE THE TOOL:
- When the student asks about course concepts, topics, or modules
- When you need specific information from the course materials
- When explaining technical concepts that are covered in the course

WHEN NOT TO USE THE TOOL:
- For greetings (hi, hello, how are you)
- For questions about yourself (what's your name, who are you)
- For simple thanks or farewells
- For general conversation not related to course content

After gathering information (if needed), provide your final answer.
Mark your final response with: <answer>your response here</answer>

Available course modules:
{module_list}

Guidelines:
- Be encouraging and supportive
- Explain concepts clearly and concisely
- Use examples when helpful
- Keep responses focused (under 500 words)
- Cite which module information comes from when using search results
- If search returns no relevant results, provide general guidance
"""

REACT_USER_PROMPT = """Student question: {question}

{context}

Think step by step:
1. Do I need to search course content to answer this?
2. If yes, what should I search for?
3. Provide the answer.

Remember: Use <tool>search_course_content</tool><query>...</query> to search, then <answer>...</answer> for your final response."""


class AssistantTool(BaseTool):
    """Default assistant tool using ReAct framework.

    This tool uses a ReAct (Reasoning + Acting) approach where
    the LLM decides when to search course content for context.
    """

    async def execute(self, state: SubAgentState) -> ToolResult:
        """Execute the assistant tool with ReAct loop.

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

            # Build module list for context
            module_list = "\n".join(
                f"- {m.name}: {m.description or 'No description'}"
                for m in self.bot.course.modules
            )

            # Build system prompt
            system_prompt = REACT_SYSTEM_PROMPT.format(module_list=module_list)

            # Add conversation context if available
            context = ""
            if state.context_summary:
                context = f"Recent conversation:\n{state.context_summary}\n"

            # Build initial prompt
            prompt = REACT_USER_PROMPT.format(
                question=user_question,
                context=context,
            )

            # ReAct loop
            search_results = []
            answer = None
            used_rag = False

            for iteration in range(MAX_REACT_ITERATIONS):
                logger.debug(f"ReAct iteration {iteration + 1}")

                # Generate response
                response = await self.bot.llm_manager.generate(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    max_tokens=1024,
                    temperature=0.7,
                )

                if not response or not response.content:
                    logger.warning("Empty LLM response in ReAct loop")
                    break

                llm_output = response.content.strip()
                logger.debug(f"LLM output: {llm_output[:200]}...")

                # Check for tool call
                tool_call = self._parse_tool_call(llm_output)
                if tool_call:
                    tool_name, query = tool_call
                    logger.info(f"ReAct tool call: {tool_name}('{query}')")

                    if tool_name == "search_course_content":
                        # Execute search
                        search_result = await self._search_course_content(query)
                        search_results.append(search_result)
                        used_rag = True

                        # Add search result to prompt for next iteration
                        prompt = f"""{prompt}

Assistant's action: Searched for "{query}"

Search results:
{search_result}

Now provide your final answer using <answer>...</answer>"""
                        continue

                # Check for final answer
                answer = self._parse_answer(llm_output)
                if answer:
                    logger.debug("ReAct loop: Found final answer")
                    break

                # If no tool call and no answer tag, treat whole response as answer
                if not tool_call:
                    answer = llm_output
                    break

            # If no answer after loop, use last response
            if not answer:
                answer = llm_output if 'llm_output' in locals() else "I'm sorry, I couldn't generate a response."

            # Send response to Discord
            await self._send_response(discord_message, answer)

            logger.info(f"Assistant responded to {state.user_name} (used_rag={used_rag})")

            return ToolResult(
                success=True,
                result=answer,
                summary=f"Answered question about: {user_question[:50]}...",
                metadata={
                    "response_sent": True,
                    "used_rag": used_rag,
                    "search_count": len(search_results),
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

    def _parse_tool_call(self, text: str) -> Optional[Tuple[str, str]]:
        """Parse a tool call from LLM output.

        Args:
            text: LLM output text

        Returns:
            Tuple of (tool_name, query) or None if no tool call found
        """
        # Pattern: <tool>tool_name</tool><query>query text</query>
        pattern = r"<tool>(\w+)</tool>\s*<query>(.*?)</query>"
        match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)

        if match:
            tool_name = match.group(1).strip()
            query = match.group(2).strip()
            return (tool_name, query)

        return None

    def _parse_answer(self, text: str) -> Optional[str]:
        """Parse the final answer from LLM output.

        Args:
            text: LLM output text

        Returns:
            Answer text or None if no answer tag found
        """
        # Pattern: <answer>answer text</answer>
        pattern = r"<answer>(.*?)</answer>"
        match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)

        if match:
            return match.group(1).strip()

        return None

    async def _search_course_content(self, query: str) -> str:
        """Search course content using context manager.

        Args:
            query: Search query

        Returns:
            Search results as formatted string
        """
        if self.bot.context_manager is None:
            logger.warning("Context manager not available")
            return "No course content available for search."

        try:
            context_result = await self.bot.context_manager.get_context_for_assistant(
                question=query,
            )

            if not context_result.has_relevant_content:
                return f"No relevant content found for: {query}"

            # Format results
            result = context_result.context
            if context_result.source_names:
                result += f"\n\n(Sources: {', '.join(context_result.source_names)})"

            logger.info(
                f"RAG search returned {context_result.total_chunks} chunks "
                f"from {len(context_result.source_names)} sources"
            )

            return result

        except Exception as e:
            logger.error(f"Search error: {e}", exc_info=True)
            return f"Search error: {str(e)}"

    async def _send_response(self, message: discord.Message, answer: str) -> None:
        """Send response to Discord, handling long messages.

        Args:
            message: Discord message to reply to
            answer: Answer text to send
        """
        # Clean up any remaining tags
        answer = re.sub(r"</?(?:tool|query|answer)>", "", answer).strip()

        if len(answer) > 2000:
            chunks = [answer[i : i + 2000] for i in range(0, len(answer), 2000)]
            for i, chunk in enumerate(chunks):
                if i == 0:
                    await message.reply(chunk, mention_author=False)
                else:
                    await message.channel.send(chunk)
        else:
            await message.reply(answer, mention_author=False)


async def create_tool(bot: "ChibiBot", config: ToolConfig) -> AssistantTool:
    """Create an AssistantTool instance.

    Args:
        bot: ChibiBot instance
        config: Tool configuration

    Returns:
        Configured AssistantTool instance
    """
    return AssistantTool(bot, config)
