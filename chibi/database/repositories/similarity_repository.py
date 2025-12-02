"""ChromaDB repository for question similarity detection."""

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

    def __init__(self, config: "SimilarityConfig"):
        self.config = config
        self._client: Optional[chromadb.PersistentClient] = None
        self._collection: Optional[chromadb.Collection] = None

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

        logger.info(
            f"ChromaDB connected, collection has {self._collection.count()} questions"
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
