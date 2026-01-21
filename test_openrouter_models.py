#!/usr/bin/env python3
"""Test OpenRouter model accessibility."""

import asyncio
import os
import sys
from dotenv import load_dotenv
from openai import AsyncOpenAI

load_dotenv()

async def test_model(model_name: str):
    """Test if a model is accessible via OpenRouter."""
    api_key = os.getenv("OPENROUTER_API_KEY")

    if not api_key:
        print("❌ OPENROUTER_API_KEY not set in .env")
        return False

    client = AsyncOpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
        timeout=30,
    )

    print(f"\nTesting model: {model_name}")
    print("-" * 60)

    try:
        response = await client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "user", "content": "Say 'test successful' and nothing else."}
            ],
            max_tokens=10,
            temperature=0.3,
        )

        content = response.choices[0].message.content or ""
        tokens = response.usage.total_tokens if response.usage else 0

        print(f"✓ Model works!")
        print(f"  Response: {content}")
        print(f"  Tokens used: {tokens}")
        return True

    except Exception as e:
        print(f"✗ Model failed: {type(e).__name__}")
        print(f"  Error: {str(e)[:200]}")
        return False


async def main():
    """Test all models from config."""

    print("=" * 60)
    print("OpenRouter Model Accessibility Test")
    print("=" * 60)

    # Models from your config
    models_to_test = [
        "openai/gpt-oss-120b",      # fallback.model (line 21)
        "openai/gpt-oss-20b",       # contextual after stripping prefix (line 101)
        "meta-llama/llama-3-8b-instruct",  # quiz_model after stripping
    ]

    # Suggested alternatives (known working models)
    suggested_models = [
        "openai/gpt-4o-mini",
        "anthropic/claude-3.5-haiku",
        "google/gemini-2.0-flash-001",
        "meta-llama/llama-3.3-70b-instruct",
    ]

    print("\nTesting models from your config.yaml:")
    results = {}
    for model in models_to_test:
        results[model] = await test_model(model)
        await asyncio.sleep(1)  # Rate limiting

    print("\n" + "=" * 60)
    print("Testing suggested alternatives:")
    print("=" * 60)
    for model in suggested_models:
        results[model] = await test_model(model)
        await asyncio.sleep(1)

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    print("\nCurrent config models:")
    for model in models_to_test:
        status = "✓" if results.get(model) else "✗"
        print(f"  {status} {model}")

    print("\nSuggested alternatives:")
    for model in suggested_models:
        status = "✓" if results.get(model) else "✗"
        print(f"  {status} {model}")

    working_models = [m for m, works in results.items() if works]
    if working_models:
        print(f"\n💡 Recommendation: Use one of these working models:")
        for model in working_models[:3]:
            print(f"   - {model}")
    else:
        print("\n❌ No models worked. Check your OPENROUTER_API_KEY")


if __name__ == "__main__":
    asyncio.run(main())
