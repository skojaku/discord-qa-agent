#!/usr/bin/env python3
"""Test script to verify content change detection works correctly."""

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
from chibi.services import ContentIndexer, EmbeddingService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def main():
    """Test content change detection."""
    logger.info("Testing content change detection...")

    # Load configuration
    config = load_config()

    # Load course
    course = load_course()
    logger.info(f"Course loaded: {course.name}")

    # Load content for all modules
    content_loader = ContentLoader()
    await content_loader.load_all_content(course)
    logger.info("Content loaded for all modules")

    # Initialize RAG repository
    rag_repo = RAGRepository(config.similarity)
    await rag_repo.connect()
    logger.info("RAG repository connected")

    # Initialize embedding service
    embedding_service = EmbeddingService(
        config.similarity,
        api_key=config.openrouter_api_key,
    )

    # Initialize content indexer
    content_indexer = ContentIndexer(
        embedding_service=embedding_service,
        rag_repo=rag_repo,
        chunk_size=500,
        chunk_overlap=100,
        use_contextual_retrieval=False,  # Disable for faster testing
    )
    logger.info("Content indexer initialized")

    # Test: Check each module
    logger.info("\n" + "="*80)
    logger.info("Checking each module for content changes...")
    logger.info("="*80)

    for module in course.modules:
        logger.info(f"\nModule: {module.id} - {module.name}")

        # Check content for each URL
        for url_index, (url, content) in enumerate(module.contents.items()):
            source_id = f"{module.id}:url_{url_index}"

            # Build full content
            full_content = content_indexer._build_url_content(module, url, content)
            current_length = len(full_content)

            # Get stored length
            stored_length = await rag_repo.get_source_content_length(source_id)

            if stored_length is None:
                logger.info(f"  {source_id}: NOT INDEXED (current: {current_length} chars)")
            elif current_length == stored_length:
                logger.info(f"  {source_id}: UP TO DATE ({current_length} chars)")
            else:
                logger.warning(
                    f"  {source_id}: CONTENT CHANGED "
                    f"({stored_length} -> {current_length} chars, "
                    f"diff: {current_length - stored_length:+d})"
                )

    # Test: Run indexing with automatic change detection
    logger.info("\n" + "="*80)
    logger.info("Running index_course with automatic change detection...")
    logger.info("="*80 + "\n")

    stats = await content_indexer.index_course(
        course=course,
        force_reindex=False,  # Use automatic change detection
    )

    logger.info("\n" + "="*80)
    logger.info("Indexing Statistics:")
    logger.info("="*80)
    logger.info(f"Modules indexed: {stats['modules_indexed']}")
    logger.info(f"Modules skipped: {stats['modules_skipped']}")
    logger.info(f"Modules with content changes: {stats['modules_content_changed']}")
    logger.info(f"Total chunks: {stats['total_chunks']}")
    if stats['reindexed_modules']:
        logger.info(f"Reindexed modules: {', '.join(stats['reindexed_modules'])}")
    if stats['errors']:
        logger.error(f"Errors: {stats['errors']}")

    # Close connections
    await rag_repo.close()
    logger.info("\nTest completed successfully!")


if __name__ == "__main__":
    asyncio.run(main())
