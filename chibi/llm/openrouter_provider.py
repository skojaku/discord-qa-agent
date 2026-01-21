"""OpenRouter LLM provider implementation."""

import logging
import time
from typing import Any, Dict, List, Optional

from openai import AsyncOpenAI, AuthenticationError, APIConnectionError, APIError

from .base import BaseLLMProvider, LLMResponse, HealthCheckResult

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

    async def health_check(self) -> HealthCheckResult:
        """Perform a health check by attempting a simple generation."""
        start_time = time.time()

        # Check if we have an API key
        if not self.api_key:
            return HealthCheckResult(
                provider_name=self.name,
                is_healthy=False,
                model=self.model,
                error_message="OpenRouter API key not configured",
                troubleshooting=(
                    "OpenRouter API key is missing or empty.\n\n"
                    "To fix this issue:\n"
                    "1. Get an API key from https://openrouter.ai/keys\n"
                    "2. Add it to your .env file: OPENROUTER_API_KEY=your_key_here\n"
                    "3. Or set it in config.yaml under llm.openrouter.api_key\n"
                    "4. Restart the bot after updating the configuration"
                ),
                response_time_ms=(time.time() - start_time) * 1000
            )

        try:
            # Try a simple generation to verify the API key and model work
            # If reasoning is configured, we need more tokens (reasoning budget + response)
            max_tokens_for_test = 10
            if self.reasoning and self.reasoning.get('max_tokens'):
                # Add buffer beyond reasoning budget for actual response
                max_tokens_for_test = self.reasoning['max_tokens'] + 100

            response = await self.generate(
                prompt="Say 'OK' if you can read this.",
                max_tokens=max_tokens_for_test,
                temperature=0.0
            )

            response_time = (time.time() - start_time) * 1000

            if not response.content:
                return HealthCheckResult(
                    provider_name=self.name,
                    is_healthy=False,
                    model=self.model,
                    error_message="Model returned empty response",
                    troubleshooting=(
                        f"OpenRouter accepted the request but the model '{self.model}' returned no content.\n\n"
                        "To fix this issue:\n"
                        "1. Check if this is a reasoning model that needs special parameters\n"
                        "2. Verify the model name is correct: https://openrouter.ai/models\n"
                        "3. Try a different model like 'meta-llama/llama-3-8b-instruct'\n"
                        "4. Check your OpenRouter credits: https://openrouter.ai/credits\n"
                        "5. If using reasoning models (gpt-oss-20b), ensure reasoning parameters are set"
                    ),
                    response_time_ms=response_time
                )

            return HealthCheckResult(
                provider_name=self.name,
                is_healthy=True,
                model=self.model,
                response_time_ms=response_time
            )

        except AuthenticationError as e:
            return HealthCheckResult(
                provider_name=self.name,
                is_healthy=False,
                model=self.model,
                error_message=f"Authentication failed: {str(e)}",
                troubleshooting=(
                    "OpenRouter rejected the API key.\n\n"
                    "To fix this issue:\n"
                    "1. Verify your API key at https://openrouter.ai/keys\n"
                    "2. Check if the key in .env matches the one on OpenRouter\n"
                    "3. Regenerate the API key if it was revoked\n"
                    "4. Make sure there are no extra spaces or quotes around the key\n"
                    "5. Restart the bot after updating the API key"
                ),
                response_time_ms=(time.time() - start_time) * 1000
            )

        except APIConnectionError as e:
            return HealthCheckResult(
                provider_name=self.name,
                is_healthy=False,
                model=self.model,
                error_message=f"Cannot connect to OpenRouter: {str(e)}",
                troubleshooting=(
                    f"Failed to connect to OpenRouter at {self.base_url}\n\n"
                    "To fix this issue:\n"
                    "1. Check your internet connection\n"
                    "2. Verify the base_url in config.yaml: https://openrouter.ai/api/v1\n"
                    "3. Check if OpenRouter is down: https://status.openrouter.ai\n"
                    "4. Try again in a few moments\n"
                    "5. Check firewall/proxy settings that might block the connection"
                ),
                response_time_ms=(time.time() - start_time) * 1000
            )

        except APIError as e:
            error_msg = str(e)
            # Check for common error patterns
            if "insufficient credits" in error_msg.lower() or "balance" in error_msg.lower():
                troubleshooting = (
                    "You don't have enough OpenRouter credits.\n\n"
                    "To fix this issue:\n"
                    "1. Add credits at https://openrouter.ai/credits\n"
                    "2. Check your current balance\n"
                    "3. Set up auto-reload if available\n"
                    "4. Consider using free models if available"
                )
            elif "model" in error_msg.lower() and "not found" in error_msg.lower():
                troubleshooting = (
                    f"Model '{self.model}' not found on OpenRouter.\n\n"
                    "To fix this issue:\n"
                    "1. Check available models: https://openrouter.ai/models\n"
                    "2. Update config.yaml with a valid model name\n"
                    "3. Try 'meta-llama/llama-3-8b-instruct' as a reliable default\n"
                    "4. Make sure the model name format is correct (provider/model)"
                )
            else:
                troubleshooting = (
                    f"OpenRouter API error: {error_msg}\n\n"
                    "To fix this issue:\n"
                    "1. Check OpenRouter status: https://status.openrouter.ai\n"
                    "2. Review the error message above for specific guidance\n"
                    "3. Check your account status at https://openrouter.ai\n"
                    "4. Try a different model if the current one is unavailable"
                )

            return HealthCheckResult(
                provider_name=self.name,
                is_healthy=False,
                model=self.model,
                error_message=f"API Error: {error_msg}",
                troubleshooting=troubleshooting,
                response_time_ms=(time.time() - start_time) * 1000
            )

        except Exception as e:
            return HealthCheckResult(
                provider_name=self.name,
                is_healthy=False,
                model=self.model,
                error_message=f"Health check failed: {str(e)}",
                troubleshooting=(
                    f"An unexpected error occurred: {type(e).__name__}\n\n"
                    "To fix this issue:\n"
                    "1. Check the error message above for clues\n"
                    "2. Verify your config.yaml settings\n"
                    "3. Check OpenRouter status: https://status.openrouter.ai\n"
                    "4. Try restarting the bot\n"
                    "5. If the issue persists, report it with the error details"
                ),
                response_time_ms=(time.time() - start_time) * 1000
            )
