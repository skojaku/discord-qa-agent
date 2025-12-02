"""Embedding service with Ollama primary and OpenRouter fallback."""

import logging
from typing import List, Optional, TYPE_CHECKING

import httpx
from ollama import AsyncClient

if TYPE_CHECKING:
    from ..config import SimilarityConfig

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Service for generating embeddings using Ollama with OpenRouter fallback."""

    def __init__(self, config: "SimilarityConfig", api_key: str = ""):
        self.config = config
        self.api_key = api_key
        self._ollama_client = AsyncClient(host=config.ollama_base_url)
        self._http_client: Optional[httpx.AsyncClient] = None

    async def _get_http_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client for OpenRouter."""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(timeout=30.0)
        return self._http_client

    async def _get_ollama_embedding(self, text: str) -> Optional[List[float]]:
        """Generate embedding using Ollama."""
        try:
            response = await self._ollama_client.embeddings(
                model=self.config.embedding_model,
                prompt=text,
            )
            return response["embedding"]
        except Exception as e:
            logger.warning(f"Ollama embedding failed: {e}")
            return None

    async def _get_openrouter_embedding(self, text: str) -> Optional[List[float]]:
        """Generate embedding using OpenRouter API."""
        if not self.api_key:
            logger.warning("OpenRouter API key not configured for fallback embeddings")
            return None

        try:
            client = await self._get_http_client()
            response = await client.post(
                f"{self.config.fallback_base_url}/embeddings",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.config.fallback_model,
                    "input": text,
                },
            )
            response.raise_for_status()
            data = response.json()
            return data["data"][0]["embedding"]
        except Exception as e:
            logger.warning(f"OpenRouter embedding failed: {e}")
            return None

    async def get_embedding(self, text: str) -> Optional[List[float]]:
        """Generate embedding for a single text.

        Tries Ollama first, falls back to OpenRouter if configured.

        Args:
            text: The text to embed

        Returns:
            List of floats representing the embedding, or None on error
        """
        # Try Ollama first
        embedding = await self._get_ollama_embedding(text)
        if embedding is not None:
            return embedding

        # Fall back to OpenRouter if enabled
        if self.config.fallback_enabled:
            logger.info("Falling back to OpenRouter for embedding")
            embedding = await self._get_openrouter_embedding(text)
            if embedding is not None:
                return embedding

        logger.error("All embedding providers failed")
        return None

    async def is_available(self) -> bool:
        """Check if any embedding service is available."""
        # Check Ollama
        try:
            response = await self._ollama_client.embeddings(
                model=self.config.embedding_model,
                prompt="test",
            )
            if "embedding" in response:
                return True
        except Exception as e:
            logger.warning(f"Ollama embedding not available: {e}")

        # Check OpenRouter fallback
        if self.config.fallback_enabled and self.api_key:
            try:
                client = await self._get_http_client()
                response = await client.post(
                    f"{self.config.fallback_base_url}/embeddings",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.config.fallback_model,
                        "input": "test",
                    },
                )
                if response.status_code == 200:
                    return True
            except Exception as e:
                logger.warning(f"OpenRouter embedding not available: {e}")

        return False

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._http_client is not None:
            await self._http_client.aclose()
            self._http_client = None
