#!/usr/bin/env python3
"""Quick verification that content change detection works."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from chibi.config import load_config
from chibi.content.course import load_course
from chibi.content.loader import ContentLoader
from chibi.database.repositories import RAGRepository
from chibi.services import ContentIndexer, EmbeddingService


async def main():
    """Verify content change detection for m00."""
    print("Verifying content change detection...\n")

    config = load_config()
    course = load_course()

    # Load content
    content_loader = ContentLoader()
    await content_loader.load_all_content(course)

    # Get m00
    m00 = next(m for m in course.modules if m.id == "m00")

    # Initialize services
    rag_repo = RAGRepository(config.similarity)
    await rag_repo.connect()

    embedding_service = EmbeddingService(config.similarity, api_key=config.openrouter_api_key)

    indexer = ContentIndexer(
        embedding_service=embedding_service,
        rag_repo=rag_repo,
        chunk_size=500,
        chunk_overlap=100,
        use_contextual_retrieval=False,
    )

    # Check current vs stored content
    print("Module m00 status:")
    print("-" * 60)

    for url_index, (url, content) in enumerate(m00.contents.items()):
        source_id = f"m00:url_{url_index}"
        full_content = indexer._build_url_content(m00, url, content)
        current_length = len(full_content)
        stored_length = await rag_repo.get_source_content_length(source_id)

        if stored_length is None:
            print(f"{source_id}: NOT INDEXED (current: {current_length} chars)")
        elif current_length == stored_length:
            print(f"{source_id}: ✅ UP TO DATE ({current_length} chars)")
        else:
            diff = current_length - stored_length
            print(f"{source_id}: ⚠️  CHANGED ({stored_length} -> {current_length} chars, {diff:+d})")

    # Test indexing (should skip if unchanged)
    print("\n" + "=" * 60)
    print("Testing index_module() with automatic change detection...")
    print("=" * 60 + "\n")

    result = await indexer.index_module(module=m00, force_reindex=False)

    if result["indexed"]:
        print(f"✅ Module reindexed: {result['chunks']} chunks")
        if result.get("content_changed"):
            print("   Reason: Content changed")
    else:
        print("✅ Module skipped: Content unchanged")

    await rag_repo.close()
    print("\n✅ Verification complete!")


if __name__ == "__main__":
    asyncio.run(main())
