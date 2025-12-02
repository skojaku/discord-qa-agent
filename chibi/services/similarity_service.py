"""Similarity detection service for LLM Quiz anti-cheat."""

import logging
from dataclasses import dataclass
from typing import List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..config import SimilarityConfig
    from ..database.repositories.similarity_repository import (
        SimilarityRepository,
        SimilarQuestion,
    )
    from .embedding_service import EmbeddingService

logger = logging.getLogger(__name__)


@dataclass
class SimilarityCheckResult:
    """Result of a similarity check."""

    is_similar: bool
    highest_similarity: float
    similar_questions: List["SimilarQuestion"]
    error: Optional[str] = None


class SimilarityService:
    """Service for detecting similar questions to prevent cheating."""

    def __init__(
        self,
        config: "SimilarityConfig",
        embedding_service: "EmbeddingService",
        similarity_repo: "SimilarityRepository",
    ):
        self.config = config
        self.embedding_service = embedding_service
        self.similarity_repo = similarity_repo

    @property
    def enabled(self) -> bool:
        """Check if similarity detection is enabled."""
        return self.config.enabled

    async def check_similarity(
        self,
        question: str,
        module_id: str,
    ) -> SimilarityCheckResult:
        """Check if a question is too similar to existing questions in the module.

        Args:
            question: The question text to check
            module_id: The module to check against

        Returns:
            SimilarityCheckResult indicating if question should be rejected
        """
        if not self.enabled:
            return SimilarityCheckResult(
                is_similar=False,
                highest_similarity=0.0,
                similar_questions=[],
            )

        try:
            embedding = await self.embedding_service.get_embedding(question)

            if embedding is None:
                logger.warning("Failed to generate embedding, allowing question")
                return SimilarityCheckResult(
                    is_similar=False,
                    highest_similarity=0.0,
                    similar_questions=[],
                    error="Embedding service unavailable",
                )

            similar_questions = await self.similarity_repo.find_similar_in_module(
                embedding=embedding,
                module_id=module_id,
                top_k=self.config.top_k,
            )

            highest_similarity = 0.0
            if similar_questions:
                highest_similarity = max(q.similarity_score for q in similar_questions)

            is_similar = highest_similarity >= self.config.similarity_threshold

            if is_similar:
                logger.info(
                    f"Question rejected - similarity {highest_similarity:.2f} >= "
                    f"threshold {self.config.similarity_threshold}"
                )

            return SimilarityCheckResult(
                is_similar=is_similar,
                highest_similarity=highest_similarity,
                similar_questions=similar_questions,
            )

        except Exception as e:
            logger.error(f"Similarity check failed: {e}", exc_info=True)
            return SimilarityCheckResult(
                is_similar=False,
                highest_similarity=0.0,
                similar_questions=[],
                error=str(e),
            )

    async def add_question(
        self,
        question_id: int,
        question_text: str,
        module_id: str,
        user_id: int,
    ) -> bool:
        """Add a question to the similarity database.

        Args:
            question_id: The database ID of the question
            question_text: The question text
            module_id: The module ID
            user_id: The user who submitted the question

        Returns:
            True if successfully added, False otherwise
        """
        if not self.enabled:
            return True

        try:
            embedding = await self.embedding_service.get_embedding(question_text)

            if embedding is None:
                logger.warning(f"Failed to generate embedding for question {question_id}")
                return False

            await self.similarity_repo.add_question(
                question_id=question_id,
                question_text=question_text,
                embedding=embedding,
                module_id=module_id,
                user_id=user_id,
            )

            return True

        except Exception as e:
            logger.error(f"Failed to add question to similarity database: {e}")
            return False

    async def is_available(self) -> bool:
        """Check if the similarity service is fully available."""
        if not self.enabled:
            return True

        return await self.embedding_service.is_available()
