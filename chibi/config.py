"""Configuration loader for Chibi bot."""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml
from dotenv import load_dotenv


@dataclass
class LLMProviderConfig:
    """Configuration for an LLM provider."""

    provider: str
    base_url: str
    model: str
    timeout: int = 60
    max_retries: int = 2


@dataclass
class LLMConfig:
    """LLM configuration with primary and fallback providers."""

    primary: LLMProviderConfig
    fallback: LLMProviderConfig
    max_tokens: int = 1024
    temperature: float = 0.7


@dataclass
class PersonaConfig:
    """Chibi persona configuration."""

    name: str = "Chibi"
    description: str = "Time-traveling AI tutor from 22nd century"


@dataclass
class MasteryConfig:
    """Mastery calculation configuration."""

    min_attempts_for_mastery: int = 3
    quality_threshold: float = 3.5
    correct_ratio_threshold: float = 0.7


@dataclass
class DatabaseConfig:
    """Database configuration."""

    path: str = "data/chibi.db"


@dataclass
class DiscordConfig:
    """Discord bot configuration."""

    sync_commands_on_startup: bool = True
    admin_channel_id: Optional[int] = None  # Channel ID where admin commands are allowed


@dataclass
class LLMQuizConfig:
    """LLM Quiz Challenge configuration."""

    target_wins_per_module: int = 3
    # Quiz model (the one students try to stump)
    quiz_model: str = "openrouter/google/gemma-3-12b-it"
    quiz_base_url: str = "https://openrouter.ai/api/v1"
    # Evaluator model (judges both answers)
    evaluator_model: str = "openrouter/google/gemini-2.5-flash-lite"
    evaluator_base_url: str = "https://openrouter.ai/api/v1"


@dataclass
class SimilarityConfig:
    """Similarity detection configuration for anti-cheat."""

    enabled: bool = True
    similarity_threshold: float = 0.85
    top_k: int = 5
    # Primary: Ollama (local)
    embedding_model: str = "nomic-embed-text"
    ollama_base_url: str = "http://localhost:11434"
    # Fallback: OpenRouter (cloud)
    fallback_enabled: bool = True
    fallback_model: str = "openai/text-embedding-3-small"
    fallback_base_url: str = "https://openrouter.ai/api/v1"
    # Storage
    chromadb_path: str = "data/chromadb"


@dataclass
class AgentConfig:
    """Agent configuration for LangGraph orchestration."""

    # Channel IDs where natural language routing is enabled
    nl_routing_channels: list = field(default_factory=list)
    # Minimum confidence threshold for intent classification
    intent_confidence_threshold: float = 0.7
    # Maximum conversation history to retain per user/channel
    max_conversation_history: int = 20
    # Whether the agent is enabled (if False, only slash commands work)
    enabled: bool = True


@dataclass
class AttendanceConfig:
    """Attendance tracking configuration."""

    # Channel ID where students submit attendance with /here command
    attendance_channel_id: Optional[int] = None
    # Seconds between code rotations
    code_rotation_interval: int = 15
    # Length of attendance codes
    code_length: int = 4


@dataclass
class ContextualRetrievalConfig:
    """Configuration for contextual retrieval (improved RAG)."""

    enabled: bool = True  # Enabled by default for better retrieval quality
    max_context_tokens: int = 100  # Max tokens for context summary
    batch_size: int = 5  # Chunks to process concurrently
    batch_delay_seconds: float = 0.5  # Delay between batches (rate limiting)
    temperature: float = 0.3  # LLM temperature for context generation
    # Model for generating context (use "default" to use main LLM)
    model: str = "default"  # e.g., "ollama/llama3.2" or "openrouter/meta-llama/llama-3.2-3b-instruct"
    base_url: str = ""  # Base URL (leave empty for default based on provider prefix)


@dataclass
class Config:
    """Main configuration container."""

    discord: DiscordConfig
    llm: LLMConfig
    persona: PersonaConfig
    mastery: MasteryConfig
    database: DatabaseConfig
    llm_quiz: LLMQuizConfig
    similarity: SimilarityConfig
    agent: AgentConfig
    attendance: AttendanceConfig
    contextual_retrieval: ContextualRetrievalConfig

    # Environment variables (loaded separately)
    discord_token: str = ""
    openrouter_api_key: str = ""


