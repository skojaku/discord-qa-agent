"""OpenRouter LLM provider implementation."""

import logging
from typing import Any, Dict, List, Optional

from openai import AsyncOpenAI

from .base import BaseLLMProvider, LLMResponse

logger = logging.getLogger(__name__)


class OpenRouterProvider(BaseLLMProvider):
    """OpenRouter LLM provider for cloud inference.

    Supports OpenRouter-specific features:
    - Reasoning parameters (effort, max_tokens, exclude)
    - Provider preferences (order, require_parameters, data_collection, allow_fallbacks)
    - Transforms (middle-out for context management)
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://openrouter.ai/api/v1",
        model: str = "meta-llama/llama-3.2-3b-instruct",
        timeout: int = 90,
        reasoning: Optional[Dict[str, Any]] = None,
        provider: Optional[Dict[str, Any]] = None,
        transforms: Optional[List[str]] = None,
    ):
        """Initialize OpenRouter provider.

        Args:
            api_key: OpenRouter API key
            base_url: OpenRouter API base URL
            model: Model name (e.g., "meta-llama/llama-3.2-3b-instruct")
            timeout: Request timeout in seconds
            reasoning: Optional reasoning config:
                - effort: "xhigh", "high", "medium", "low", "minimal", "none"
                - max_tokens: int (mutually exclusive with effort)
                - exclude: bool (use reasoning but don't return it)
                - enabled: bool (enable with defaults)
            provider: Optional provider preferences:
                - order: List[str] (provider IDs in priority order)
                - allow_fallbacks: bool (allow backup providers)
                - require_parameters: bool (only use providers supporting all params)
                - data_collection: "allow" or "deny"
                - quantizations: List[str] (filter by quantization)
            transforms: Optional transforms (e.g., ["middle-out"])
        """
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.timeout = timeout
        self.reasoning = reasoning
        self.provider = provider
        self.transforms = transforms
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
        reasoning: Optional[Dict[str, Any]] = None,
        provider: Optional[Dict[str, Any]] = None,
        transforms: Optional[List[str]] = None,
    ) -> LLMResponse:
        """Generate a response using OpenRouter.

        Args:
            prompt: The user prompt
            system_prompt: Optional system prompt
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature
            reasoning: Optional reasoning override (overrides init value)
            provider: Optional provider preferences override (overrides init value)
            transforms: Optional transforms override (overrides init value)

        Returns:
            LLMResponse with content and metadata
        """
        messages = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        messages.append({"role": "user", "content": prompt})

        # Build extra_body with OpenRouter-specific parameters
        extra_body = {}

        # Use per-call overrides if provided, otherwise use instance defaults
        final_reasoning = reasoning if reasoning is not None else self.reasoning
        final_provider = provider if provider is not None else self.provider
        final_transforms = transforms if transforms is not None else self.transforms

        logger.debug(
            f"OpenRouter parameters - reasoning={final_reasoning}, "
            f"provider={final_provider}, transforms={final_transforms}"
        )

        if final_reasoning:
            extra_body["reasoning"] = final_reasoning
            logger.info(f"Passing reasoning config to API: {final_reasoning}")

        if final_provider:
            extra_body["provider"] = final_provider
            logger.debug(f"Passing provider preferences to API: {final_provider}")

        if final_transforms:
            extra_body["transforms"] = final_transforms
            logger.debug(f"Passing transforms to API: {final_transforms}")

        try:
            # Pass extra_body only if we have OpenRouter-specific params
            kwargs = {
                "model": self.model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
            }

            if extra_body:
                kwargs["extra_body"] = extra_body
                logger.info(f"Calling OpenRouter API with extra_body: {extra_body}")
            else:
                logger.warning(
                    f"Calling OpenRouter API WITHOUT extra_body "
                    f"(reasoning={final_reasoning}, provider={final_provider}, transforms={final_transforms})"
                )

            response = await self._client.chat.completions.create(**kwargs)

            content = response.choices[0].message.content or ""
            tokens_used = response.usage.total_tokens if response.usage else 0

            # Log reasoning token usage if available
            if hasattr(response.usage, 'reasoning_tokens') and response.usage.reasoning_tokens:
                logger.debug(
                    f"Reasoning tokens used: {response.usage.reasoning_tokens} "
                    f"(out of {tokens_used} total)"
                )

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
