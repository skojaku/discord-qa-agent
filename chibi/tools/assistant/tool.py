"""Assistant tool implementation - default helpful assistant."""

import logging
from typing import TYPE_CHECKING

import discord

from ...agent.state import SubAgentState, ToolResult
from ..base import BaseTool, ToolConfig

if TYPE_CHECKING:
    from ...bot import ChibiBot

logger = logging.getLogger(__name__)


ASSISTANT_SYSTEM_PROMPT = """You are Chibi, a friendly and helpful AI tutor assistant.
Your role is to help students learn and understand course material.

Guidelines:
- Be encouraging and supportive
- Explain concepts clearly and concisely
- Use examples when helpful
- If you're not sure about something, say so
- Keep responses focused and not too long (under 500 words)
- If the question is about course-specific material, use the provided context
- If you can't answer from the context, provide general guidance and suggest they check the course materials

Available course modules:
{module_list}

{context}
"""


class AssistantTool(BaseTool):
    """Default assistant tool for general questions.

    This tool handles general questions about course content,
    providing helpful explanations using available course materials.
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

            # Build context from course content
            context = self._build_context(state.parameters.get("topic"))

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

    def _build_context(self, topic: str = None) -> str:
        """Build context from course content.

        Args:
            topic: Optional topic to focus on

        Returns:
            Context string with relevant course content
        """
        context_parts = []

        # If topic specified, try to find relevant module
        if topic:
            topic_lower = topic.lower()
            for module in self.bot.course.modules:
                # Check if topic matches module name or description
                if (
                    topic_lower in module.name.lower()
                    or (module.description and topic_lower in module.description.lower())
                ):
                    if module.content:
                        # Truncate content if too long
                        content = module.content[:3000] if len(module.content) > 3000 else module.content
                        context_parts.append(
                            f"Content from {module.name}:\n{content}"
                        )

                # Check concepts
                for concept in module.concepts:
                    if topic_lower in concept.name.lower():
                        context_parts.append(
                            f"Concept: {concept.name}\n"
                            f"Description: {concept.description}\n"
                            f"Focus: {concept.quiz_focus}"
                        )

        # If no specific context found, provide general course overview
        if not context_parts:
            context_parts.append(
                "Course: " + self.bot.course.name + "\n"
                "Description: " + (self.bot.course.description or "No description")
            )

            # Add brief concept list
            all_concepts = self.bot.course.get_all_concepts()
            if all_concepts:
                concept_names = [c.name for c in all_concepts[:20]]
                context_parts.append(
                    "Available concepts include: " + ", ".join(concept_names)
                )

        if context_parts:
            return "Relevant course context:\n" + "\n\n".join(context_parts)
        return ""


async def create_tool(bot: "ChibiBot", config: ToolConfig) -> AssistantTool:
    """Create an AssistantTool instance.

    Args:
        bot: ChibiBot instance
        config: Tool configuration

    Returns:
        Configured AssistantTool instance
    """
    return AssistantTool(bot, config)
