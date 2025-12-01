"""OpenRouter LLM provider implementation."""

import logging
from typing import Optional

from openai import AsyncOpenAI

from .base import BaseLLMProvider, LLMResponse

logger = logging.getLogger(__name__)


class OpenRouterProvider(BaseLLMProvider):
    """OpenRouter LLM provider for cloud inference."""

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://openrouter.ai/api/v1",
        model: str = "meta-llama/llama-3.2-3b-instruct",
        timeout: int = 90,
    ):
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.timeout = timeout
        self._client = AsyncOpenAI(
            base_url=base_url,
            api_key=api_key,
            timeout=timeout,
        )

    @property
    def name(self) -> str:
        return "openrouter"

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
    ) -> LLMResponse:
        """Generate a response using OpenRouter."""
        messages = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        messages.append({"role": "user", "content": prompt})

        try:
            response = await self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )

            content = response.choices[0].message.content or ""
            tokens_used = response.usage.total_tokens if response.usage else 0

            return LLMResponse(
                content=content,
                model=self.model,
                provider=self.name,
                tokens_used=tokens_used,
            )

        except Exception as e:
            logger.error(f"OpenRouter generation failed: {e}")
            raise

    async def is_available(self) -> bool:
        """Check if OpenRouter is available.

        OpenRouter doesn't have a dedicated health endpoint,
        so we assume it's available if we have an API key.
        Actual availability is determined by request success.
        """
        return bool(self.api_key)
