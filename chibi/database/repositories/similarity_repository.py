"""ChromaDB repository for question similarity detection."""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, TYPE_CHECKING

import chromadb
from chromadb.config import Settings

if TYPE_CHECKING:
    from ...config import SimilarityConfig
    from ...services.embedding_service import EmbeddingService

logger = logging.getLogger(__name__)


@dataclass
class SimilarQuestion:
    """Represents a similar question found in the database."""

    question_id: str
    question_text: str
    module_id: str
    user_id: int
    similarity_score: float


class SimilarityRepository:
    """Repository for question similarity operations using ChromaDB."""

    COLLECTION_NAME = "llm_quiz_questions"

    def __init__(self, config: "SimilarityConfig", embedding_service: "EmbeddingService"):
        self.config = config
        self.embedding_service = embedding_service
        self._client: Optional[chromadb.PersistentClient] = None
        self._collection: Optional[chromadb.Collection] = None
        self._embedding_dimension: Optional[int] = None

    async def connect(self) -> None:
        """Initialize ChromaDB connection with dynamic dimension detection."""
        Path(self.config.chromadb_path).mkdir(parents=True, exist_ok=True)

        self._client = chromadb.PersistentClient(
            path=self.config.chromadb_path,
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=False,
            ),
        )

        # Detect embedding dimension by generating a test embedding
        logger.info("Detecting embedding dimensions from current model...")
        test_embedding = await self.embedding_service.get_embedding("test")

        if test_embedding is None:
            raise RuntimeError(
                "Failed to generate test embedding. Cannot determine embedding dimensions. "
                "Please check your embedding service configuration."
            )

        self._embedding_dimension = len(test_embedding)
        logger.info(f"Detected embedding dimension: {self._embedding_dimension}")

        # Check if collection exists
        existing_collections = [col.name for col in self._client.list_collections()]
        collection_exists = self.COLLECTION_NAME in existing_collections

        if collection_exists:
            # Get existing collection to check dimensions
            temp_collection = self._client.get_collection(name=self.COLLECTION_NAME)

            # Try to detect existing dimension from collection metadata or by checking first item
            existing_dimension = None
            if temp_collection.count() > 0:
                # Get one item to check dimension
                sample = temp_collection.get(limit=1, include=["embeddings"])
                if sample.get("embeddings") is not None and len(sample["embeddings"]) > 0:
                    existing_dimension = len(sample["embeddings"][0])

            if existing_dimension and existing_dimension != self._embedding_dimension:
                logger.warning(
                    f"Dimension mismatch detected! "
                    f"Existing collection: {existing_dimension}D, Current model: {self._embedding_dimension}D"
                )
                logger.warning(
                    f"Deleting existing collection '{self.COLLECTION_NAME}' and recreating with new dimensions. "
                    f"Similarity history will be lost."
                )
                self._client.delete_collection(name=self.COLLECTION_NAME)
                collection_exists = False

        if not collection_exists:
            logger.info(f"Creating new collection with {self._embedding_dimension} dimensions")

        # Create or get collection
        self._collection = self._client.get_or_create_collection(
            name=self.COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )

        logger.info(
            f"ChromaDB connected (dimension: {self._embedding_dimension}), "
            f"collection has {self._collection.count()} questions"
        )

    async def close(self) -> None:
        """Close ChromaDB connection."""
        pass

    @property
    def collection(self) -> chromadb.Collection:
        """Get the ChromaDB collection."""
        if self._collection is None:
            raise RuntimeError(
                "SimilarityRepository not connected. Call connect() first."
            )
        return self._collection

    async def add_question(
        self,
        question_id: int,
        question_text: str,
        embedding: List[float],
        module_id: str,
        user_id: int,
    ) -> None:
        """Add a question embedding to the database.

        Args:
            question_id: The SQLite database ID for this question
            question_text: The original question text
            embedding: The embedding vector
            module_id: The module this question belongs to
            user_id: The user who submitted this question
        """
        doc_id = f"q_{question_id}"

        self.collection.add(
            ids=[doc_id],
            embeddings=[embedding],
            documents=[question_text],
            metadatas=[
                {
                    "module_id": module_id,
                    "user_id": user_id,
                    "question_id": question_id,
                }
            ],
        )
        logger.debug(f"Added question {doc_id} to similarity database")

    async def find_similar_in_module(
        self,
        embedding: List[float],
        module_id: str,
        top_k: int = 5,
    ) -> List[SimilarQuestion]:
        """Find similar questions within the same module.

        Args:
            embedding: The query embedding
            module_id: Only search within this module
            top_k: Maximum number of results

        Returns:
            List of similar questions, sorted by similarity (highest first)
        """
        results = self.collection.query(
            query_embeddings=[embedding],
            n_results=top_k,
            where={"module_id": module_id},
            include=["documents", "metadatas", "distances"],
        )

        similar_questions = []

        if results["ids"] and results["ids"][0]:
            for i, doc_id in enumerate(results["ids"][0]):
                # ChromaDB returns distance, convert to similarity for cosine
                # cosine distance = 1 - cosine similarity
                distance = results["distances"][0][i]
                similarity = 1 - distance

                similar_questions.append(
                    SimilarQuestion(
                        question_id=doc_id,
                        question_text=results["documents"][0][i],
                        module_id=results["metadatas"][0][i]["module_id"],
                        user_id=results["metadatas"][0][i]["user_id"],
                        similarity_score=similarity,
                    )
                )

        return similar_questions

    async def get_question_count_for_module(self, module_id: str) -> int:
        """Get the number of questions stored for a module."""
        results = self.collection.get(
            where={"module_id": module_id},
            include=[],
        )
        return len(results["ids"]) if results["ids"] else 0

    async def delete_question(self, question_id: int) -> None:
        """Delete a question from the similarity database."""
        doc_id = f"q_{question_id}"
        try:
            self.collection.delete(ids=[doc_id])
            logger.debug(f"Deleted question {doc_id} from similarity database")
        except Exception as e:
            logger.warning(f"Failed to delete question {doc_id}: {e}")

    async def clear_module(self, module_id: str) -> int:
        """Clear all questions for a specific module.

        Args:
            module_id: The module to clear

        Returns:
            Number of questions deleted
        """
        try:
            # Get all question IDs for this module
            results = self.collection.get(
                where={"module_id": module_id},
                include=[],
            )
            if results["ids"]:
                count = len(results["ids"])
                self.collection.delete(ids=results["ids"])
                logger.info(f"Cleared {count} questions from module {module_id}")
                return count
            return 0
        except Exception as e:
            logger.error(f"Failed to clear module {module_id}: {e}")
            raise

    async def clear_all(self) -> int:
        """Clear all questions from the similarity database.

        Returns:
            Number of questions deleted
        """
        try:
            count = self.collection.count()
            if count > 0:
                # Get all IDs and delete them
                results = self.collection.get(include=[])
                if results["ids"]:
                    self.collection.delete(ids=results["ids"])
            logger.info(f"Cleared all {count} questions from similarity database")
            return count
        except Exception as e:
            logger.error(f"Failed to clear similarity database: {e}")
            raise
