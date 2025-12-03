"""Main Discord bot class for Chibi."""

import logging
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from .agent.graph import AgentGraph, create_agent_graph
from .agent.context_manager import ContextManagerAgent, create_context_manager
from .config import Config, load_config
from .content.course import Course, load_course
from .content.loader import ContentLoader
from .database.connection import Database
from .database.repositories import (
    AttendanceRepository,
    LLMQuizRepository,
    MasteryRepository,
    QuizRepository,
    RAGRepository,
    SimilarityRepository,
    UserRepository,
)
from .learning.mastery import MasteryCalculator, MasteryConfig
from .llm.manager import LLMManager
from .llm.ollama_provider import OllamaProvider
from .llm.openrouter_provider import OpenRouterProvider
from .services import (
    ContentIndexer,
    ContextualChunkingService,
    ContextualChunkConfig,
    EmbeddingService,
    GradeService,
    GuidanceService,
    LLMQuizChallengeService,
    QuizService,
    RAGService,
    SearchAgentService,
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
        self.rag_repo: Optional[RAGRepository] = None
        self.attendance_repo: Optional[AttendanceRepository] = None

        # Services
        self.quiz_service: Optional[QuizService] = None
        self.grade_service: Optional[GradeService] = None
        self.llm_quiz_service: Optional[LLMQuizChallengeService] = None
        self.guidance_service: Optional[GuidanceService] = None
        self.embedding_service: Optional[EmbeddingService] = None
        self.similarity_service: Optional[SimilarityService] = None
        self.rag_service: Optional[RAGService] = None
        self.content_indexer: Optional[ContentIndexer] = None

        # Agent components
        self.tool_registry: Optional[ToolRegistry] = None
        self.agent_graph: Optional[AgentGraph] = None
        self.context_manager: Optional[ContextManagerAgent] = None
        self.search_agent: Optional[SearchAgentService] = None

    def log_to_conversation(
        self,
        user_id: str,
        channel_id: str,
        role: str,
        content: str,
        metadata: Optional[dict] = None,
    ) -> None:
        """Log a message to conversation memory.

        This allows tools and modals to add entries to conversation history
        for better context in follow-up questions.

        Args:
            user_id: Discord user ID
            channel_id: Discord channel ID
            role: "user" or "assistant"
            content: Message content to log
            metadata: Optional metadata
        """
        if self.agent_graph and self.agent_graph.conversation_memory:
            self.agent_graph.conversation_memory.add_message(
                user_id=user_id,
                channel_id=channel_id,
                role=role,
                content=content,
                metadata=metadata,
            )

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
        self.attendance_repo = AttendanceRepository(self.database)
        logger.info("Database connected")

        # Initialize similarity repository (ChromaDB)
        self.similarity_repo = SimilarityRepository(self.config.similarity)
        await self.similarity_repo.connect()
        logger.info("Similarity repository connected")

        # Initialize RAG repository (ChromaDB)
        self.rag_repo = RAGRepository(self.config.similarity)
        await self.rag_repo.connect()
        logger.info("RAG repository connected")

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
        self.guidance_service = GuidanceService(
            mastery_repo=self.mastery_repo,
            llm_quiz_service=self.llm_quiz_service,
            course=self.course,
            min_attempts=self.config.mastery.min_attempts_for_mastery,
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

        # Initialize RAG service and content indexer
        self.rag_service = RAGService(
            embedding_service=self.embedding_service,
            rag_repo=self.rag_repo,
            top_k=5,
            min_similarity=0.3,
            max_context_length=4000,
        )

        # Initialize contextual chunking service if enabled
        contextual_service = None
        if self.config.contextual_retrieval.enabled:
            contextual_config = ContextualChunkConfig(
                enabled=True,
                max_context_tokens=self.config.contextual_retrieval.max_context_tokens,
                batch_size=self.config.contextual_retrieval.batch_size,
                batch_delay_seconds=self.config.contextual_retrieval.batch_delay_seconds,
                temperature=self.config.contextual_retrieval.temperature,
            )

            # Determine which LLM to use for context generation
            context_model = self.config.contextual_retrieval.model
            if context_model == "default":
                # Use the main LLM manager
                context_llm_manager = self.llm_manager
                logger.info("Contextual chunking using default LLM")
            else:
                # Create a dedicated LLM provider for context generation
                context_llm_manager = self._create_context_llm_manager(context_model)
                logger.info(f"Contextual chunking using dedicated model: {context_model}")

            contextual_service = ContextualChunkingService(
                llm_manager=context_llm_manager,
                config=contextual_config,
            )
            logger.info("Contextual chunking service initialized")

        self.content_indexer = ContentIndexer(
            embedding_service=self.embedding_service,
            rag_repo=self.rag_repo,
            chunk_size=500,
            chunk_overlap=100,
            contextual_chunking_service=contextual_service,
            use_contextual_retrieval=self.config.contextual_retrieval.enabled,
        )
        logger.info("Services initialized")

        # Index course content for RAG
        logger.info("Indexing course content for RAG...")
        try:
            index_stats = await self.content_indexer.index_course(
                course=self.course,
                force_reindex=False,  # Only index if not already indexed
            )
            logger.info(
                f"Course indexing complete: {index_stats['modules_indexed']} modules, "
                f"{index_stats['total_chunks']} chunks"
            )
        except Exception as e:
            logger.warning(f"Failed to index course content: {e}")

        # Initialize context manager
        self.context_manager = create_context_manager(
            rag_service=self.rag_service,
            embedding_service=self.embedding_service,
            course=self.course,
        )
        logger.info("Context manager initialized")

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

            # Initialize search agent (requires context_manager and conversation_memory)
            if self.context_manager and self.agent_graph.conversation_memory:
                self.search_agent = SearchAgentService(
                    context_manager=self.context_manager,
                    llm_manager=self.llm_manager,
                    conversation_memory=self.agent_graph.conversation_memory,
                )
                logger.info("Search agent initialized")

        # Load cogs
        await self.load_extension("chibi.cogs.quiz")
        await self.load_extension("chibi.cogs.status")
        await self.load_extension("chibi.cogs.admin")
        await self.load_extension("chibi.cogs.llm_quiz")
        await self.load_extension("chibi.cogs.modules")
        await self.load_extension("chibi.cogs.guidance")
        await self.load_extension("chibi.cogs.attendance")
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
            name="/quiz, /status, /guidance",
        )
        await self.change_presence(activity=activity)

    async def on_message(self, message: discord.Message) -> None:
        """Handle incoming messages for natural language routing.

        This method processes messages in designated channels, DMs, or
        when the bot is mentioned, and routes them through the LangGraph
        agent for intent classification and tool invocation.
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

        # Don't process if message starts with command prefix
        if message.content.startswith(self.command_prefix):
            return

        # Don't process empty messages
        if not message.content.strip():
            return

        # Determine if we should process this message
        should_process = False
        is_dm = isinstance(message.channel, discord.DMChannel)
        is_mentioned = self.user in message.mentions

        # Always process DMs
        if is_dm:
            should_process = True
            logger.debug(f"Processing DM from {message.author.display_name}")

        # Always process mentions
        elif is_mentioned:
            should_process = True
            logger.debug(f"Processing mention from {message.author.display_name}")

        # Check if channel is in the configured NL routing channels
        else:
            channel_id = message.channel.id
            nl_channels = self.config.agent.nl_routing_channels
            if nl_channels and channel_id in nl_channels:
                should_process = True

        if not should_process:
            return

        # Clean up message content (remove bot mention if present)
        content = message.content
        if is_mentioned and self.user:
            content = content.replace(f"<@{self.user.id}>", "").strip()
            content = content.replace(f"<@!{self.user.id}>", "").strip()

        logger.info(
            f"Processing NL message from {message.author.display_name}: "
            f"{content[:50]}..."
        )

        try:
            # Invoke the agent graph with cleaned content
            await self.agent_graph.invoke(message, cleaned_content=content)
        except Exception as e:
            logger.error(f"Error in agent graph: {e}", exc_info=True)
            try:
                await message.reply(
                    "I encountered an error processing your request. Please try again.",
                    mention_author=False,
                )
            except Exception:
                pass

    def _create_context_llm_manager(self, model: str) -> LLMManager:
        """Create a dedicated LLM manager for context generation.

        Args:
            model: Model specification (e.g., "ollama/llama3.2" or "openrouter/model-name")

        Returns:
            LLMManager configured for the specified model
        """
        # Parse model string to determine provider
        if model.startswith("ollama/"):
            model_name = model[7:]  # Remove "ollama/" prefix
            base_url = (
                self.config.contextual_retrieval.base_url
                or "http://localhost:11434"
            )
            context_primary = OllamaProvider(
                base_url=base_url,
                model=model_name,
                timeout=60,
            )
            # Use main fallback as backup
            context_fallback = OpenRouterProvider(
                api_key=self.config.openrouter_api_key,
                base_url=self.config.llm.fallback.base_url,
                model=self.config.llm.fallback.model,
                timeout=self.config.llm.fallback.timeout,
            )
        elif model.startswith("openrouter/"):
            model_name = model[11:]  # Remove "openrouter/" prefix
            base_url = (
                self.config.contextual_retrieval.base_url
                or "https://openrouter.ai/api/v1"
            )
            context_primary = OpenRouterProvider(
                api_key=self.config.openrouter_api_key,
                base_url=base_url,
                model=model_name,
                timeout=90,
            )
            # Use main primary (Ollama) as fallback
            context_fallback = OllamaProvider(
                base_url=self.config.llm.primary.base_url,
                model=self.config.llm.primary.model,
                timeout=self.config.llm.primary.timeout,
            )
        else:
            # Assume it's a raw model name, use primary provider type
            logger.warning(
                f"Model '{model}' has no provider prefix, assuming Ollama"
            )
            context_primary = OllamaProvider(
                base_url=self.config.contextual_retrieval.base_url or "http://localhost:11434",
                model=model,
                timeout=60,
            )
            context_fallback = OpenRouterProvider(
                api_key=self.config.openrouter_api_key,
                base_url=self.config.llm.fallback.base_url,
                model=self.config.llm.fallback.model,
                timeout=self.config.llm.fallback.timeout,
            )

        return LLMManager(context_primary, context_fallback)

    async def close(self) -> None:
        """Clean up on shutdown."""
        logger.info("Shutting down Chibi bot...")

        if self.rag_repo:
            await self.rag_repo.close()
            logger.info("RAG repository closed")

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
