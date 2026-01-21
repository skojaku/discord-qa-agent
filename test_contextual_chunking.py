#!/usr/bin/env python3
"""Test script for diagnosing contextual chunking issues.

This script will:
1. Initialize the bot services
2. Force reindex a single module with contextual chunking
3. Display detailed error messages from the LLM providers
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from chibi.config import load_config
from dotenv import load_dotenv

# Set up detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

# Focus on relevant loggers
logging.getLogger('chibi.services.contextual_chunking_service').setLevel(logging.DEBUG)
logging.getLogger('chibi.llm.manager').setLevel(logging.DEBUG)
logging.getLogger('chibi.llm.openrouter_provider').setLevel(logging.DEBUG)
logging.getLogger('chibi.llm.ollama_provider').setLevel(logging.DEBUG)

# Suppress noisy loggers
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('httpcore').setLevel(logging.WARNING)


async def test_contextual_chunking():
    """Test contextual chunking on a single module."""
    print("\n" + "="*80)
    print("CONTEXTUAL CHUNKING DIAGNOSTIC TEST")
    print("="*80 + "\n")

    # Load environment
    load_dotenv()

    # Load config
    config = load_config("config.yaml")

    print(f"Contextual Retrieval Enabled: {config.contextual_retrieval.enabled}")
    print(f"Contextual Model: {config.contextual_retrieval.model}")
    print(f"Contextual Base URL: {config.contextual_retrieval.base_url}")
    print(f"Batch Size: {config.contextual_retrieval.batch_size}")
    print(f"Primary LLM: {config.llm.primary.provider}/{config.llm.primary.model}")
    print(f"Fallback LLM: {config.llm.fallback.provider}/{config.llm.fallback.model}")

    # Check API keys
    print("\nAPI Keys:")
    print(f"  OPENROUTER_API_KEY: {'✓ Set' if os.getenv('OPENROUTER_API_KEY') else '✗ Not set'}")
    print(f"  DISCORD_TOKEN: {'✓ Set' if os.getenv('DISCORD_TOKEN') else '✗ Not set'}")

    print("\n" + "-"*80)
    print("Initializing services (this may take a moment)...")
    print("-"*80 + "\n")

    # Initialize bot (but don't start Discord connection)
    # We'll manually call the init methods we need
    from chibi.content.course_loader import load_course
    from chibi.database.connection import Database
    from chibi.database.repositories.rag_repository import RAGRepository
    from chibi.services.embedding_service import EmbeddingService
    from chibi.services.contextual_chunking_service import ContextualChunkingService, ContextualChunkConfig
    from chibi.services.content_indexer import ContentIndexer
    from chibi.llm.manager import LLMManager
    from chibi.llm.ollama_provider import OllamaProvider
    from chibi.llm.openrouter_provider import OpenRouterProvider

    # Load course
    course = load_course("course.yaml")
    print(f"Loaded course: {course.title}")
    print(f"Modules: {', '.join(m.id for m in course.modules)}")

    # Initialize database and RAG
    db = Database("data/chibi.db")
    await db.connect()
    rag_repo = RAGRepository()

    # Initialize embedding service
    embedding_service = EmbeddingService(
        fallback_model=config.similarity.fallback_model,
        fallback_base_url=config.similarity.fallback_base_url,
        openrouter_api_key=os.getenv("OPENROUTER_API_KEY", ""),
    )

    # Initialize LLM manager for contextual chunking
    context_model = config.contextual_retrieval.model
    print(f"\nInitializing contextual LLM: {context_model}")

    if context_model.startswith("openrouter/"):
        model_name = context_model[11:]
        context_primary = OpenRouterProvider(
            api_key=os.getenv("OPENROUTER_API_KEY", ""),
            base_url=config.contextual_retrieval.base_url,
            model=model_name,
            timeout=90,
            reasoning=config.contextual_retrieval.reasoning,
            provider=config.contextual_retrieval.provider,
            transforms=config.contextual_retrieval.transforms,
        )
        print(f"  Reasoning config: {config.contextual_retrieval.reasoning}")
        print(f"  Provider config: {config.contextual_retrieval.provider}")
        print(f"  Transforms: {config.contextual_retrieval.transforms}")
        context_fallback = OllamaProvider(
            base_url=config.llm.primary.base_url,
            model=config.llm.primary.model,
            timeout=config.llm.primary.timeout,
        )
    else:
        print(f"ERROR: Unexpected model format: {context_model}")
        return

    llm_manager = LLMManager(context_primary, context_fallback)

    # Test LLM availability
    print("\nTesting LLM provider availability...")
    primary_available = await context_primary.is_available()
    fallback_available = await context_fallback.is_available()
    print(f"  Primary (OpenRouter): {'✓ Available' if primary_available else '✗ Not available'}")
    print(f"  Fallback (Ollama): {'✓ Available' if fallback_available else '✗ Not available'}")

    if not primary_available and not fallback_available:
        print("\n❌ ERROR: Both LLM providers are unavailable!")
        print("   - Check that Ollama is running: curl http://localhost:11434/api/tags")
        print("   - Check OpenRouter API key is valid")
        return

    # Initialize contextual chunking service
    contextual_config = ContextualChunkConfig(
        enabled=True,
        max_context_tokens=config.contextual_retrieval.max_context_tokens,
        batch_size=config.contextual_retrieval.batch_size,
        batch_delay_seconds=config.contextual_retrieval.batch_delay_seconds,
        temperature=config.contextual_retrieval.temperature,
    )

    contextual_service = ContextualChunkingService(
        llm_manager=llm_manager,
        config=contextual_config,
    )

    # Initialize content indexer
    content_indexer = ContentIndexer(
        embedding_service=embedding_service,
        rag_repo=rag_repo,
        contextual_chunking_service=contextual_service,
        use_contextual_retrieval=True,
    )

    # Select first module for testing
    test_module = course.modules[0]
    print(f"\n" + "="*80)
    print(f"Testing contextual chunking on module: {test_module.id} ({test_module.name})")
    print("="*80 + "\n")

    # Force reindex this module
    try:
        result = await content_indexer.index_module(
            module=test_module,
            force_reindex=True,
        )

        print("\n" + "="*80)
        print("INDEXING RESULT")
        print("="*80)
        print(f"Module: {result['module_id']}")
        print(f"Indexed: {result['indexed']}")
        print(f"Total chunks: {result['chunks']}")
        print(f"URLs indexed: {result['urls_indexed']}")

        # Show contextual service stats
        stats = contextual_service.get_stats()
        print(f"\nContextual Chunking Stats:")
        print(f"  Total chunks processed: {stats['total_chunks']}")
        print(f"  Successful contexts: {stats['successful_contexts']}")
        print(f"  Failed contexts: {stats['failed_contexts']}")
        if stats['total_chunks'] > 0:
            success_rate = stats['successful_contexts'] / stats['total_chunks'] * 100
            print(f"  Success rate: {success_rate:.1f}%")

        if stats['successful_contexts'] == 0:
            print("\n❌ NO CONTEXTS GENERATED - Check the error messages above")
        elif stats['successful_contexts'] < stats['total_chunks'] * 0.5:
            print("\n⚠️  LOW SUCCESS RATE - Check the warning messages above")
        else:
            print("\n✓ Contextual chunking working well!")

    except Exception as e:
        print(f"\n❌ ERROR during indexing: {e}")
        import traceback
        traceback.print_exc()

    finally:
        await db.close()

    print("\n" + "="*80)
    print("TEST COMPLETE")
    print("="*80)


if __name__ == "__main__":
    asyncio.run(test_contextual_chunking())
