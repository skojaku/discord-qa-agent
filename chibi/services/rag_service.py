"""RAG (Retrieval-Augmented Generation) service."""

import logging
from dataclasses import dataclass
from typing import List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..database.repositories.rag_repository import RAGRepository, RetrievedChunk
    from .embedding_service import EmbeddingService

logger = logging.getLogger(__name__)


@dataclass
class RAGResult:
    """Result of a RAG query."""

    context: str  # Combined context from retrieved chunks
    chunks: List["RetrievedChunk"]  # Individual retrieved chunks
    query: str  # Original query
    total_chunks: int  # Number of chunks retrieved


class RAGService:
    """Service for Retrieval-Augmented Generation.

    Handles semantic search over indexed course content to provide
    relevant context for answering user questions.
    """

    def __init__(
        self,
        embedding_service: "EmbeddingService",
        rag_repo: "RAGRepository",
        top_k: int = 5,
        min_similarity: float = 0.3,
        max_context_length: int = 4000,
    ):
        """Initialize the RAG service.

        Args:
            embedding_service: Service for generating embeddings
            rag_repo: Repository for storing/retrieving chunks
            top_k: Maximum number of chunks to retrieve
            min_similarity: Minimum similarity threshold for inclusion
            max_context_length: Maximum total context length in characters
        """
        self.embedding_service = embedding_service
        self.rag_repo = rag_repo
        self.top_k = top_k
        self.min_similarity = min_similarity
        self.max_context_length = max_context_length

    async def retrieve(
        self,
        query: str,
        source_id: Optional[str] = None,
        top_k: Optional[int] = None,
        exclude_chunk_ids: Optional[set] = None,
    ) -> RAGResult:
        """Retrieve relevant content chunks for a query.

        Args:
            query: The user's question or search query
            source_id: Optional filter to a specific source (module)
            top_k: Override default number of results
            exclude_chunk_ids: Optional set of chunk IDs to exclude (already retrieved)

        Returns:
            RAGResult with combined context and individual chunks
        """
        if top_k is None:
            top_k = self.top_k

        # Get query embedding
        query_embedding = await self.embedding_service.get_embedding(query)
        if query_embedding is None:
            logger.warning("Failed to generate query embedding")
            return RAGResult(
                context="",
                chunks=[],
                query=query,
                total_chunks=0,
            )

        # Search for similar chunks
        chunks = await self.rag_repo.search(
            query_embedding=query_embedding,
            top_k=top_k,
            source_id=source_id,
            exclude_chunk_ids=exclude_chunk_ids,
        )

        # Filter by minimum similarity
        filtered_chunks = [
            c for c in chunks if c.similarity_score >= self.min_similarity
        ]

        if not filtered_chunks:
            logger.debug(f"No chunks found above similarity threshold for: {query[:50]}")
            return RAGResult(
                context="",
                chunks=[],
                query=query,
                total_chunks=0,
            )

        # Build combined context, respecting max length
        context = self._build_context(filtered_chunks)

        logger.info(
            f"RAG retrieved {len(filtered_chunks)} chunks for query: {query[:50]}..."
        )

        return RAGResult(
            context=context,
            chunks=filtered_chunks,
            query=query,
            total_chunks=len(filtered_chunks),
        )

    def _build_context(self, chunks: List["RetrievedChunk"]) -> str:
        """Build combined context from chunks.

        Args:
            chunks: List of retrieved chunks, sorted by relevance

        Returns:
            Combined context string, truncated to max length
        """
        context_parts = []
        current_length = 0

        # Group chunks by source for better organization
        chunks_by_source = {}
        for chunk in chunks:
            source = chunk.source_name
            if source not in chunks_by_source:
                chunks_by_source[source] = []
            chunks_by_source[source].append(chunk)

        for source_name, source_chunks in chunks_by_source.items():
            # Sort chunks by chunk_index within each source
            source_chunks.sort(key=lambda c: c.chunk_index)

            source_text = f"\n--- From {source_name} ---\n"
            source_length = len(source_text)

            for chunk in source_chunks:
                chunk_text = chunk.text.strip()
                chunk_length = len(chunk_text) + 2  # +2 for newlines

                if current_length + source_length + chunk_length > self.max_context_length:
                    # Would exceed limit, stop adding
                    break

                source_text += chunk_text + "\n\n"
                current_length += chunk_length

            context_parts.append(source_text)

            if current_length >= self.max_context_length:
                break

        return "".join(context_parts).strip()

    async def retrieve_for_concepts(
        self,
        concepts: List[str],
        top_k_per_concept: int = 2,
    ) -> RAGResult:
        """Retrieve content related to multiple concepts.

        Useful for building context around specific learning topics.

        Args:
            concepts: List of concept names to search for
            top_k_per_concept: Number of chunks to retrieve per concept

        Returns:
            Combined RAGResult from all concept searches
        """
        all_chunks = []
        seen_chunk_ids = set()

        for concept in concepts:
            result = await self.retrieve(
                query=concept,
                top_k=top_k_per_concept,
            )

            for chunk in result.chunks:
                if chunk.chunk_id not in seen_chunk_ids:
                    all_chunks.append(chunk)
                    seen_chunk_ids.add(chunk.chunk_id)

        # Sort by similarity and limit
        all_chunks.sort(key=lambda c: c.similarity_score, reverse=True)
        limited_chunks = all_chunks[: self.top_k * 2]  # Allow more for multi-concept

        context = self._build_context(limited_chunks)

        return RAGResult(
            context=context,
            chunks=limited_chunks,
            query=", ".join(concepts),
            total_chunks=len(limited_chunks),
        )

    async def is_ready(self) -> bool:
        """Check if the RAG service is ready for queries.

        Returns:
            True if embedding service is available and repo is connected
        """
        if not self.rag_repo.is_connected:
            return False

        # Check if we have any content indexed
        chunk_count = await self.rag_repo.get_chunk_count()
        if chunk_count == 0:
            logger.warning("RAG repository is empty - no content indexed")
            return False

        # Check if embedding service is available
        is_available = await self.embedding_service.is_available()
        if not is_available:
            logger.warning("Embedding service is not available")
            return False

        return True
