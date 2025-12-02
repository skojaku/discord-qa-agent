"""Chat cog for handling mentions and follow-up conversations."""

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, TYPE_CHECKING

import discord
from discord.ext import commands

from ..prompts.templates import PromptTemplates

if TYPE_CHECKING:
    from ..bot import ChibiBot

logger = logging.getLogger(__name__)


@dataclass
class ConversationMessage:
    """A message in the conversation history."""
    role: str  # "user" or "assistant"
    content: str
    timestamp: datetime = field(default_factory=datetime.now)


class ChatCog(commands.Cog):
    """Cog for handling mentions and conversational responses."""

    def __init__(self, bot: "ChibiBot"):
        self.bot = bot
        # Conversation history per channel: channel_id -> list of messages
        self._conversations: Dict[int, List[ConversationMessage]] = defaultdict(list)
        self._conversation_timeout = timedelta(minutes=30)
        self._max_history = 10  # Keep last N messages for context

    def _add_to_history(self, channel_id: int, role: str, content: str):
        """Add a message to conversation history."""
        self._conversations[channel_id].append(
            ConversationMessage(role=role, content=content)
        )
        # Trim old messages
        if len(self._conversations[channel_id]) > self._max_history:
            self._conversations[channel_id] = self._conversations[channel_id][-self._max_history:]

    def _get_conversation_context(self, channel_id: int) -> str:
        """Get recent conversation as context string."""
        messages = self._conversations.get(channel_id, [])
        if not messages:
            return ""

        # Filter out old messages
        now = datetime.now()
        recent = [m for m in messages if now - m.timestamp < self._conversation_timeout]

        if not recent:
            return ""

        # Format as conversation
        lines = ["RECENT CONVERSATION:"]
        for msg in recent[-6:]:  # Last 6 messages max
            prefix = "Student" if msg.role == "user" else "Chibi"
            # Truncate long messages
            content = msg.content[:300] + "..." if len(msg.content) > 300 else msg.content
            lines.append(f"{prefix}: {content}")

        return "\n".join(lines)

    def add_bot_message(self, channel_id: int, content: str):
        """Add a bot message to conversation history (called by other cogs)."""
        self._add_to_history(channel_id, "assistant", content)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Respond to mentions and follow-up questions."""
        # Ignore bot messages
        if message.author.bot:
            return

        # Check if bot is mentioned
        if not self.bot.user.mentioned_in(message):
            return

        # Ignore @everyone and @here
        if message.mention_everyone:
            return

        # Get the message content without the mention
        content = message.content
        for mention in message.mentions:
            content = content.replace(f"<@{mention.id}>", "").replace(f"<@!{mention.id}>", "")
        content = content.strip()

        # If empty message (just a mention), provide help
        if not content:
            await message.reply(
                "Hey! I'm Chibi, your AI tutor! 🤖\n\n"
                "You can:\n"
                "• `/ask [module] <question>` - Ask me about course topics\n"
                "• `/quiz [module]` - Test your knowledge\n"
                "• `/status` - Check your learning progress\n"
                "• Or just mention me with a question!"
            )
            return

        # Show typing indicator
        async with message.channel.typing():
            try:
                # Get or create user
                user = await self.bot.repository.get_or_create_user(
                    discord_id=str(message.author.id),
                    username=message.author.display_name,
                )

                # Get recent context (last interaction module)
                recent = await self.bot.repository.get_recent_interactions(user.id, limit=1)
                module_obj = None
                module_name = ""
                module_description = ""
                module_content = ""
                concept_list = ""

                if recent and self.bot.course:
                    module_obj = self.bot.course.get_module(recent[0].module_id)
                    if module_obj:
                        module_name = module_obj.name
                        module_description = module_obj.description
                        module_content = module_obj.content or ""
                        concept_list = "\n".join(
                            f"- {c.name}: {c.description}" for c in module_obj.concepts
                        )

                # Get conversation context
                conversation_context = self._get_conversation_context(message.channel.id)

                # Build system prompt with conversation context
                system_prompt = PromptTemplates.get_system_prompt(
                    module_name=module_name,
                    module_description=module_description,
                    module_content=module_content,
                    concept_list=concept_list,
                )

                # Add conversation context and instructions
                if conversation_context:
                    system_prompt += f"\n\n{conversation_context}\n\n"
                    system_prompt += """CONVERSATION INSTRUCTIONS:
- Look at the RECENT CONVERSATION above to understand context
- If you (Chibi) asked a question and the student is answering it, ACKNOWLEDGE their answer first
- If the student's response is an answer to your question, evaluate it briefly (correct/incorrect/partially correct)
- Then you may continue the conversation naturally"""

                # Add user message to history
                self._add_to_history(message.channel.id, "user", content)

                # Generate response
                response = await self.bot.llm_manager.generate(
                    prompt=content,
                    system_prompt=system_prompt,
                    max_tokens=self.bot.config.llm.max_tokens,
                    temperature=self.bot.config.llm.temperature,
                )

                if not response:
                    await message.reply(self.bot.llm_manager.get_error_message())
                    return

                # Add bot response to history
                self._add_to_history(message.channel.id, "assistant", response.content)

                # Log interaction
                await self.bot.repository.log_interaction(
                    user_id=user.id,
                    module_id=module_obj.id if module_obj else "general",
                    question=content,
                    response=response.content,
                )

                # Send response (split if too long)
                reply_content = response.content
                if len(reply_content) > 2000:
                    chunks = [reply_content[i:i + 1990] for i in range(0, len(reply_content), 1990)]
                    for chunk in chunks:
                        await message.reply(chunk)
                else:
                    await message.reply(reply_content)

                logger.info(f"Responded to mention from {message.author.display_name}")

            except Exception as e:
                logger.error(f"Error responding to mention: {e}", exc_info=True)
                await message.reply(
                    "Oops! My circuits got a bit tangled. Please try again! 🔧"
                )


async def setup(bot: "ChibiBot"):
    """Set up the Chat cog."""
    await bot.add_cog(ChatCog(bot))
