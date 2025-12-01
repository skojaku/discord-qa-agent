"""Ollama LLM provider implementation."""

import logging
from typing import Optional

import ollama
from ollama import AsyncClient

from .base import BaseLLMProvider, LLMResponse

logger = logging.getLogger(__name__)


class OllamaProvider(BaseLLMProvider):
    """Ollama LLM provider for local inference."""

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "llama3.2",
        timeout: int = 60,
    ):
        self.base_url = base_url
        self.model = model
        self.timeout = timeout
        self._client = AsyncClient(host=base_url)

    @property
    def name(self) -> str:
        return "ollama"

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
    ) -> LLMResponse:
        """Generate a response using Ollama."""
        messages = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        messages.append({"role": "user", "content": prompt})

        try:
            response = await self._client.chat(
                model=self.model,
                messages=messages,
                options={
                    "num_predict": max_tokens,
                    "temperature": temperature,
                },
            )

            content = response["message"]["content"]
            tokens_used = response.get("eval_count", 0) + response.get(
                "prompt_eval_count", 0
            )

            return LLMResponse(
                content=content,
                model=self.model,
                provider=self.name,
                tokens_used=tokens_used,
            )

        except Exception as e:
            logger.error(f"Ollama generation failed: {e}")
            raise

    async def is_available(self) -> bool:
        """Check if Ollama is available by listing models."""
        try:
            await self._client.list()
            return True
        except Exception as e:
            logger.warning(f"Ollama not available: {e}")
            return False
