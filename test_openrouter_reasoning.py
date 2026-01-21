#!/usr/bin/env python3
"""Quick test for OpenRouter reasoning parameter support."""

import asyncio
import os
import sys
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, os.path.dirname(__file__))

from chibi.llm.openrouter_provider import OpenRouterProvider

load_dotenv()


async def test_reasoning():
    """Test OpenRouter with and without reasoning parameters."""

    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        print("❌ OPENROUTER_API_KEY not set")
        return

    print("="*80)
    print("Testing OpenRouter Reasoning Parameter Support")
    print("="*80)

    # Test 1: Without reasoning (should return empty content)
    print("\n[TEST 1] gpt-oss-20b WITHOUT reasoning parameter")
    print("-"*80)

    provider_no_reasoning = OpenRouterProvider(
        api_key=api_key,
        model="openai/gpt-oss-20b",
        timeout=30,
    )

    try:
        response = await provider_no_reasoning.generate(
            prompt="Say 'hello world' and nothing else.",
            max_tokens=20,
            temperature=0.3,
        )

        print(f"✓ API call succeeded")
        print(f"Content: '{response.content}'")
        print(f"Content length: {len(response.content)} chars")
        print(f"Tokens used: {response.tokens_used}")

        if not response.content or len(response.content) < 5:
            print("❌ FAIL: Empty or minimal content (as expected without reasoning)")
        else:
            print("✓ PASS: Got content")

    except Exception as e:
        print(f"❌ Error: {e}")

    # Test 2: With reasoning (should return actual content)
    print("\n[TEST 2] gpt-oss-20b WITH reasoning parameter (enabled=true)")
    print("-"*80)

    provider_with_reasoning = OpenRouterProvider(
        api_key=api_key,
        model="openai/gpt-oss-20b",
        timeout=30,
        reasoning={"enabled": True},
    )

    try:
        response = await provider_with_reasoning.generate(
            prompt="Say 'hello world' and nothing else.",
            max_tokens=100,
            temperature=0.3,
        )

        print(f"✓ API call succeeded")
        print(f"Content: '{response.content}'")
        print(f"Content length: {len(response.content)} chars")
        print(f"Tokens used: {response.tokens_used}")

        if response.content and len(response.content) >= 5:
            print("✓ PASS: Got actual content with reasoning enabled!")
        else:
            print("❌ FAIL: Still getting empty content")

    except Exception as e:
        print(f"❌ Error: {e}")

    # Test 3: With reasoning effort=low (for contextual chunking)
    print("\n[TEST 3] gpt-oss-20b WITH reasoning (effort='low')")
    print("-"*80)

    provider_low_reasoning = OpenRouterProvider(
        api_key=api_key,
        model="openai/gpt-oss-20b",
        timeout=30,
        reasoning={"effort": "low"},
    )

    try:
        response = await provider_low_reasoning.generate(
            prompt="Briefly summarize what this is about: 'Neural networks use backpropagation to learn.'",
            max_tokens=100,
            temperature=0.3,
        )

        print(f"✓ API call succeeded")
        print(f"Content: '{response.content}'")
        print(f"Content length: {len(response.content)} chars")
        print(f"Tokens used: {response.tokens_used}")

        if response.content and len(response.content) >= 10:
            print("✓ PASS: Got summary with low-effort reasoning!")
        else:
            print("❌ FAIL: Empty content even with effort='low'")

    except Exception as e:
        print(f"❌ Error: {e}")

    # Test 4: Per-call override
    print("\n[TEST 4] Per-call reasoning override")
    print("-"*80)

    provider_default = OpenRouterProvider(
        api_key=api_key,
        model="openai/gpt-oss-20b",
        timeout=30,
    )

    try:
        response = await provider_default.generate(
            prompt="Count to 3.",
            max_tokens=50,
            temperature=0.3,
            reasoning={"effort": "minimal"},  # Per-call override
        )

        print(f"✓ API call succeeded")
        print(f"Content: '{response.content}'")
        print(f"Content length: {len(response.content)} chars")
        print(f"Tokens used: {response.tokens_used}")

        if response.content:
            print("✓ PASS: Per-call reasoning override works!")
        else:
            print("❌ FAIL: Per-call override didn't work")

    except Exception as e:
        print(f"❌ Error: {e}")

    print("\n" + "="*80)
    print("TEST COMPLETE")
    print("="*80)


if __name__ == "__main__":
    asyncio.run(test_reasoning())
