"""Help command cog for students."""

import logging
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from .utils import defer_interaction, handle_slash_command_errors

if TYPE_CHECKING:
    from ..bot import ChibiBot

logger = logging.getLogger(__name__)

ERROR_HELP = "Oops! Something went wrong while fetching help. Please try again!"


class HelpCog(commands.Cog):
    """Cog for the /help command."""

    def __init__(self, bot: "ChibiBot"):
        self.bot = bot

    @app_commands.command(name="help", description="Show available commands and how to use them")
    @defer_interaction(thinking=False)
    @handle_slash_command_errors(error_message=ERROR_HELP, context="/help")
    async def help(self, interaction: discord.Interaction):
        """Show help information for students."""
        embed = discord.Embed(
            title="Chibi Bot Help",
            description="Here are all the commands you can use to learn and track your progress.",
            color=discord.Color.green(),
        )

        # Quiz commands
        embed.add_field(
            name="Quiz Commands",
            value=(
                "**/quiz** - Get a quiz question to test your knowledge\n"
                "  `/quiz` - Random question from any module\n"
                "  `/quiz module:<name>` - Question from a specific module\n"
                "\n"
                "**/llm-quiz** - Challenge the AI! Try to stump it with a question\n"
                "  `/llm-quiz module:<name>` - Start a challenge for a module"
            ),
            inline=False,
        )

        # Progress commands
        embed.add_field(
            name="Progress Commands",
            value=(
                "**/status** - View your learning progress\n"
                "  `/status` - See overall progress for all modules\n"
                "  `/status module:<name>` - Detailed progress for a specific module\n"
                "\n"
                "**/modules** - List all available course modules"
            ),
            inline=False,
        )

        # Learning commands
        embed.add_field(
            name="Learning Commands",
            value=(
                "**/guidance** - Get personalized study recommendations\n"
                "  `/guidance` - Suggestions based on your current progress"
            ),
            inline=False,
        )

        # Attendance commands
        embed.add_field(
            name="Attendance Commands",
            value=(
                "**/register** - Register your student ID for attendance\n"
                "  `/register student_id:<your_id>` - Link your student ID\n"
                "\n"
                "**/here** - Submit your attendance during class\n"
                "  `/here code:<code>` - Enter the code shown by instructor"
            ),
            inline=False,
        )

        # Chat with bot
        embed.add_field(
            name="Chat with Chibi",
            value=(
                "You can also chat directly with the bot!\n"
                "- **DM the bot** - Send a direct message\n"
                "- **@mention** - Mention the bot in any channel\n"
                "\n"
                "Ask questions about the course material and get help!"
            ),
            inline=False,
        )

        # Tips
        embed.add_field(
            name="Tips",
            value=(
                "- Pass **3 quizzes per concept** to complete it\n"
                "- Use `/status` to see your progress bars\n"
                "- Challenge yourself with `/llm-quiz` to deepen understanding"
            ),
            inline=False,
        )

        embed.set_footer(text="Need more help? Ask Chibi directly!")

        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot: "ChibiBot"):
    """Set up the Help cog."""
    await bot.add_cog(HelpCog(bot))
