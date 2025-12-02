"""ChromaDB repository for RAG (Retrieval-Augmented Generation)."""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, TYPE_CHECKING

import chromadb
from chromadb.config import Settings

if TYPE_CHECKING:
    from ...config import SimilarityConfig

logger = logging.getLogger(__name__)


@dataclass
class RetrievedChunk:
    """Represents a retrieved content chunk."""

    chunk_id: str
    text: str
    source_id: str  # Module ID
    source_name: str  # Module name
    chunk_index: int
    similarity_score: float

    def __str__(self) -> str:
        return f"[{self.source_name}] {self.text}"


class RAGRepository:
    """Repository for RAG operations using ChromaDB.

    Stores and retrieves course content chunks for semantic search.
    """

    COLLECTION_NAME = "course_content"

    def __init__(self, config: "SimilarityConfig"):
        self.config = config
        self._client: Optional[chromadb.PersistentClient] = None
        self._collection: Optional[chromadb.Collection] = None
        self._is_connected = False

    async def connect(self) -> None:
        """Initialize ChromaDB connection."""
        Path(self.config.chromadb_path).mkdir(parents=True, exist_ok=True)

        self._client = chromadb.PersistentClient(
            path=self.config.chromadb_path,
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=False,
            ),
        )

        self._collection = self._client.get_or_create_collection(
            name=self.COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )

        self._is_connected = True
        logger.info(
            f"RAG repository connected, collection has {self._collection.count()} chunks"
        )

    async def close(self) -> None:
        """Close ChromaDB connection."""
        self._is_connected = False

    @property
    def is_connected(self) -> bool:
        """Check if connected."""
        return self._is_connected

    @property
    def collection(self) -> chromadb.Collection:
        """Get the ChromaDB collection."""
        if self._collection is None:
            raise RuntimeError("RAGRepository not connected. Call connect() first.")
        return self._collection

    async def add_chunk(
        self,
        chunk_id: str,
        text: str,
        embedding: List[float],
        source_id: str,
        source_name: str,
        chunk_index: int,
    ) -> None:
        """Add a content chunk to the database.

        Args:
            chunk_id: Unique identifier for the chunk
            text: The chunk text
            embedding: The embedding vector
            source_id: The module/document ID
            source_name: Human-readable source name
            chunk_index: Position of chunk in source document
        """
        self.collection.add(
            ids=[chunk_id],
            embeddings=[embedding],
            documents=[text],
            metadatas=[
                {
                    "source_id": source_id,
                    "source_name": source_name,
                    "chunk_index": chunk_index,
                }
            ],
        )
        logger.debug(f"Added chunk {chunk_id} to RAG database")

    async def add_chunks_batch(
        self,
        chunk_ids: List[str],
        texts: List[str],
        embeddings: List[List[float]],
        metadatas: List[dict],
    ) -> None:
        """Add multiple chunks in a batch.

        Args:
            chunk_ids: List of unique identifiers
            texts: List of chunk texts
            embeddings: List of embedding vectors
            metadatas: List of metadata dicts
        """
        if not chunk_ids:
            return

        self.collection.add(
            ids=chunk_ids,
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas,
        )
        logger.debug(f"Added {len(chunk_ids)} chunks to RAG database")

    async def search(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        source_id: Optional[str] = None,
    ) -> List[RetrievedChunk]:
        """Search for similar content chunks.

        Args:
            query_embedding: The query embedding vector
            top_k: Maximum number of results
            source_id: Optional filter by source (module ID)

        Returns:
            List of RetrievedChunk objects, sorted by similarity (highest first)
        """
        where_filter = {"source_id": source_id} if source_id else None

        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=where_filter,
            include=["documents", "metadatas", "distances"],
        )

        retrieved_chunks = []

        if results["ids"] and results["ids"][0]:
            for i, chunk_id in enumerate(results["ids"][0]):
                # ChromaDB returns distance, convert to similarity for cosine
                distance = results["distances"][0][i]
                similarity = 1 - distance

                metadata = results["metadatas"][0][i]
                retrieved_chunks.append(
                    RetrievedChunk(
                        chunk_id=chunk_id,
                        text=results["documents"][0][i],
                        source_id=metadata.get("source_id", ""),
                        source_name=metadata.get("source_name", ""),
                        chunk_index=metadata.get("chunk_index", 0),
                        similarity_score=similarity,
                    )
                )

        return retrieved_chunks

    async def get_chunk_count(self) -> int:
        """Get total number of chunks in the database."""
        return self.collection.count()

    async def get_chunk_count_for_source(self, source_id: str) -> int:
        """Get number of chunks for a specific source."""
        results = self.collection.get(
            where={"source_id": source_id},
            include=[],
        )
        return len(results["ids"]) if results["ids"] else 0

    async def delete_source(self, source_id: str) -> None:
        """Delete all chunks from a source.

        Args:
            source_id: The source (module) ID to delete
        """
        try:
            # Get all chunk IDs for this source
            results = self.collection.get(
                where={"source_id": source_id},
                include=[],
            )
            if results["ids"]:
                self.collection.delete(ids=results["ids"])
                logger.info(
                    f"Deleted {len(results['ids'])} chunks for source {source_id}"
                )
        except Exception as e:
            logger.warning(f"Failed to delete chunks for source {source_id}: {e}")

    async def clear_all(self) -> None:
        """Clear all chunks from the database."""
        try:
            # Get all IDs and delete them
            all_data = self.collection.get(include=[])
            if all_data["ids"]:
                self.collection.delete(ids=all_data["ids"])
                logger.info(f"Cleared {len(all_data['ids'])} chunks from RAG database")
        except Exception as e:
            logger.warning(f"Failed to clear RAG database: {e}")

    async def has_source(self, source_id: str) -> bool:
        """Check if a source has been indexed.

        Args:
            source_id: The source (module) ID to check

        Returns:
            True if the source has chunks in the database
        """
        count = await self.get_chunk_count_for_source(source_id)
        return count > 0
