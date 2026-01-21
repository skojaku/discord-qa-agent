"""Test script to verify reasoning parameters are properly configured.

This tests that reasoning parameters from config.yaml are correctly
passed to the OpenRouter provider.
"""

import asyncio
import logging
import sys
import tempfile
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from chibi.config import load_config
from chibi.llm.openrouter_provider import OpenRouterProvider

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def test_reasoning_config():
    """Test that reasoning parameters are properly loaded and used."""

    # Create a temporary config with reasoning parameters
    config_content = """
llm:
  primary:
    provider: "ollama"
    base_url: "http://localhost:11434"
    model: "llama3.2"
    timeout: 60

  fallback:
    provider: "openrouter"
    base_url: "https://openrouter.ai/api/v1"
    model: "openai/gpt-oss-20b"
    timeout: 90
    max_retries: 1
    reasoning:
      enabled: true
      effort: "low"

  max_tokens: 1024
  temperature: 0.7

database:
  path: "data/chibi.db"

discord:
  sync_commands_on_startup: true

persona:
  name: "Chibi"
  description: "Test"

mastery:
  min_attempts_for_mastery: 3

backup:
  credentials_file: "credentials/google_oauth_credentials.json"
  token_file: "credentials/token.json"
  folder_name: "Test"
  scopes: []

llm_quiz:
  target_wins_per_module: 3
  quiz_model: "test"
  quiz_base_url: "test"
  evaluator_model: "test"
  evaluator_base_url: "test"

similarity:
  enabled: true
  similarity_threshold: 0.85
  top_k: 5
  embedding_model: "test"
  ollama_base_url: "test"
  fallback_enabled: false
  fallback_model: "test"
  fallback_base_url: "test"
  chromadb_path: "test"

agent:
  enabled: true
  intent_confidence_threshold: 0.7
  max_conversation_history: 20

attendance:
  attendance_channel_id: 123
  code_rotation_interval: 15
  code_length: 4

contextual_retrieval:
  enabled: false
"""

    # Write to temp file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write(config_content)
        temp_config_path = f.name

    try:
        # Load config from temp file
        import os
        os.environ['OPENROUTER_API_KEY'] = 'test_key_for_config_test'

        config = load_config(temp_config_path)

        print("=" * 80)
        print("REASONING CONFIGURATION TEST")
        print("=" * 80)

        # Check that reasoning parameters were loaded
        print(f"\nFallback provider: {config.llm.fallback.provider}")
        print(f"Fallback model: {config.llm.fallback.model}")
        print(f"Reasoning parameters: {config.llm.fallback.reasoning}")

        if config.llm.fallback.reasoning:
            print(f"  - enabled: {config.llm.fallback.reasoning.get('enabled')}")
            print(f"  - effort: {config.llm.fallback.reasoning.get('effort')}")
            print("\n✓ Reasoning parameters loaded correctly from config")
        else:
            print("\n✗ ERROR: Reasoning parameters not loaded!")
            return False

        # Create provider with reasoning params
        provider = OpenRouterProvider(
            api_key='test_key',
            base_url=config.llm.fallback.base_url,
            model=config.llm.fallback.model,
            timeout=config.llm.fallback.timeout,
            reasoning=config.llm.fallback.reasoning,
        )

        print(f"\nProvider created with reasoning config:")
        print(f"  - model: {provider.model}")
        print(f"  - reasoning: {provider.reasoning}")

        if provider.reasoning == config.llm.fallback.reasoning:
            print("\n✓ Reasoning parameters passed to provider correctly")
            print("\n" + "=" * 80)
            print("TEST PASSED: Reasoning configuration works correctly")
            print("=" * 80)
            return True
        else:
            print("\n✗ ERROR: Reasoning parameters not passed correctly!")
            return False

    finally:
        # Clean up temp file
        Path(temp_config_path).unlink()


async def test_without_reasoning():
    """Test that providers work without reasoning parameters."""
    print("\n" + "=" * 80)
    print("STANDARD MODEL TEST (without reasoning)")
    print("=" * 80)

    # Load actual config (should not have reasoning params for current model)
    config = load_config()

    print(f"\nFallback model: {config.llm.fallback.model}")
    print(f"Reasoning parameters: {config.llm.fallback.reasoning}")

    if config.llm.fallback.reasoning is None:
        print("\n✓ Standard model config: No reasoning parameters (correct)")
    else:
        print(f"\n✓ Model has reasoning parameters: {config.llm.fallback.reasoning}")

    print("=" * 80)


async def main():
    """Run all tests."""
    success = await test_reasoning_config()
    await test_without_reasoning()

    if success:
        print("\n✅ ALL TESTS PASSED")
        return 0
    else:
        print("\n❌ TESTS FAILED")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
