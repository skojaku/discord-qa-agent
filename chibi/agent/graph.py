"""Main ReAct Agent using LangGraph."""

import logging
import re
from typing import TYPE_CHECKING, Any, Dict, Optional

from langgraph.graph import END, StateGraph

from .memory import ConversationMemory
from .state import AgentState, SubAgentState, ToolResult

if TYPE_CHECKING:
    from ..llm.manager import LLMManager
    from ..tools.registry import ToolRegistry

logger = logging.getLogger(__name__)

# Maximum iterations for ReAct loop
MAX_ITERATIONS = 3

SYSTEM_PROMPT = """You are Chibi, a friendly and helpful AI tutor assistant.
Your role is to help students learn and understand course material.

You have these tools available:

1. <tool>search_course_content</tool><query>your search query</query>
   Search course materials for information to answer questions about course concepts.

2. <tool>quiz</tool><params>{{"module": "optional-module-id"}}</params>
   Generate a quiz question for the student. Use when they ask for a quiz or to test themselves.

3. <tool>status</tool>
   Show the student's learning progress and mastery levels.

4. <tool>llm_quiz</tool><params>{{"module": "module-id"}}</params>
   Start an LLM challenge where the student tries to stump/challenge the AI.
   IMPORTANT: Always invoke this tool when user mentions "llm quiz", "challenge", "stump the ai", etc.
   If no module specified, invoke with empty params - the tool will prompt for module selection.

5. <tool>guidance</tool>
   Show learning guidance and recommendations.

WHEN TO USE TOOLS (ALWAYS USE THE TOOL, DO NOT RESPOND CONVERSATIONALLY):
- search_course_content: Questions about course concepts, need explanations
- quiz: User asks for quiz, practice, or to test themselves
- status: User asks about progress, scores, mastery, or performance
- llm_quiz: User mentions "llm quiz", "challenge the AI", "stump the AI", "challenge", etc.
- guidance: User asks for learning advice or what to study

WHEN NOT TO USE TOOLS:
- Greetings (hi, hello, how are you)
- Simple thanks or farewells
- Questions about yourself (what's your name, who are you)

TYPO TOLERANCE:
- Users may have typos in their messages - be forgiving and interpret their intent
- "quzi" → quiz, "statsu" → status, "challange" → challenge, "serach" → search
- If a message looks like a question about course content (even with typos), use search_course_content
- When in doubt about intent, default to search_course_content rather than asking for clarification

CRITICAL: When a user's intent matches a tool, ALWAYS invoke the tool. Do NOT have a conversation about it.
DEFAULT: When unclear but seems like a course-related question, use <tool>search_course_content</tool>
- User: "let's do llm quiz" → Use <tool>llm_quiz</tool>
- User: "quiz me" → Use <tool>quiz</tool>
- User: "show my status" → Use <tool>status</tool>

UNDERSTANDING CONVERSATION CONTEXT:
- When the user gives a short response (yes, no, sure, tell me more), look at conversation context
- If the user provides a module name/ID as a follow-up, that's likely a parameter for the previous tool request

After using tools (if needed), provide your final response:
<answer>your response here</answer>

Guidelines:
- Be encouraging and supportive
- Keep responses brief and conversational (2-3 sentences)
- Use intuition and examples before technical details
- Use proper syntax highlighting: ```python, ```r
- Use LaTeX: $inline$ or $$display$$
- Use a friendly tone with occasional emojis 😊
- Ask ONE focused follow-up question when appropriate

{module_list}
"""

USER_PROMPT = """Student: {message}

{context}

Think step by step:
1. What is the student asking?
2. Do I need a tool, or can I answer from context?
3. If using a tool, which one and with what parameters?
4. Provide response with <answer>...</answer>"""


