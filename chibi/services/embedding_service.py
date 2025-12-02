"""Embedding service using Ollama for vector generation."""

import logging
from typing import List, Optional, TYPE_CHECKING

from ollama import AsyncClient

if TYPE_CHECKING:
    from ..config import SimilarityConfig

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Service for generating embeddings using Ollama."""

    def __init__(self, config: "SimilarityConfig"):
        self.config = config
        self._client = AsyncClient(host=config.ollama_base_url)
        self.model = config.embedding_model

    async def get_embedding(self, text: str) -> Optional[List[float]]:
        """Generate embedding for a single text.

        Args:
            text: The text to embed

        Returns:
            List of floats representing the embedding, or None on error
        """
        try:
            response = await self._client.embeddings(
                model=self.model,
                prompt=text,
            )
            return response["embedding"]
        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            return None

    async def is_available(self) -> bool:
        """Check if the embedding service is available."""
        try:
            response = await self._client.embeddings(
                model=self.model,
                prompt="test",
            )
            return "embedding" in response
        except Exception as e:
            logger.warning(f"Embedding service not available: {e}")
            return False
