"""Content indexer service for RAG."""

import asyncio
import logging
from typing import TYPE_CHECKING, List, Optional

from .chunking import TextChunk, TextChunker

if TYPE_CHECKING:
    from ..content.course import Course, Module
    from ..database.repositories.rag_repository import RAGRepository
    from .embedding_service import EmbeddingService

logger = logging.getLogger(__name__)


class ContentIndexer:
    """Service for indexing course content into the RAG database.

    Handles chunking module content and generating embeddings
    for semantic search.
    """

    def __init__(
        self,
        embedding_service: "EmbeddingService",
        rag_repo: "RAGRepository",
        chunk_size: int = 500,
        chunk_overlap: int = 100,
        batch_size: int = 10,
    ):
        """Initialize the content indexer.

        Args:
            embedding_service: Service for generating embeddings
            rag_repo: Repository for storing chunks
            chunk_size: Target size for each chunk in characters
            chunk_overlap: Number of characters to overlap between chunks
            batch_size: Number of chunks to process in each batch
        """
        self.embedding_service = embedding_service
        self.rag_repo = rag_repo
        self.chunker = TextChunker(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
        self.batch_size = batch_size

    async def index_course(
        self,
        course: "Course",
        force_reindex: bool = False,
    ) -> dict:
        """Index all modules in a course.

        Args:
            course: The course to index
            force_reindex: If True, reindex even if already indexed

        Returns:
            Dict with indexing statistics
        """
        stats = {
            "modules_indexed": 0,
            "modules_skipped": 0,
            "total_chunks": 0,
            "errors": [],
        }

        for module in course.modules:
            try:
                result = await self.index_module(
                    module=module,
                    force_reindex=force_reindex,
                )
                if result["indexed"]:
                    stats["modules_indexed"] += 1
                    stats["total_chunks"] += result["chunks"]
                else:
                    stats["modules_skipped"] += 1
            except Exception as e:
                logger.error(f"Error indexing module {module.id}: {e}")
                stats["errors"].append(f"{module.id}: {str(e)}")

        logger.info(
            f"Course indexing complete: {stats['modules_indexed']} modules, "
            f"{stats['total_chunks']} chunks"
        )

        return stats

    async def index_module(
        self,
        module: "Module",
        force_reindex: bool = False,
    ) -> dict:
        """Index a single module.

        Args:
            module: The module to index
            force_reindex: If True, reindex even if already indexed

        Returns:
            Dict with indexing result
        """
        result = {
            "module_id": module.id,
            "indexed": False,
            "chunks": 0,
        }

        # Check if already indexed
        if not force_reindex:
            has_content = await self.rag_repo.has_source(module.id)
            if has_content:
                logger.debug(f"Module {module.id} already indexed, skipping")
                return result

        # Get content to index
        content = self._build_module_content(module)
        if not content.strip():
            logger.debug(f"Module {module.id} has no content to index")
            return result

        # Clear existing chunks for this module
        await self.rag_repo.delete_source(module.id)

        # Chunk the content
        chunks = self.chunker.chunk_text(
            text=content,
            source_id=module.id,
            source_name=module.name,
        )

        if not chunks:
            logger.debug(f"No chunks generated for module {module.id}")
            return result

        # Generate embeddings and store in batches
        total_indexed = 0
        for i in range(0, len(chunks), self.batch_size):
            batch = chunks[i : i + self.batch_size]
            indexed = await self._index_batch(batch)
            total_indexed += indexed

        result["indexed"] = True
        result["chunks"] = total_indexed

        logger.info(f"Indexed module {module.id}: {total_indexed} chunks")

        return result

    def _build_module_content(self, module: "Module") -> str:
        """Build the full content for a module.

        Combines module content with concept information.

        Args:
            module: The module to build content for

        Returns:
            Combined content string
        """
        parts = []

        # Add module description
        if module.description:
            parts.append(f"# {module.name}\n\n{module.description}")

        # Add module content (from URL)
        if module.content:
            parts.append(module.content)

        # Add concept information
        if module.concepts:
            concept_text = "\n\n## Key Concepts\n\n"
            for concept in module.concepts:
                concept_text += f"### {concept.name}\n"
                if concept.description:
                    concept_text += f"{concept.description}\n"
                if concept.quiz_focus:
                    concept_text += f"Focus: {concept.quiz_focus}\n"
                concept_text += "\n"
            parts.append(concept_text)

        return "\n\n".join(parts)

    async def _index_batch(self, chunks: List[TextChunk]) -> int:
        """Index a batch of chunks.

        Args:
            chunks: List of chunks to index

        Returns:
            Number of chunks successfully indexed
        """
        chunk_ids = []
        texts = []
        embeddings = []
        metadatas = []

        for chunk in chunks:
            # Generate embedding
            embedding = await self.embedding_service.get_embedding(chunk.text)
            if embedding is None:
                logger.warning(f"Failed to generate embedding for chunk {chunk.chunk_id}")
                continue

            chunk_ids.append(chunk.chunk_id)
            texts.append(chunk.text)
            embeddings.append(embedding)
            metadatas.append(
                {
                    "source_id": chunk.source_id,
                    "source_name": chunk.source_name,
                    "chunk_index": chunk.chunk_index,
                }
            )

            # Small delay to avoid overwhelming the embedding service
            await asyncio.sleep(0.05)

        if chunk_ids:
            await self.rag_repo.add_chunks_batch(
                chunk_ids=chunk_ids,
                texts=texts,
                embeddings=embeddings,
                metadatas=metadatas,
            )

        return len(chunk_ids)

    async def get_index_status(self, course: "Course") -> dict:
        """Get indexing status for a course.

        Args:
            course: The course to check

        Returns:
            Dict with status for each module
        """
        status = {
            "total_modules": len(course.modules),
            "indexed_modules": 0,
            "total_chunks": 0,
            "modules": {},
        }

        for module in course.modules:
            chunk_count = await self.rag_repo.get_chunk_count_for_source(module.id)
            status["modules"][module.id] = {
                "name": module.name,
                "chunks": chunk_count,
                "indexed": chunk_count > 0,
            }
            if chunk_count > 0:
                status["indexed_modules"] += 1
            status["total_chunks"] += chunk_count

        return status

    async def clear_index(self) -> None:
        """Clear all indexed content."""
        await self.rag_repo.clear_all()
        logger.info("Cleared all indexed content")
