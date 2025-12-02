"""Main Discord bot class for Chibi."""

import logging
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from .config import Config, load_config
from .content.course import Course, load_course
from .content.loader import ContentLoader
from .database.connection import Database
from .database.repository import Repository
from .llm.manager import LLMManager
from .llm.ollama_provider import OllamaProvider
from .llm.openrouter_provider import OpenRouterProvider

logger = logging.getLogger(__name__)


class ChibiBot(commands.Bot):
    """The main Chibi Discord bot."""

    def __init__(self, config: Config):
        intents = discord.Intents.default()
        intents.message_content = True

        super().__init__(
            command_prefix="!",
            intents=intents,
            description="Chibi - Your AI tutor from the future!",
            help_command=None,  # Disable default help, we have custom !help
        )

        self.config = config
        self.course: Optional[Course] = None
        self.llm_manager: Optional[LLMManager] = None
        self.database: Optional[Database] = None
        self.repository: Optional[Repository] = None
        self.content_loader: Optional[ContentLoader] = None

    async def setup_hook(self) -> None:
        """Initialize bot components on startup."""
        logger.info("Setting up Chibi bot...")

        # Initialize database
        self.database = Database(self.config.database.path)
        await self.database.connect()
        self.repository = Repository(self.database)
        logger.info("Database connected")

        # Initialize LLM providers
        primary = OllamaProvider(
            base_url=self.config.llm.primary.base_url,
            model=self.config.llm.primary.model,
            timeout=self.config.llm.primary.timeout,
        )
        fallback = OpenRouterProvider(
            api_key=self.config.openrouter_api_key,
            base_url=self.config.llm.fallback.base_url,
            model=self.config.llm.fallback.model,
            timeout=self.config.llm.fallback.timeout,
        )
        self.llm_manager = LLMManager(primary, fallback)
        logger.info("LLM manager initialized")

        # Load course configuration
        self.course = load_course()
        logger.info(f"Course loaded: {self.course.name} with {len(self.course.modules)} modules")

        # Initialize content loader and load module content
        self.content_loader = ContentLoader()
        await self.content_loader.load_all_content(self.course)
        logger.info("Module content loaded")

        # Load cogs
        await self.load_extension("chibi.cogs.quiz")
        await self.load_extension("chibi.cogs.status")
        await self.load_extension("chibi.cogs.admin")
        logger.info("Cogs loaded")

        # Sync commands if configured
        if self.config.discord.sync_commands_on_startup:
            await self.tree.sync()
            logger.info("Commands synced")

        # Set up global error handler for app commands
        self.tree.on_error = self.on_app_command_error

    async def on_app_command_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> None:
        """Global error handler for app commands."""
        if isinstance(error, app_commands.CommandInvokeError):
            original = error.original
            if isinstance(original, discord.NotFound):
                logger.warning(f"Interaction not found (expired): {error}")
                return

        logger.error(f"App command error: {error}", exc_info=error)

        # Try to respond to the user
        try:
            if interaction.response.is_done():
                await interaction.followup.send(
                    "Oops! Something went wrong. Please try again! 🔧",
                    ephemeral=True,
                )
            else:
                await interaction.response.send_message(
                    "Oops! Something went wrong. Please try again! 🔧",
                    ephemeral=True,
                )
        except discord.NotFound:
            # Interaction expired, can't respond
            pass
        except Exception as e:
            logger.error(f"Failed to send error response: {e}")

    async def on_ready(self) -> None:
        """Called when the bot is ready."""
        logger.info(f"Logged in as {self.user} (ID: {self.user.id})")
        logger.info(f"Connected to {len(self.guilds)} guild(s)")

        # Set activity status (only show student-facing commands)
        activity = discord.Activity(
            type=discord.ActivityType.listening,
            name="/quiz, /status",
        )
        await self.change_presence(activity=activity)

    async def close(self) -> None:
        """Clean up on shutdown."""
        logger.info("Shutting down Chibi bot...")

        if self.database:
            await self.database.close()
            logger.info("Database closed")

        await super().close()


def create_bot(config_path: str = "config.yaml") -> ChibiBot:
    """Create and configure a ChibiBot instance.

    Args:
        config_path: Path to the configuration file

    Returns:
        Configured ChibiBot instance
    """
    config = load_config(config_path)
    return ChibiBot(config)
