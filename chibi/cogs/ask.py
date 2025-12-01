"""Ask command cog for Q&A interactions."""

import logging
from typing import List, TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from ..prompts.templates import PromptTemplates

if TYPE_CHECKING:
    from ..bot import ChibiBot

logger = logging.getLogger(__name__)


class AskCog(commands.Cog):
    """Cog for the /ask command."""

    def __init__(self, bot: "ChibiBot"):
        self.bot = bot

    async def module_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> List[app_commands.Choice[str]]:
        """Autocomplete for module selection."""
        if not self.bot.course:
            return []

        choices = []
        for module in self.bot.course.modules:
            display_name = f"{module.id}: {module.name}"
            # Filter by current input
            if current.lower() in display_name.lower():
                choices.append(
                    app_commands.Choice(name=display_name[:100], value=module.id)
                )

        return choices[:25]  # Discord limit

    @app_commands.command(name="ask", description="Ask Chibi about a topic in your course")
    @app_commands.describe(
        question="Your question about the course material",
        module="The module to ask about (optional - type to search)",
    )
    @app_commands.autocomplete(module=module_autocomplete)
    async def ask(
        self,
        interaction: discord.Interaction,
        question: str,
        module: str = None,
    ):
        """Ask a question about course content."""
        # Defer response since LLM may take time
        await interaction.response.defer(thinking=True)

        try:
            # Get or create user
            user = await self.bot.repository.get_or_create_user(
                discord_id=str(interaction.user.id),
                username=interaction.user.display_name,
            )

            # Get module context
            module_obj = None
            module_content = ""
            module_name = ""
            module_description = ""
            concept_list = ""

            if module and self.bot.course:
                module_obj = self.bot.course.get_module(module)
                if module_obj:
                    module_name = module_obj.name
                    module_description = module_obj.description
                    module_content = module_obj.content or ""
                    concept_list = "\n".join(
                        f"- {c.name}: {c.description}" for c in module_obj.concepts
                    )

            # Get student profile context
            mastery_summary = "No mastery data yet"
            recent_topics = "None"

            if self.bot.repository:
                # Get mastery summary
                summary = await self.bot.repository.get_mastery_summary(user.id)
                if summary.get("total_quiz_attempts", 0) > 0:
                    mastery_summary = (
                        f"Mastered: {summary.get('mastered', 0)}, "
                        f"Proficient: {summary.get('proficient', 0)}, "
                        f"Learning: {summary.get('learning', 0)}"
                    )

                # Get recent interactions
                recent = await self.bot.repository.get_recent_interactions(user.id, limit=3)
                if recent:
                    recent_topics = ", ".join(r.module_id for r in recent)

            # Build system prompt
            system_prompt = PromptTemplates.get_system_prompt(
                module_name=module_name,
                module_description=module_description,
                module_content=module_content,
                concept_list=concept_list,
                mastery_summary=mastery_summary,
                recent_topics=recent_topics,
            )

            # Generate response
            response = await self.bot.llm_manager.generate(
                prompt=question,
                system_prompt=system_prompt,
                max_tokens=self.bot.config.llm.max_tokens,
                temperature=self.bot.config.llm.temperature,
            )

            if not response:
                await interaction.followup.send(
                    self.bot.llm_manager.get_error_message()
                )
                return

            # Log interaction
            await self.bot.repository.log_interaction(
                user_id=user.id,
                module_id=module or "general",
                question=question,
                response=response.content,
            )

            # Send response (split if too long)
            content = response.content
            if len(content) > 2000:
                # Split into chunks
                chunks = [content[i : i + 1990] for i in range(0, len(content), 1990)]
                for i, chunk in enumerate(chunks):
                    if i == 0:
                        await interaction.followup.send(chunk)
                    else:
                        await interaction.followup.send(chunk)
            else:
                await interaction.followup.send(content)

            logger.info(
                f"Answered question from {interaction.user.display_name} "
                f"about module {module or 'general'}"
            )

        except Exception as e:
            logger.error(f"Error in /ask command: {e}", exc_info=True)
            await interaction.followup.send(
                "Oops! Something went wrong while processing your question. "
                "Please try again! 🔧"
            )


async def setup(bot: "ChibiBot"):
    """Set up the Ask cog."""
    await bot.add_cog(AskCog(bot))
