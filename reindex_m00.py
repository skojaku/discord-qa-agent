#!/usr/bin/env python3
"""Script to reindex module m00 after content changes."""

import asyncio
import logging
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from chibi.config import load_config
from chibi.content.course import load_course
from chibi.content.loader import ContentLoader
from chibi.database.repositories import RAGRepository
from chibi.services import ContentIndexer, EmbeddingService, ContextualChunkingService, ContextualChunkConfig
from chibi.llm.manager import LLMManager
from chibi.llm.ollama_provider import OllamaProvider
from chibi.llm.openrouter_provider import OpenRouterProvider

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def main():
    """Reindex module m00 with new content."""
    logger.info("Starting m00 reindexing process...")

    # Load configuration
    config = load_config()
    logger.info("Configuration loaded")

    # Load course
    course = load_course()
    logger.info(f"Course loaded: {course.name}")

    # Find module m00
    m00 = None
    for module in course.modules:
        if module.id == "m00":
            m00 = module
            break

    if not m00:
        logger.error("Module m00 not found in course!")
        return

    logger.info(f"Found module: {m00.name}")

    # Load content for m00
    content_loader = ContentLoader()
    await content_loader.load_module_content(m00)
    logger.info(f"Content loaded for m00: {len(m00.contents)} URLs")

    # Check content size
    for url, content in m00.contents.items():
        logger.info(f"  {url}: {len(content)} characters")

    # Initialize RAG repository
    rag_repo = RAGRepository(config.similarity)
    await rag_repo.connect()
    logger.info("RAG repository connected")

    # Check current index status for m00
    for i in range(10):
        source_id = f"m00:url_{i}"
        count = await rag_repo.get_chunk_count_for_source(source_id)
        if count > 0:
            logger.info(f"  Current chunks in {source_id}: {count}")

    # Initialize embedding service
    embedding_service = EmbeddingService(
        config.similarity,
        api_key=config.openrouter_api_key,
    )
    logger.info("Embedding service initialized")

    # Initialize contextual chunking if enabled
    contextual_service = None
    if config.contextual_retrieval.enabled:
        logger.info("Contextual chunking is enabled")

        # Initialize LLM for context generation
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
            reasoning=config.llm.fallback.reasoning,
            provider=config.llm.fallback.provider_preferences,
            transforms=config.llm.fallback.transforms,
        )
        llm_manager = LLMManager(primary, fallback)

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
        logger.info("Contextual chunking service initialized")

    # Initialize content indexer
    content_indexer = ContentIndexer(
        embedding_service=embedding_service,
        rag_repo=rag_repo,
        chunk_size=500,
        chunk_overlap=100,
        contextual_chunking_service=contextual_service,
        use_contextual_retrieval=config.contextual_retrieval.enabled,
    )
    logger.info("Content indexer initialized")

    # Force reindex m00
    logger.info("Reindexing m00 (force_reindex=True)...")
    result = await content_indexer.index_module(
        module=m00,
        force_reindex=True,  # Force reindexing even if already indexed
    )

    logger.info(f"Reindexing complete!")
    logger.info(f"  Module ID: {result['module_id']}")
    logger.info(f"  Indexed: {result['indexed']}")
    logger.info(f"  URLs indexed: {result['urls_indexed']}")
    logger.info(f"  Total chunks: {result['chunks']}")

    # Verify new index status
    logger.info("\nNew index status for m00:")
    for i in range(10):
        source_id = f"m00:url_{i}"
        count = await rag_repo.get_chunk_count_for_source(source_id)
        if count > 0:
            logger.info(f"  {source_id}: {count} chunks")

    # Close connections
    await rag_repo.close()
    logger.info("\nReindexing completed successfully!")


if __name__ == "__main__":
    asyncio.run(main())
