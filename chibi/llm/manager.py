"""LLM Manager with fallback logic."""

import logging
from typing import Optional

from .base import BaseLLMProvider, LLMResponse

logger = logging.getLogger(__name__)


class LLMManager:
    """Manages LLM providers with automatic fallback."""

    def __init__(
        self,
        primary_provider: BaseLLMProvider,
        fallback_provider: BaseLLMProvider,
        max_failures_before_skip: int = 3,
    ):
        self.primary = primary_provider
        self.fallback = fallback_provider
        self._primary_failures = 0
        self._max_failures = max_failures_before_skip

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
    ) -> Optional[LLMResponse]:
        """Generate a response, with automatic fallback.

        Tries the primary provider first. If it fails, falls back to the
        secondary provider. Tracks consecutive failures to temporarily
        skip a failing primary provider.

        Args:
            prompt: The user prompt
            system_prompt: Optional system prompt
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature

        Returns:
            LLMResponse if successful, None if both providers fail
        """
        # Try primary provider if not too many recent failures
        if self._primary_failures < self._max_failures:
            try:
                if await self.primary.is_available():
                    logger.debug(f"Using primary provider: {self.primary.name}")
                    response = await self.primary.generate(
                        prompt=prompt,
                        system_prompt=system_prompt,
                        max_tokens=max_tokens,
                        temperature=temperature,
                    )
                    self._primary_failures = 0  # Reset on success
                    return response
            except Exception as e:
                logger.warning(f"Primary provider ({self.primary.name}) failed: {e}")
                self._primary_failures += 1
        else:
            logger.info(
                f"Skipping primary provider due to {self._primary_failures} consecutive failures"
            )

        # Try fallback provider
        try:
            if await self.fallback.is_available():
                logger.info(f"Using fallback provider: {self.fallback.name}")
                response = await self.fallback.generate(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
                return response
            else:
                logger.error(f"Fallback provider ({self.fallback.name}) not available")
        except Exception as e:
            logger.error(f"Fallback provider ({self.fallback.name}) failed: {e}")

        # Both providers failed
        return None

    def reset_primary_failures(self) -> None:
        """Reset the primary failure counter.

        Call this periodically to retry the primary provider
        after it has been temporarily skipped.
        """
        self._primary_failures = 0
        logger.info("Primary provider failure counter reset")

    def get_error_message(self) -> str:
        """Get a user-friendly error message when both providers fail."""
        return (
            "Oops! Chibi's brain circuits are a bit fuzzy right now. "
            "Both my local and cloud thinking systems are taking a break. "
            "Please try again in a few moments! 🤖💤"
        )

    @property
    def primary_provider_name(self) -> str:
        """Get the primary provider name."""
        return self.primary.name

    @property
    def fallback_provider_name(self) -> str:
        """Get the fallback provider name."""
        return self.fallback.name
