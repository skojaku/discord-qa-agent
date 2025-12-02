#!/usr/bin/env python3
"""Migration script to add existing LLM quiz questions to ChromaDB."""

import asyncio
import logging
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import os
from dotenv import load_dotenv

from chibi.config import load_config
from chibi.database.connection import Database
from chibi.database.repositories import SimilarityRepository
from chibi.services import EmbeddingService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def migrate():
    """Migrate existing questions to ChromaDB."""
    logger.info("Starting migration of existing questions to ChromaDB...")

    # Load environment variables for API key
    load_dotenv(project_root / ".env")

    config = load_config(str(project_root / "config.yaml"))
    api_key = os.getenv("OPENROUTER_API_KEY", "")

    # Connect to SQLite
    database = Database(config.database.path)
    await database.connect()
    logger.info(f"Connected to database: {config.database.path}")

    # Connect to ChromaDB
    similarity_repo = SimilarityRepository(config.similarity)
    await similarity_repo.connect()
    logger.info(f"Connected to ChromaDB: {config.similarity.chromadb_path}")

    # Initialize embedding service
    embedding_service = EmbeddingService(config.similarity, api_key=api_key)

    # Check if embedding service is available
    if not await embedding_service.is_available():
        logger.error(
            "Embedding service not available. "
            "Is Ollama running with the nomic-embed-text model?"
        )
        logger.error(
            "Try running: ollama pull nomic-embed-text"
        )
        await database.close()
        return

    logger.info("Embedding service is available")

    # Get all existing questions
    conn = database.connection
    cursor = await conn.execute(
        "SELECT id, question, module_id, user_id FROM llm_quiz_attempts"
    )
    rows = await cursor.fetchall()

    total = len(rows)
    logger.info(f"Found {total} questions to migrate")

    if total == 0:
        logger.info("No questions to migrate")
        await database.close()
        return

    migrated = 0
    failed = 0
    skipped = 0

    for row in rows:
        question_id = row["id"]
        question_text = row["question"]
        module_id = row["module_id"]
        user_id = row["user_id"]

        # Check if already migrated
        doc_id = f"q_{question_id}"
        try:
            existing = similarity_repo.collection.get(ids=[doc_id])
            if existing["ids"]:
                skipped += 1
                continue
        except Exception:
            pass

        # Generate embedding
        embedding = await embedding_service.get_embedding(question_text)

        if embedding is None:
            logger.warning(f"Failed to generate embedding for question {question_id}")
            failed += 1
            continue

        # Add to ChromaDB
        try:
            await similarity_repo.add_question(
                question_id=question_id,
                question_text=question_text,
                embedding=embedding,
                module_id=module_id,
                user_id=user_id,
            )
            migrated += 1

            if migrated % 10 == 0:
                logger.info(f"Progress: {migrated}/{total} questions migrated...")

        except Exception as e:
            logger.error(f"Failed to add question {question_id}: {e}")
            failed += 1

    logger.info(
        f"Migration complete: {migrated} migrated, {skipped} skipped, {failed} failed"
    )

    await database.close()
    logger.info("Database connection closed")


if __name__ == "__main__":
    asyncio.run(migrate())
