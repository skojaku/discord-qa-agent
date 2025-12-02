"""Modules command cog for listing available course modules."""

import logging
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from .utils import defer_interaction, handle_slash_command_errors

if TYPE_CHECKING:
    from ..bot import ChibiBot

logger = logging.getLogger(__name__)

ERROR_MODULES = "Oops! Something went wrong while fetching modules. Please try again!"


class ModulesCog(commands.Cog):
    """Cog for the /modules command."""

    def __init__(self, bot: "ChibiBot"):
        self.bot = bot

    @app_commands.command(name="modules", description="List all available course modules")
    @defer_interaction(thinking=False)
    @handle_slash_command_errors(error_message=ERROR_MODULES, context="/modules")
    async def modules(self, interaction: discord.Interaction):
        """List all available modules in the course."""
        modules = self.bot.course.modules

        if not modules:
            await interaction.followup.send(
                "No modules available in the course yet.",
                ephemeral=True,
            )
            return

        embed = discord.Embed(
            title="📚 Available Modules",
            description=f"There are **{len(modules)}** modules in this course.",
            color=discord.Color.blue(),
        )

        # Group modules into chunks to avoid field limit
        module_lines = []
        for module in modules:
            concept_count = len(module.concepts) if module.concepts else 0
            description = module.description[:80] + "..." if module.description and len(module.description) > 80 else (module.description or "No description")
            module_lines.append(
                f"**`{module.id}`** - {module.name}\n"
                f"  ↳ {description} ({concept_count} concepts)"
            )

        # Split into multiple fields if needed (Discord limits field value to 1024 chars)
        current_field = []
        current_length = 0

        for line in module_lines:
            line_length = len(line) + 1  # +1 for newline
            if current_length + line_length > 1000 and current_field:
                embed.add_field(
                    name="Modules" if len(embed.fields) == 0 else "​",  # Zero-width space for continuation
                    value="\n".join(current_field),
                    inline=False,
                )
                current_field = []
                current_length = 0

            current_field.append(line)
            current_length += line_length

        # Add remaining modules
        if current_field:
            embed.add_field(
                name="Modules" if len(embed.fields) == 0 else "​",
                value="\n".join(current_field),
                inline=False,
            )

        embed.set_footer(
            text="Use the module ID (e.g., 'quiz me on module-1' or 'llm quiz module-1')"
        )

        await interaction.followup.send(embed=embed)


async def setup(bot: "ChibiBot"):
    """Set up the Modules cog."""
    await bot.add_cog(ModulesCog(bot))
