"""Test script for LLM health check functionality.

This script tests the health check for both Ollama and OpenRouter providers
with various configurations to ensure proper error handling and messaging.
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from chibi.config import load_config
from chibi.llm.manager import LLMManager
from chibi.llm.ollama_provider import OllamaProvider
from chibi.llm.openrouter_provider import OpenRouterProvider

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def print_health_result(result):
    """Print a health check result in a formatted way."""
    print("\n" + "=" * 80)
    print(f"Provider: {result.provider_name}")
    print(f"Model: {result.model}")
    print(f"Status: {'HEALTHY ✓' if result.is_healthy else 'UNHEALTHY ✗'}")
    if result.response_time_ms:
        print(f"Response time: {result.response_time_ms:.0f}ms")

    if not result.is_healthy:
        print(f"\nError: {result.error_message}")
        if result.troubleshooting:
            print(f"\nTroubleshooting:")
            print(result.troubleshooting)

    print("=" * 80)


async def test_valid_config():
    """Test health check with valid configuration."""
    print("\n" + "🔍 " * 20)
    print("TEST 1: Valid Configuration (from config.yaml)")
    print("🔍 " * 20)

    try:
        config = load_config()

        # Create providers from config
        primary = OllamaProvider(
            base_url=config.llm.primary.base_url,
            model=config.llm.primary.model,
            timeout=config.llm.primary.timeout,
        )

        fallback = OpenRouterProvider(
            api_key=config.openrouter_api_key,
            base_url=config.llm.fallback.base_url,
            model=config.llm.fallback.model,
            timeout=config.llm.fallback.timeout,
        )

        manager = LLMManager(primary, fallback)

        # Run health checks
        results = await manager.health_check_all()

        for result in results:
            print_health_result(result)

        # Summary
        healthy_count = sum(1 for r in results if r.is_healthy)
        print(f"\nSummary: {healthy_count}/{len(results)} providers are healthy")

    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)


async def test_invalid_ollama():
    """Test health check with invalid Ollama configuration."""
    print("\n" + "🔍 " * 20)
    print("TEST 2: Invalid Ollama Configuration (wrong port)")
    print("🔍 " * 20)

    try:
        # Create provider with invalid base_url
        provider = OllamaProvider(
            base_url="http://localhost:99999",  # Invalid port
            model="llama3.2",
            timeout=5,
        )

        result = await provider.health_check()
        print_health_result(result)

    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)


async def test_invalid_model():
    """Test health check with invalid model name."""
    print("\n" + "🔍 " * 20)
    print("TEST 3: Invalid Model Name (nonexistent model)")
    print("🔍 " * 20)

    try:
        config = load_config()

        # Create provider with invalid model name
        provider = OllamaProvider(
            base_url=config.llm.primary.base_url,
            model="this-model-does-not-exist",
            timeout=5,
        )

        result = await provider.health_check()
        print_health_result(result)

    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)


async def test_invalid_api_key():
    """Test health check with invalid OpenRouter API key."""
    print("\n" + "🔍 " * 20)
    print("TEST 4: Invalid OpenRouter API Key")
    print("🔍 " * 20)

    try:
        # Create provider with invalid API key
        provider = OpenRouterProvider(
            api_key="invalid_key_12345",
            base_url="https://openrouter.ai/api/v1",
            model="meta-llama/llama-3-8b-instruct",
            timeout=10,
        )

        result = await provider.health_check()
        print_health_result(result)

    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)


async def test_missing_api_key():
    """Test health check with missing OpenRouter API key."""
    print("\n" + "🔍 " * 20)
    print("TEST 5: Missing OpenRouter API Key")
    print("🔍 " * 20)

    try:
        # Create provider with empty API key
        provider = OpenRouterProvider(
            api_key="",
            base_url="https://openrouter.ai/api/v1",
            model="meta-llama/llama-3-8b-instruct",
            timeout=10,
        )

        result = await provider.health_check()
        print_health_result(result)

    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)


async def main():
    """Run all health check tests."""
    print("\n" + "🤖 " * 20)
    print("LLM HEALTH CHECK TEST SUITE")
    print("🤖 " * 20)

    # Test 1: Valid configuration
    await test_valid_config()

    # Test 2: Invalid Ollama
    await test_invalid_ollama()

    # Test 3: Invalid model
    await test_invalid_model()

    # Test 4: Invalid API key (skip if no valid key in env)
    if os.getenv("OPENROUTER_API_KEY"):
        await test_invalid_api_key()
    else:
        print("\n⏭️  Skipping TEST 4: No OpenRouter API key in environment")

    # Test 5: Missing API key
    await test_missing_api_key()

    print("\n" + "✅ " * 20)
    print("ALL TESTS COMPLETED")
    print("✅ " * 20)


if __name__ == "__main__":
    asyncio.run(main())
