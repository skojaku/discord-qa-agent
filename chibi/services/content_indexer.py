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
            "modules_content_changed": 0,
            "total_chunks": 0,
            "errors": [],
            "reindexed_modules": [],  # List of module IDs that were reindexed
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
                    stats["reindexed_modules"].append(module.id)
                    if result.get("content_changed"):
                        stats["modules_content_changed"] += 1
                else:
                    stats["modules_skipped"] += 1
            except Exception as e:
                logger.error(f"Error indexing module {module.id}: {e}")
                stats["errors"].append(f"{module.id}: {str(e)}")

        if stats["modules_indexed"] > 0:
            logger.info(
                f"Course indexing complete: {stats['modules_indexed']} modules indexed "
                f"({stats['modules_content_changed']} with content changes), "
                f"{stats['total_chunks']} chunks"
            )
            if stats["reindexed_modules"]:
                logger.info(f"Reindexed modules: {', '.join(stats['reindexed_modules'])}")
        else:
            logger.info(
                f"Course indexing complete: All {stats['modules_skipped']} modules up to date"
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
            "content_changed": False,
        }

        # Check if content has changed (unless force_reindex is True)
        if not force_reindex:
            content_changed = await self._has_content_changed(module)
            if not content_changed:
                logger.debug(f"Module {module.id} content unchanged, skipping")
                return result
            else:
                logger.info(f"Module {module.id} content changed, reindexing")
                result["content_changed"] = True

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
            content_length = len(full_content)

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
                indexed = await self._index_batch(batch, content_length=content_length)
                total_indexed += indexed

            urls_indexed += 1
            logger.debug(f"Indexed {source_id}: {len(chunks)} chunks, {content_length} chars")

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

    async def _has_content_changed(self, module: "Module") -> bool:
        """Check if module content has changed since last indexing.

        Compares current content character counts with stored metadata.

        Args:
            module: The module to check

        Returns:
            True if content has changed or module not yet indexed
        """
        # Check each URL in the module
        for url_index, (url, content) in enumerate(module.contents.items()):
            source_id = f"{module.id}:url_{url_index}"

            # Build full content (same as during indexing)
            full_content = self._build_url_content(module, url, content)
            current_length = len(full_content)

            # Get stored content length from metadata
            stored_length = await self.rag_repo.get_source_content_length(source_id)

            # If no stored length (not indexed) or lengths differ, content has changed
            if stored_length is None:
                logger.debug(f"{source_id} not indexed yet")
                return True

            if current_length != stored_length:
                logger.info(
                    f"{source_id} content changed: {stored_length} -> {current_length} chars"
                )
                return True

        # All URLs have unchanged content
        return False

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

    async def _index_batch(self, chunks: List[TextChunk], content_length: int = 0) -> int:
        """Index a batch of chunks.

        Args:
            chunks: List of chunks to index
            content_length: Total character count of source content (stored in first chunk)

        Returns:
            Number of chunks successfully indexed
        """
        chunk_ids = []
        texts = []
        embeddings = []
        metadatas = []

        for idx, chunk in enumerate(chunks):
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

            # Build metadata - store content_length in first chunk for change detection
            metadata = {
                "source_id": chunk.source_id,
                "source_name": chunk.source_name,
                "chunk_index": chunk.chunk_index,
                "context": chunk.context or "",  # Store context in metadata
            }

            # Store content length in first chunk's metadata for change detection
            if chunk.chunk_index == 0 and content_length > 0:
                metadata["content_length"] = content_length

            metadatas.append(metadata)

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
