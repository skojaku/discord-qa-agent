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
class Config:
    """Main configuration container."""

    discord: DiscordConfig
    llm: LLMConfig
    persona: PersonaConfig
    mastery: MasteryConfig
    database: DatabaseConfig

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

    # Load admin channel ID from environment variable
    admin_channel_id_str = os.getenv("ADMIN_CHANNEL_ID", "")
    admin_channel_id = int(admin_channel_id_str) if admin_channel_id_str else None

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
        discord_token=os.getenv("DISCORD_TOKEN", ""),
        openrouter_api_key=os.getenv("OPENROUTER_API_KEY", ""),
    )

    return config
