"""Main Discord bot class for Chibi."""

import logging
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from .agent.graph import AgentGraph, create_agent_graph
from .config import Config, load_config
from .content.course import Course, load_course
from .content.loader import ContentLoader
from .database.connection import Database
from .database.repositories import (
    LLMQuizRepository,
    MasteryRepository,
    QuizRepository,
    SimilarityRepository,
    UserRepository,
)
from .learning.mastery import MasteryCalculator, MasteryConfig
from .llm.manager import LLMManager
from .llm.ollama_provider import OllamaProvider
from .llm.openrouter_provider import OpenRouterProvider
from .services import (
    EmbeddingService,
    GradeService,
    LLMQuizChallengeService,
    QuizService,
    SimilarityService,
)
from .tools.registry import ToolRegistry

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
        self.content_loader: Optional[ContentLoader] = None

        # Repositories
        self.user_repo: Optional[UserRepository] = None
        self.quiz_repo: Optional[QuizRepository] = None
        self.mastery_repo: Optional[MasteryRepository] = None
        self.llm_quiz_repo: Optional[LLMQuizRepository] = None
        self.similarity_repo: Optional[SimilarityRepository] = None

        # Services
        self.quiz_service: Optional[QuizService] = None
        self.grade_service: Optional[GradeService] = None
        self.llm_quiz_service: Optional[LLMQuizChallengeService] = None
        self.embedding_service: Optional[EmbeddingService] = None
        self.similarity_service: Optional[SimilarityService] = None

        # Agent components
        self.tool_registry: Optional[ToolRegistry] = None
        self.agent_graph: Optional[AgentGraph] = None

    async def setup_hook(self) -> None:
        """Initialize bot components on startup."""
        logger.info("Setting up Chibi bot...")

        # Initialize database and repositories
        self.database = Database(self.config.database.path)
        await self.database.connect()
        self.user_repo = UserRepository(self.database)
        self.quiz_repo = QuizRepository(self.database)
        self.mastery_repo = MasteryRepository(self.database)
        self.llm_quiz_repo = LLMQuizRepository(self.database)
        logger.info("Database connected")

        # Initialize similarity repository (ChromaDB)
        self.similarity_repo = SimilarityRepository(self.config.similarity)
        await self.similarity_repo.connect()
        logger.info("Similarity repository connected")

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

        # Initialize services
        mastery_config = MasteryConfig(
            min_attempts_for_mastery=self.config.mastery.min_attempts_for_mastery,
        )
        mastery_calculator = MasteryCalculator(mastery_config)

        self.quiz_service = QuizService(
            mastery_repo=self.mastery_repo,
            quiz_repo=self.quiz_repo,
            llm_manager=self.llm_manager,
            mastery_calculator=mastery_calculator,
            max_tokens=self.config.llm.max_tokens,
        )
        self.grade_service = GradeService(
            user_repo=self.user_repo,
            mastery_repo=self.mastery_repo,
            course=self.course,
        )
        self.llm_quiz_service = LLMQuizChallengeService(
            llm_quiz_repo=self.llm_quiz_repo,
            config=self.config.llm_quiz,
            api_key=self.config.openrouter_api_key,
        )

        # Initialize embedding and similarity services
        self.embedding_service = EmbeddingService(
            self.config.similarity,
            api_key=self.config.openrouter_api_key,
        )
        self.similarity_service = SimilarityService(
            config=self.config.similarity,
            embedding_service=self.embedding_service,
            similarity_repo=self.similarity_repo,
        )
        logger.info("Services initialized")

        # Initialize tool registry and load tools
        self.tool_registry = ToolRegistry(self)
        await self.tool_registry.load_tools_from_directory()
        logger.info(f"Tools loaded: {', '.join(self.tool_registry.get_tool_names())}")

        # Initialize agent graph (if agent is enabled)
        if self.config.agent.enabled:
            self.agent_graph = create_agent_graph(
                llm_manager=self.llm_manager,
                tool_registry=self.tool_registry,
                max_conversation_history=self.config.agent.max_conversation_history,
            )
            logger.info("Agent graph initialized")

        # Load cogs
        await self.load_extension("chibi.cogs.quiz")
        await self.load_extension("chibi.cogs.status")
        await self.load_extension("chibi.cogs.admin")
        await self.load_extension("chibi.cogs.llm_quiz")
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
            name="/quiz, /status, /llm-quiz",
        )
        await self.change_presence(activity=activity)

    async def on_message(self, message: discord.Message) -> None:
        """Handle incoming messages for natural language routing.

        This method processes messages in designated channels and routes
        them through the LangGraph agent for intent classification and
        tool invocation.
        """
        # Ignore messages from the bot itself
        if message.author == self.user:
            return

        # Ignore messages from other bots
        if message.author.bot:
            return

        # Process prefix commands first (e.g., !help)
        await self.process_commands(message)

        # Check if agent is enabled
        if not self.config.agent.enabled or self.agent_graph is None:
            return

        # Check if this channel is enabled for NL routing
        channel_id = message.channel.id
        nl_channels = self.config.agent.nl_routing_channels

        # If no channels configured, NL routing is disabled
        if not nl_channels:
            return

        # Check if current channel is in the list
        if channel_id not in nl_channels:
            return

        # Don't process if message starts with command prefix
        if message.content.startswith(self.command_prefix):
            return

        # Don't process empty messages
        if not message.content.strip():
            return

        logger.info(
            f"Processing NL message from {message.author.display_name} "
            f"in channel {channel_id}: {message.content[:50]}..."
        )

        try:
            # Invoke the agent graph
            await self.agent_graph.invoke(message)
        except Exception as e:
            logger.error(f"Error in agent graph: {e}", exc_info=True)
            try:
                await message.reply(
                    "I encountered an error processing your request. Please try again.",
                    mention_author=False,
                )
            except Exception:
                pass

    async def close(self) -> None:
        """Clean up on shutdown."""
        logger.info("Shutting down Chibi bot...")

        if self.similarity_repo:
            await self.similarity_repo.close()
            logger.info("Similarity repository closed")

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
