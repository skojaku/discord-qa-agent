"""Embedding service with flexible primary/fallback provider support."""

import logging
from typing import List, Optional, TYPE_CHECKING

import httpx
from ollama import AsyncClient

if TYPE_CHECKING:
    from ..config import SimilarityConfig

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Service for generating embeddings with auto-detected primary provider.

    Primary provider is determined by embedding_model format:
    - Contains "/" (e.g., "qwen/qwen3-embedding-4b") → OpenRouter
    - No "/" (e.g., "nomic-embed-text") → Ollama

    Falls back to the other provider if primary fails.
    """

    def __init__(self, config: "SimilarityConfig", api_key: str = ""):
        self.config = config
        self.api_key = api_key

        # Determine primary provider from model name
        self.use_openrouter_primary = "/" in config.embedding_model

        # Initialize Ollama client if needed
        if config.ollama_base_url and not self.use_openrouter_primary:
            self._ollama_client = AsyncClient(host=config.ollama_base_url)
        else:
            self._ollama_client = None

        self._http_client: Optional[httpx.AsyncClient] = None

        logger.info(
            f"EmbeddingService initialized with primary provider: "
            f"{'OpenRouter' if self.use_openrouter_primary else 'Ollama'} "
            f"(model: {config.embedding_model})"
        )

    async def _get_http_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client for OpenRouter."""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(timeout=30.0)
        return self._http_client

    async def _get_ollama_embedding(self, text: str, model: Optional[str] = None) -> Optional[List[float]]:
        """Generate embedding using Ollama.

        Args:
            text: Text to embed
            model: Optional model override (defaults to config.embedding_model or fallback_model)
        """
        if self._ollama_client is None:
            return None

        try:
            embedding_model = model or self.config.embedding_model
            response = await self._ollama_client.embeddings(
                model=embedding_model,
                prompt=text,
            )
            return response["embedding"]
        except Exception as e:
            logger.warning(f"Ollama embedding failed: {e}")
            return None

    async def _get_openrouter_embedding(self, text: str, model: Optional[str] = None) -> Optional[List[float]]:
        """Generate embedding using OpenRouter API.

        Args:
            text: Text to embed
            model: Optional model override (defaults to config.embedding_model or fallback_model)
        """
        if not self.api_key:
            logger.warning("OpenRouter API key not configured for embeddings")
            return None

        try:
            # Use primary model if OpenRouter is primary, otherwise use fallback model
            embedding_model = model or (
                self.config.embedding_model if self.use_openrouter_primary else self.config.fallback_model
            )

            client = await self._get_http_client()
            response = await client.post(
                f"{self.config.fallback_base_url}/embeddings",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": embedding_model,
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

        Tries primary provider first (auto-detected from model name),
        then falls back to alternate provider if configured.

        Args:
            text: The text to embed

        Returns:
            List of floats representing the embedding, or None on error
        """
        if self.use_openrouter_primary:
            # Primary: OpenRouter
            embedding = await self._get_openrouter_embedding(text)
            if embedding is not None:
                return embedding

            # Fallback: Ollama (if available)
            if self.config.fallback_enabled and self._ollama_client:
                logger.info("Falling back to Ollama for embedding")
                embedding = await self._get_ollama_embedding(text, model=self.config.fallback_model)
                if embedding is not None:
                    return embedding
        else:
            # Primary: Ollama
            embedding = await self._get_ollama_embedding(text)
            if embedding is not None:
                return embedding

            # Fallback: OpenRouter (if enabled)
            if self.config.fallback_enabled:
                logger.info("Falling back to OpenRouter for embedding")
                embedding = await self._get_openrouter_embedding(text)
                if embedding is not None:
                    return embedding

        logger.error("All embedding providers failed")
        return None

    async def is_available(self) -> bool:
        """Check if any embedding service is available."""
        if self.use_openrouter_primary:
            # Check OpenRouter first
            if self.api_key:
                try:
                    embedding = await self._get_openrouter_embedding("test")
                    if embedding:
                        return True
                except Exception as e:
                    logger.warning(f"OpenRouter embedding not available: {e}")

            # Check Ollama fallback
            if self.config.fallback_enabled and self._ollama_client:
                try:
                    embedding = await self._get_ollama_embedding("test", model=self.config.fallback_model)
                    if embedding:
                        return True
                except Exception as e:
                    logger.warning(f"Ollama embedding not available: {e}")
        else:
            # Check Ollama first
            if self._ollama_client:
                try:
                    embedding = await self._get_ollama_embedding("test")
                    if embedding:
                        return True
                except Exception as e:
                    logger.warning(f"Ollama embedding not available: {e}")

            # Check OpenRouter fallback
            if self.config.fallback_enabled and self.api_key:
                try:
                    embedding = await self._get_openrouter_embedding("test")
                    if embedding:
                        return True
                except Exception as e:
                    logger.warning(f"OpenRouter embedding not available: {e}")

        return False

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._http_client is not None:
            await self._http_client.aclose()
            self._http_client = None
