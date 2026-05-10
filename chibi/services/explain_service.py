"""
Explain service for managing conversational content creation sessions.

This service handles:
- Session state management for active explanation threads
- Conversation message processing
- Completion intent detection
- Educational content generation following CLAUDE.md style
- Multi-message posting to output channel
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Dict, List, Optional

import discord

from ..constants import TEMPERATURE_QUIZ_GENERATION
from ..utils.message_splitter import split_message

if TYPE_CHECKING:
    from ..llm.manager import LLMManager
    from ..services.search_agent import SearchAgentService

logger = logging.getLogger(__name__)


@dataclass
class ExplainSession:
    """State for an active explanation session."""

    thread_id: int
    topic: str
    context: str
    started_at: datetime
    admin_user_id: int
    admin_channel_id: int


class ExplainService:
    """Service for managing explanation content creation sessions."""

    # Keywords that suggest conversation completion
    COMPLETION_KEYWORDS = [
        "done",
        "ready",
        "that's it",
        "looks good",
        "finish",
        "finalize",
        "post it",
        "good to go",
        "all set",
    ]

    # Educational style guide template
    STYLE_GUIDE = """
## Writing Style Requirements

**Role:** The Engaging Lecturer
**Tone:** Educational, inviting, and authoritative but accessible.
**Core Philosophy:** "Visuals first, then intuition, then math."

### Key Guidelines:

1. **Direct Address:** Use "Let's talk about..." or "Shift your attention..."
2. **Learning Goals:** Start with a callout-note summarizing what will be learned
3. **Conversational Flow:** Use transitional questions to guide logic
4. **No Bullet Points:** Write in full, connected paragraphs
5. **No Em-dashes:** Use periods or commas instead
6. **Math:** Use LaTeX ($$ for block, $ for inline) where relevant
7. **Callouts:** Use ::: {.callout-note}, ::: {.callout-tip} for key concepts

### Example Learning Goals Callout:
```
::: {.callout-note title="What you'll learn in this module"}
This module introduces [core concept]. We will explore [Major Concept A], examine [Major Concept B], and understand how they apply to [Practical Context].
:::
```