def load_config(config_path: str = "config.yaml") -> Config:
    """Load configuration from YAML file and environment variables."""
    # Load environment variables
    load_dotenv()

    # Read YAML config
    config_file = Path(config_path)
    if not config_file.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    with open(config_file, "r") as f:
        data = yaml.safe_load(f)

    # Parse LLM config
    llm_data = data.get("llm", {})
    primary_data = llm_data.get("primary", {})
    fallback_data = llm_data.get("fallback", {})

    llm_config = LLMConfig(
        primary=LLMProviderConfig(
            provider=primary_data.get("provider", "ollama"),
            base_url=primary_data.get("base_url", "http://localhost:11434"),
            model=primary_data.get("model", "llama3.2"),
            timeout=primary_data.get("timeout", 60),
            max_retries=primary_data.get("max_retries", 2),
        ),
        fallback=LLMProviderConfig(
            provider=fallback_data.get("provider", "openrouter"),
            base_url=fallback_data.get(
                "base_url", "https://openrouter.ai/api/v1"
            ),
            model=fallback_data.get("model", "meta-llama/llama-3.2-3b-instruct"),
            timeout=fallback_data.get("timeout", 90),
            max_retries=fallback_data.get("max_retries", 1),
        ),
        max_tokens=llm_data.get("max_tokens", 1024),
        temperature=llm_data.get("temperature", 0.7),
    )

    # Parse other configs
    discord_data = data.get("discord", {})
    persona_data = data.get("persona", {})
    mastery_data = data.get("mastery", {})
    database_data = data.get("database", {})
    llm_quiz_data = data.get("llm_quiz", {})
    similarity_data = data.get("similarity", {})
    agent_data = data.get("agent", {})
    attendance_data = data.get("attendance", {})
    contextual_retrieval_data = data.get("contextual_retrieval", {})

    # Load admin channel ID from environment variable
    admin_channel_id_str = os.getenv("ADMIN_CHANNEL_ID", "")
    admin_channel_id = int(admin_channel_id_str) if admin_channel_id_str else None

    # Load attendance channel ID from environment variable
    attendance_channel_id_str = os.getenv("ATTENDANCE_CHANNEL_ID", "")
    attendance_channel_id = int(attendance_channel_id_str) if attendance_channel_id_str else None

    config = Config(
        discord=DiscordConfig(
            sync_commands_on_startup=discord_data.get("sync_commands_on_startup", True),
            admin_channel_id=admin_channel_id,
        ),
        llm=llm_config,
        persona=PersonaConfig(
            name=persona_data.get("name", "Chibi"),
            description=persona_data.get(
                "description", "Time-traveling AI tutor from 22nd century"
            ),
        ),
        mastery=MasteryConfig(
            min_attempts_for_mastery=mastery_data.get("min_attempts_for_mastery", 3),
            quality_threshold=mastery_data.get("quality_threshold", 3.5),
            correct_ratio_threshold=mastery_data.get("correct_ratio_threshold", 0.7),
        ),
        database=DatabaseConfig(
            path=database_data.get("path", "data/chibi.db"),
        ),
        llm_quiz=LLMQuizConfig(
            target_wins_per_module=llm_quiz_data.get("target_wins_per_module", 3),
            quiz_model=llm_quiz_data.get("quiz_model", "openrouter/google/gemma-3-12b-it"),
            quiz_base_url=llm_quiz_data.get("quiz_base_url", "https://openrouter.ai/api/v1"),
            evaluator_model=llm_quiz_data.get("evaluator_model", "openrouter/google/gemini-2.5-flash-lite"),
            evaluator_base_url=llm_quiz_data.get("evaluator_base_url", "https://openrouter.ai/api/v1"),
        ),
        similarity=SimilarityConfig(
            enabled=similarity_data.get("enabled", True),
            similarity_threshold=similarity_data.get("similarity_threshold", 0.85),
            top_k=similarity_data.get("top_k", 5),
            embedding_model=similarity_data.get("embedding_model", "nomic-embed-text"),
            ollama_base_url=similarity_data.get("ollama_base_url", "http://localhost:11434"),
            fallback_enabled=similarity_data.get("fallback_enabled", True),
            fallback_model=similarity_data.get("fallback_model", "openai/text-embedding-3-small"),
            fallback_base_url=similarity_data.get("fallback_base_url", "https://openrouter.ai/api/v1"),
            chromadb_path=similarity_data.get("chromadb_path", "data/chromadb"),
        ),
        agent=AgentConfig(
            nl_routing_channels=agent_data.get("nl_routing_channels", []),
            intent_confidence_threshold=agent_data.get("intent_confidence_threshold", 0.7),
            max_conversation_history=agent_data.get("max_conversation_history", 20),
            enabled=agent_data.get("enabled", True),
        ),
        attendance=AttendanceConfig(
            attendance_channel_id=attendance_channel_id,
            code_rotation_interval=attendance_data.get("code_rotation_interval", 15),
            code_length=attendance_data.get("code_length", 4),
        ),
        contextual_retrieval=ContextualRetrievalConfig(
            enabled=contextual_retrieval_data.get("enabled", True),
            max_context_tokens=contextual_retrieval_data.get("max_context_tokens", 100),
            batch_size=contextual_retrieval_data.get("batch_size", 5),
            batch_delay_seconds=contextual_retrieval_data.get("batch_delay_seconds", 0.5),
            temperature=contextual_retrieval_data.get("temperature", 0.3),
            model=contextual_retrieval_data.get("model", "default"),
            base_url=contextual_retrieval_data.get("base_url", ""),
        ),
        discord_token=os.getenv("DISCORD_TOKEN", ""),
        openrouter_api_key=os.getenv("OPENROUTER_API_KEY", ""),
    )

    return config
