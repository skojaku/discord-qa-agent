"""Content indexer service for RAG."""

import asyncio
import logging
from typing import TYPE_CHECKING, List, Optional

from .chunking import TextChunk, TextChunker

if TYPE_CHECKING:
    from ..content.course import Course, Module
    from ..database.repositories.rag_repository import RAGRepository
    from .contextual_chunking_service import ContextualChunkingService
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
        contextual_chunking_service: Optional["ContextualChunkingService"] = None,
        use_contextual_retrieval: bool = False,
    ):
        """Initialize the content indexer.

        Args:
            embedding_service: Service for generating embeddings
            rag_repo: Repository for storing chunks
            chunk_size: Target size for each chunk in characters
            chunk_overlap: Number of characters to overlap between chunks
            batch_size: Number of chunks to process in each batch
            contextual_chunking_service: Optional service for contextual chunking
            use_contextual_retrieval: Whether to use contextual retrieval
        """
        self.embedding_service = embedding_service
        self.rag_repo = rag_repo
        self.chunker = TextChunker(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
        self.batch_size = batch_size
        self.contextual_service = contextual_chunking_service
        self.use_contextual_retrieval = use_contextual_retrieval

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

        Each URL in the module is indexed as a separate source for
        finer-grained retrieval.

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
            "urls_indexed": 0,
        }

        # Check if already indexed (any URL source exists)
        if not force_reindex:
            has_content = await self._has_module_sources(module.id)
            if has_content:
                logger.debug(f"Module {module.id} already indexed, skipping")
                return result

        # Clear existing chunks for all URLs of this module
        await self._delete_module_sources(module.id)

        # Index each URL as a separate source
        total_indexed = 0
        urls_indexed = 0

        for url_index, (url, content) in enumerate(module.contents.items()):
            if not content.strip():
                logger.debug(f"No content for URL {url_index} in module {module.id}")
                continue

            source_id = f"{module.id}:url_{url_index}"
            source_name = f"{module.name} (Source {url_index + 1})"

            # Build content for this URL
            full_content = self._build_url_content(module, url, content)

            # Chunk the content
            chunks = self.chunker.chunk_text(
                text=full_content,
                source_id=source_id,
                source_name=source_name,
            )

            if not chunks:
                logger.debug(f"No chunks generated for {source_id}")
                continue

            # Add contextual information if enabled
            if self.use_contextual_retrieval and self.contextual_service:
                logger.info(
                    f"Generating context for {len(chunks)} chunks in {source_id}"
                )
                chunks = await self.contextual_service.contextualize_chunks(
                    chunks=chunks,
                    document_text=full_content,
                    document_title=source_name,
                )

            # Generate embeddings and store in batches
            for i in range(0, len(chunks), self.batch_size):
                batch = chunks[i : i + self.batch_size]
                indexed = await self._index_batch(batch)
                total_indexed += indexed

            urls_indexed += 1
            logger.debug(f"Indexed {source_id}: {len(chunks)} chunks")

        if urls_indexed > 0:
            result["indexed"] = True
            result["chunks"] = total_indexed
            result["urls_indexed"] = urls_indexed
            logger.info(
                f"Indexed module {module.id}: {urls_indexed} URLs, {total_indexed} chunks"
            )
        else:
            logger.debug(f"Module {module.id} has no content to index")

        return result

    async def _has_module_sources(self, module_id: str) -> bool:
        """Check if any URL sources exist for a module.

        Args:
            module_id: The module ID

        Returns:
            True if any sources exist for this module
        """
        # Check for url_0 as a proxy for whether the module is indexed
        return await self.rag_repo.has_source(f"{module_id}:url_0")

    async def _delete_module_sources(self, module_id: str) -> None:
        """Delete all URL sources for a module.

        Args:
            module_id: The module ID
        """
        # Delete sources for url_0 through url_9 (should cover most cases)
        for i in range(10):
            source_id = f"{module_id}:url_{i}"
            await self.rag_repo.delete_source(source_id)

    def _build_url_content(self, module: "Module", url: str, content: str) -> str:
        """Build the full content for a single URL source.

        Combines the URL content with module metadata for context.

        Args:
            module: The module this content belongs to
            url: The source URL
            content: The raw content from the URL

        Returns:
            Combined content string with context
        """
        parts = []

        # Add module header for context
        if module.description:
            parts.append(f"# {module.name}\n\n{module.description}")

        # Add the URL content
        if content:
            parts.append(content)

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
            # Use contextualized text for embedding if contextual retrieval is enabled
            text_for_embedding = (
                chunk.contextualized_text
                if self.use_contextual_retrieval
                else chunk.text
            )

            # Generate embedding
            embedding = await self.embedding_service.get_embedding(text_for_embedding)
            if embedding is None:
                logger.warning(f"Failed to generate embedding for chunk {chunk.chunk_id}")
                continue

            chunk_ids.append(chunk.chunk_id)
            texts.append(chunk.text)  # Store original text for display
            embeddings.append(embedding)
            metadatas.append(
                {
                    "source_id": chunk.source_id,
                    "source_name": chunk.source_name,
                    "chunk_index": chunk.chunk_index,
                    "context": chunk.context or "",  # Store context in metadata
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
            # Count chunks across all URL sources for this module
            chunk_count = 0
            urls_indexed = 0
            for i in range(10):  # Check url_0 through url_9
                source_id = f"{module.id}:url_{i}"
                count = await self.rag_repo.get_chunk_count_for_source(source_id)
                if count > 0:
                    chunk_count += count
                    urls_indexed += 1

            status["modules"][module.id] = {
                "name": module.name,
                "chunks": chunk_count,
                "urls_indexed": urls_indexed,
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