### Voice Example:
*Bad:* "### The Spoiler\n\nLog scales are better."
*Good:* "## The Power of Scale\n\nPerhaps the most consequential choice in time series visualization is the y-axis scale. Let's look at why linear scales can be misleading..."
"""

    def __init__(
        self,
        llm_manager: "LLMManager",
        search_agent: "SearchAgentService",
        admin_channel_id: Optional[int],
        output_channel_id: Optional[int],
        thread_prefix: str = "[Explain]",
    ):
        """
        Initialize the explain service.

        Args:
            llm_manager: LLM manager for content generation
            search_agent: Search agent for RAG context retrieval
            admin_channel_id: Channel ID where admin threads are created
            output_channel_id: Channel ID where content is posted (#ai-tutor)
            thread_prefix: Prefix for thread names
        """
        self.llm_manager = llm_manager
        self.search_agent = search_agent
        self.admin_channel_id = admin_channel_id
        self.output_channel_id = output_channel_id
        self.thread_prefix = thread_prefix

        # Active sessions keyed by thread_id
        self.active_sessions: Dict[int, ExplainSession] = {}

        logger.info(
            f"ExplainService initialized: admin_channel={admin_channel_id}, "
            f"output_channel={output_channel_id}"
        )

    def create_session(
        self,
        thread_id: int,
        topic: str,
        context: str,
        admin_user_id: int,
        admin_channel_id: int,
    ) -> ExplainSession:
        """
        Create a new explanation session.

        Args:
            thread_id: Discord thread ID
            topic: The topic to explain
            context: Additional context about the explanation
            admin_user_id: User ID of the admin starting the session
            admin_channel_id: Channel ID where the thread was created

        Returns:
            Created session
        """
        session = ExplainSession(
            thread_id=thread_id,
            topic=topic,
            context=context,
            started_at=datetime.now(),
            admin_user_id=admin_user_id,
            admin_channel_id=admin_channel_id,
        )
        self.active_sessions[thread_id] = session
        logger.info(f"Created explain session for thread {thread_id}: {topic}")
        return session

    def get_active_session(self, thread_id: int) -> Optional[ExplainSession]:
        """
        Get an active session by thread ID.

        Args:
            thread_id: Discord thread ID

        Returns:
            Session if active, None otherwise
        """
        return self.active_sessions.get(thread_id)

    def remove_session(self, thread_id: int) -> None:
        """
        Remove a session from active sessions.

        Args:
            thread_id: Discord thread ID
        """
        if thread_id in self.active_sessions:
            del self.active_sessions[thread_id]
            logger.info(f"Removed explain session for thread {thread_id}")

    async def generate_initial_message(
        self, topic: str, context: str
    ) -> str:
        """
        Generate the initial bot message to start the conversation.

        Args:
            topic: The topic to explain
            context: Additional context

        Returns:
            Initial message content
        """
        prompt = f"""You are helping create educational content for students.

Topic: {topic}
Context: {context}

Generate a friendly opening message that:
1. Acknowledges the topic
2. Asks 1-2 clarifying questions to understand:
   - Target audience level (beginner, intermediate, advanced)
   - Specific aspects to focus on
   - Any examples or use cases to include

Keep it conversational and encouraging. End with clear questions.
"""

        try:
            response = await self.llm_manager.generate(
                prompt=prompt,
                max_tokens=300,
                temperature=0.7,
            )
            return response.content
        except Exception as e:
            logger.error(f"Error generating initial message: {e}", exc_info=True)
            # Fallback message
            return (
                f"Great! Let's create educational content about **{topic}**.\n\n"
                f"To make this as helpful as possible, I have a few questions:\n"
                f"- Who is the target audience? (e.g., beginners, intermediate learners)\n"
                f"- Are there specific aspects or concepts you want me to focus on?\n"
                f"- Should I include any particular examples or applications?"
            )

    async def handle_thread_message(self, message: discord.Message) -> None:
        """
        Handle a message in an active explain thread.

        Args:
            message: Discord message in the thread
        """
        session = self.get_active_session(message.channel.id)
        if not session:
            logger.warning(f"No active session for thread {message.channel.id}")
            return

        # Don't process bot's own messages
        if message.author.bot:
            return

        # Check for completion intent
        if await self.detect_completion_intent(message.content):
            logger.info(f"Completion intent detected in thread {message.channel.id}")
            await self.show_confirmation(message.channel)
        else:
            # Continue conversation
            await self.continue_conversation(message, session)

    async def detect_completion_intent(self, message_content: str) -> bool:
        """
        Detect if the user is signaling conversation completion.

        Uses two-tier approach:
        1. Fast path: Check explicit keywords
        2. LLM classification for nuanced detection

        Args:
            message_content: The message to analyze

        Returns:
            True if completion intent detected
        """
        # Fast path: keyword matching
        content_lower = message_content.lower()
        if any(keyword in content_lower for keyword in self.COMPLETION_KEYWORDS):
            return True

        # LLM classification for nuanced cases
        # Only use for longer messages (avoid false positives on short responses)
        if len(message_content) > 20:
            try:
                prompt = f"""Determine if this message signals the user is done with the conversation and ready to finalize:

Message: "{message_content}"

Answer only: YES or NO"""

                response = await self.llm_manager.generate(
                    prompt=prompt, max_tokens=5, temperature=0.0
                )
                return "yes" in response.content.lower()
            except Exception as e:
                logger.error(f"Error in LLM completion detection: {e}")
                return False

        return False

    async def show_confirmation(self, thread: discord.Thread) -> None:
        """
        Show confirmation buttons asking if ready to post.

        Args:
            thread: Discord thread to post in
        """
        # Import here to avoid circular dependency
        from ..ui.views.explain_confirm import ExplainConfirmView

        embed = discord.Embed(
            title="Ready to Create Content?",
            description=(
                "I can now generate the educational content based on our conversation.\n\n"
                "Should I create and post it to the AI Tutor channel?"
            ),
            color=discord.Color.blue(),
        )

        view = ExplainConfirmView(explain_service=self, thread=thread)
        await thread.send(embed=embed, view=view)

    async def continue_conversation(
        self, message: discord.Message, session: ExplainSession
    ) -> None:
        """
        Continue the conversation with a response.

        Args:
            message: Discord message to respond to
            session: Active explain session
        """
        # Get conversation history from thread
        history = await self._get_conversation_history(message.channel)

        # Generate contextual response
        prompt = f"""You are helping create educational content for students.

Topic: {session.topic}
Context: {session.context}

Recent conversation:
{history}

Latest user message: {message.content}

Generate a helpful response that:
1. Acknowledges their input
2. Asks follow-up questions if needed to clarify details
3. Or confirms understanding and asks if they're ready to generate the content

Keep it conversational, helpful, and focused on gathering what's needed for excellent educational content.
"""

        try:
            async with message.channel.typing():
                response = await self.llm_manager.generate(
                    prompt=prompt, max_tokens=400, temperature=0.7
                )
            await message.reply(response.content, mention_author=False)
        except Exception as e:
            logger.error(f"Error generating conversation response: {e}", exc_info=True)
            await message.reply(
                "I encountered an error processing your message. Please try again or "
                "type 'ready' if you want to proceed with generating the content.",
                mention_author=False,
            )

    async def _get_conversation_history(
        self, thread: discord.Thread, limit: int = 20
    ) -> str:
        """
        Get conversation history from thread.

        Args:
            thread: Discord thread
            limit: Maximum messages to retrieve

        Returns:
            Formatted conversation history
        """
        messages = []
        async for msg in thread.history(limit=limit, oldest_first=True):
            if msg.author.bot:
                messages.append(f"Bot: {msg.content}")
            else:
                messages.append(f"User: {msg.content}")

        return "\n".join(messages[-10:])  # Last 10 exchanges

    async def generate_educational_content(
        self, thread: discord.Thread, session: ExplainSession
    ) -> str:
        """
        Generate educational content following CLAUDE.md style.

        Args:
            thread: Discord thread with conversation
            session: Active session

        Returns:
            Generated educational content
        """
        # Get full conversation history
        conversation = await self._get_conversation_history(thread, limit=50)

        # Query RAG for relevant course content
        rag_context = ""
        try:
            rag_result = await self.search_agent.search_for_assistant(
                query=session.topic,
                user_id=str(session.admin_user_id),
                channel_id=str(session.admin_channel_id),
            )
            if rag_result.has_relevant_content:
                rag_context = f"\n\nRelevant course content:\n{rag_result.answer}"
        except Exception as e:
            logger.warning(f"Error retrieving RAG context: {e}")

        # Build comprehensive generation prompt
        prompt = f"""{self.STYLE_GUIDE}

## Your Task

Create educational content for the following:

**Topic:** {session.topic}
**Context:** {session.context}

**Conversation Summary:**
{conversation}
{rag_context}

## Requirements

Generate a complete educational explanation that:
1. Starts with a learning goals callout (use ::: {{.callout-note title="What you'll learn"}})
2. Uses conversational tone with direct address
3. Has clear sections with Markdown headers (##, ###)
4. Writes full paragraphs (NO bullet points)
5. Includes examples and concrete applications
6. Uses LaTeX for any math ($$...$$ for blocks, $...$ for inline)
7. Ends with practical takeaways or a challenge (use ::: {{.callout-tip}})

Write the complete content now, following all style guidelines above.
"""

        try:
            content = await self.llm_manager.generate(
                prompt=prompt,
                max_tokens=2500,
                temperature=TEMPERATURE_QUIZ_GENERATION,  # Creative but not random
            )
            return content.content
        except Exception as e:
            logger.error(f"Error generating educational content: {e}", exc_info=True)
            raise

    async def post_to_output_channel(
        self,
        bot: discord.Client,
        session: ExplainSession,
        content: str,
    ) -> Optional[discord.Thread]:
        """
        Post generated content to the output channel.

        Creates a thread in the output channel and posts content
        split across multiple messages if necessary.

        Args:
            bot: Discord bot client
            session: Active session
            content: Generated content to post

        Returns:
            Created thread, or None if failed
        """
        if not self.output_channel_id:
            logger.error("Output channel ID not configured")
            return None

        try:
            channel = bot.get_channel(self.output_channel_id)
            if not channel:
                logger.error(f"Output channel {self.output_channel_id} not found")
                return None

            # Create thread in output channel
            thread_name = f"{self.thread_prefix} {session.topic}"
            if len(thread_name) > 100:  # Discord thread name limit
                thread_name = thread_name[:97] + "..."

            thread = await channel.create_thread(
                name=thread_name,
                auto_archive_duration=1440,  # 24 hours
            )

            # Split content if needed
            chunks = split_message(content, max_length=1900)

            # Post each chunk
            for i, chunk in enumerate(chunks):
                if i > 0:
                    # Small delay between messages to avoid rate limits
                    await asyncio.sleep(0.5)
                await thread.send(chunk)

            logger.info(
                f"Posted content to thread {thread.id} in channel {self.output_channel_id}"
            )
            return thread

        except Exception as e:
            logger.error(f"Error posting to output channel: {e}", exc_info=True)
            raise

    async def archive_admin_thread(self, thread: discord.Thread) -> None:
        """
        Archive the admin thread after successful posting.

        Args:
            thread: Discord thread to archive
        """
        try:
            await thread.edit(archived=True, locked=True)
            logger.info(f"Archived admin thread {thread.id}")
        except Exception as e:
            logger.error(f"Error archiving thread {thread.id}: {e}", exc_info=True)