class MainAgent:
    """Main ReAct agent using LangGraph."""

    def __init__(
        self,
        llm_manager: "LLMManager",
        tool_registry: "ToolRegistry",
        conversation_memory: ConversationMemory,
        course: Any = None,
    ):
        """Initialize the main agent.

        Args:
            llm_manager: LLM manager for generation
            tool_registry: Registry of available tools
            conversation_memory: Conversation memory manager
            course: Course object with modules
        """
        self.llm_manager = llm_manager
        self.tool_registry = tool_registry
        self.conversation_memory = conversation_memory
        self.course = course
        self.graph = self._build_graph()
        logger.info("Main ReAct agent initialized")

    def _build_graph(self) -> StateGraph:
        """Build the LangGraph StateGraph with ReAct pattern.

        Returns:
            Compiled StateGraph
        """
        graph = StateGraph(AgentState)

        # Add nodes
        graph.add_node("reason", self._reason_node)
        graph.add_node("execute_tool", self._execute_tool_node)
        graph.add_node("respond", self._respond_node)

        # Set entry point
        graph.set_entry_point("reason")

        # Add edges
        graph.add_conditional_edges(
            "reason",
            self._should_execute_tool,
            {
                "execute": "execute_tool",
                "respond": "respond",
            },
        )
        graph.add_edge("execute_tool", "reason")  # Loop back after tool execution
        graph.add_edge("respond", END)

        return graph.compile()

    def _build_system_prompt(self) -> str:
        """Build system prompt with module list."""
        module_list = ""
        if self.course and hasattr(self.course, "modules"):
            modules = [
                f"- {m.name}: {m.description or 'No description'}"
                for m in self.course.modules
            ]
            if modules:
                module_list = "Available course modules:\n" + "\n".join(modules)

        return SYSTEM_PROMPT.format(module_list=module_list)

    async def _reason_node(self, state: AgentState) -> Dict[str, Any]:
        """Reasoning node - LLM decides what to do next.

        Args:
            state: Current agent state

        Returns:
            Updated state with pending tool call or final response
        """
        user_id = state.get("user_id", "")
        channel_id = state.get("channel_id", "")
        user_message = state.get("user_message", "")
        iteration = state.get("iteration", 0)
        observations = state.get("observations", [])

        # Build context from conversation history and observations
        context_parts = []

        # Add conversation history
        history = self.conversation_memory.get_context_summary(
            user_id=user_id,
            channel_id=channel_id,
            max_messages=5,
        )
        if history:
            context_parts.append(f"Recent conversation:\n{history}")

        # Add tool observations from current turn
        if observations:
            context_parts.append("Tool observations this turn:\n" + "\n".join(observations))

        context = "\n\n".join(context_parts) if context_parts else ""

        # Build prompt
        prompt = USER_PROMPT.format(message=user_message, context=context)
        system_prompt = self._build_system_prompt()

        # Generate response
        response = await self.llm_manager.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            max_tokens=1024,
            temperature=0.7,
        )

        if not response or not response.content:
            logger.warning("Empty LLM response in reason node")
            return {
                "final_response": "I'm sorry, I couldn't process your request. Please try again.",
                "pending_tool_call": None,
                "iteration": iteration + 1,
            }

        llm_output = response.content.strip()
        logger.debug(f"LLM output: {llm_output[:200]}...")

        # Parse for tool call
        tool_call = self._parse_tool_call(llm_output)

        # Parse for final answer
        final_answer = self._parse_answer(llm_output)

        # If no tool call and no answer tag, check if we should fallback to search
        if not tool_call and not final_answer:
            # Check if this looks like a question about course content
            user_message_lower = user_message.lower()
            question_indicators = ['?', 'what', 'how', 'why', 'when', 'where', 'who', 'explain', 'tell me', 'describe']
            looks_like_question = any(ind in user_message_lower for ind in question_indicators)

            # If it looks like a question and we haven't tried search yet, fallback to search
            if looks_like_question and iteration == 0 and len(user_message) > 5:
                logger.info(f"Fallback to search for unclear question: {user_message[:50]}")
                tool_call = {
                    "name": "search_course_content",
                    "query": user_message,
                    "params": {},
                }
            else:
                # Otherwise treat the LLM output as the answer
                final_answer = llm_output

        return {
            "pending_tool_call": tool_call,
            "final_response": final_answer,
            "iteration": iteration + 1,
        }

    def _should_execute_tool(self, state: AgentState) -> str:
        """Determine if we should execute a tool or respond.

        Args:
            state: Current agent state

        Returns:
            "execute" if tool should be executed, "respond" otherwise
        """
        pending_tool = state.get("pending_tool_call")
        iteration = state.get("iteration", 0)
        max_iterations = state.get("max_iterations", MAX_ITERATIONS)

        # If we have a pending tool call and haven't exceeded iterations
        if pending_tool and iteration < max_iterations:
            return "execute"

        return "respond"

    async def _execute_tool_node(self, state: AgentState) -> Dict[str, Any]:
        """Execute the pending tool call.

        Args:
            state: Current agent state

        Returns:
            Updated state with tool result as observation
        """
        pending_tool = state.get("pending_tool_call")
        if not pending_tool:
            return {"pending_tool_call": None}

        tool_name = pending_tool.get("name", "")
        query = pending_tool.get("query", "")
        params = pending_tool.get("params", {})

        logger.info(f"Executing tool: {tool_name}")

        # Get tool from registry
        tool = self.tool_registry.get_tool(tool_name)
        if not tool:
            observation = f"Tool '{tool_name}' not found."
            logger.warning(observation)
            observations = state.get("observations", [])
            return {
                "observations": observations + [observation],
                "pending_tool_call": None,
            }

        # Create SubAgentState for tool
        sub_state = SubAgentState(
            user_id=state.get("user_id", ""),
            user_name=state.get("user_name", ""),
            task_description=query or state.get("user_message", ""),
            parameters=params,
            context_summary="",
            discord_message=state.get("discord_message"),
        )

        try:
            result = await tool.execute(sub_state)

            # Build observation from result
            if result.success:
                observation = f"Tool '{tool_name}' result: {result.summary}"
            else:
                observation = f"Tool '{tool_name}' failed: {result.error or 'Unknown error'}"

            logger.debug(f"Tool observation: {observation}")

            # Update state
            tool_results = state.get("tool_results", [])
            observations = state.get("observations", [])

            return {
                "tool_results": tool_results + [result],
                "observations": observations + [observation],
                "pending_tool_call": None,
            }

        except Exception as e:
            logger.error(f"Error executing tool {tool_name}: {e}", exc_info=True)
            observations = state.get("observations", [])
            return {
                "observations": observations + [f"Tool '{tool_name}' error: {str(e)}"],
                "pending_tool_call": None,
            }

    async def _respond_node(self, state: AgentState) -> Dict[str, Any]:
        """Send final response to Discord.

        Args:
            state: Current agent state

        Returns:
            Updated state with response_sent flag
        """
        discord_message = state.get("discord_message")
        final_response = state.get("final_response")
        tool_results = state.get("tool_results", [])

        # Check if any tool already sent a response
        for result in tool_results:
            if result.metadata.get("response_sent"):
                logger.debug("Tool already sent response, skipping main agent response")
                return {"response_sent": True}

        if not final_response:
            final_response = "I'm not sure how to help with that. Could you try rephrasing, or ask me to 'quiz', 'status', or 'search' for something specific?"

        # Clean up response
        final_response = self._clean_response(final_response)

        if discord_message:
            try:
                await self._send_response(discord_message, final_response)
            except Exception as e:
                logger.error(f"Error sending response: {e}", exc_info=True)

        # Log to conversation memory
        user_id = state.get("user_id", "")
        channel_id = state.get("channel_id", "")

        if user_id and channel_id:
            # Log user message
            self.conversation_memory.add_message(
                user_id=user_id,
                channel_id=channel_id,
                role="user",
                content=state.get("user_message", ""),
            )

            # Log assistant response
            self.conversation_memory.add_message(
                user_id=user_id,
                channel_id=channel_id,
                role="assistant",
                content=final_response,
            )

        return {"response_sent": True}

    def _parse_tool_call(self, text: str) -> Optional[Dict[str, Any]]:
        """Parse a tool call from LLM output.

        Args:
            text: LLM output text

        Returns:
            Dict with tool name and parameters, or None
        """
        # Pattern: <tool>tool_name</tool><query>...</query> or <tool>tool_name</tool><params>...</params>
        tool_pattern = r"<tool>(\w+)</tool>"
        tool_match = re.search(tool_pattern, text, re.IGNORECASE)

        if not tool_match:
            return None

        tool_name = tool_match.group(1).strip()

        # Try to get query
        query_pattern = r"<query>(.*?)</query>"
        query_match = re.search(query_pattern, text, re.DOTALL | re.IGNORECASE)
        query = query_match.group(1).strip() if query_match else ""

        # Try to get params (JSON)
        params_pattern = r"<params>(.*?)</params>"
        params_match = re.search(params_pattern, text, re.DOTALL | re.IGNORECASE)
        params = {}

        if params_match:
            try:
                import json
                params = json.loads(params_match.group(1).strip())
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse tool params: {params_match.group(1)}")

        return {
            "name": tool_name,
            "query": query,
            "params": params,
        }

    def _parse_answer(self, text: str) -> Optional[str]:
        """Parse the final answer from LLM output.

        Args:
            text: LLM output text

        Returns:
            Answer text or None
        """
        pattern = r"<answer>(.*?)</answer>"
        match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)

        if match:
            return match.group(1).strip()

        return None

    def _clean_response(self, text: str) -> str:
        """Clean up response text by removing XML tags.

        Args:
            text: Response text

        Returns:
            Cleaned text
        """
        # Remove XML tags
        text = re.sub(r"</?(?:tool|query|answer|params)>", "", text)
        # Remove any JSON-like content that might have slipped through
        text = re.sub(r"\{[^}]*\}", "", text)
        return text.strip()

    async def _send_response(self, message: Any, response: str) -> None:
        """Send response to Discord, handling long messages.

        Args:
            message: Discord message to reply to
            response: Response text
        """
        if not response:
            return

        if len(response) > 2000:
            chunks = [response[i : i + 2000] for i in range(0, len(response), 2000)]
            for i, chunk in enumerate(chunks):
                if i == 0:
                    await message.reply(chunk, mention_author=False)
                else:
                    await message.channel.send(chunk)
        else:
            await message.reply(response, mention_author=False)

    async def invoke(
        self,
        discord_message: Any,
        cleaned_content: str = None,
    ) -> Dict[str, Any]:
        """Invoke the agent with a Discord message.

        Args:
            discord_message: Discord message that triggered the agent
            cleaned_content: Optional pre-cleaned message content

        Returns:
            Final state after graph execution
        """
        content = cleaned_content or discord_message.content

        initial_state: AgentState = {
            "user_id": str(discord_message.author.id),
            "user_name": discord_message.author.display_name,
            "channel_id": str(discord_message.channel.id),
            "guild_id": str(discord_message.guild.id) if discord_message.guild else None,
            "discord_message": discord_message,
            "user_message": content,
            "iteration": 0,
            "max_iterations": MAX_ITERATIONS,
            "pending_tool_call": None,
            "tool_results": [],
            "observations": [],
            "final_response": None,
            "response_sent": False,
        }

        try:
            final_state = await self.graph.ainvoke(initial_state)
            return final_state
        except Exception as e:
            logger.error(f"Error invoking agent: {e}", exc_info=True)
            try:
                await discord_message.reply(
                    "I encountered an error processing your request. Please try again.",
                    mention_author=False,
                )
            except Exception:
                pass
            return initial_state


def create_agent(
    llm_manager: "LLMManager",
    tool_registry: "ToolRegistry",
    conversation_memory: ConversationMemory,
    course: Any = None,
) -> MainAgent:
    """Create and configure a MainAgent instance.

    Args:
        llm_manager: LLM manager for generation
        tool_registry: Registry of available tools
        conversation_memory: Conversation memory manager
        course: Course object with modules

    Returns:
        Configured MainAgent instance
    """
    return MainAgent(
        llm_manager=llm_manager,
        tool_registry=tool_registry,
        conversation_memory=conversation_memory,
        course=course,
    )
