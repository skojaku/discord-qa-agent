"""Chat cog for handling mentions and follow-up conversations."""

import logging
from typing import TYPE_CHECKING

import discord
from discord.ext import commands

from ..prompts.templates import PromptTemplates

if TYPE_CHECKING:
    from ..bot import ChibiBot

logger = logging.getLogger(__name__)


class ChatCog(commands.Cog):
    """Cog for handling mentions and conversational responses."""

    def __init__(self, bot: "ChibiBot"):
        self.bot = bot

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

                # Build system prompt
                system_prompt = PromptTemplates.get_system_prompt(
                    module_name=module_name,
                    module_description=module_description,
                    module_content=module_content,
                    concept_list=concept_list,
                )

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
