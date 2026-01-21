"""Ollama LLM provider implementation."""

import logging
import time
from typing import Optional

import ollama
from ollama import AsyncClient

from .base import BaseLLMProvider, LLMResponse, HealthCheckResult

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

    async def health_check(self) -> HealthCheckResult:
        """Perform a health check by attempting a simple generation."""
        start_time = time.time()

        try:
            # First check if Ollama is reachable
            models = await self._client.list()
            model_names = [m.model for m in models.models]

            # Check if our configured model is available
            if self.model not in model_names:
                return HealthCheckResult(
                    provider_name=self.name,
                    is_healthy=False,
                    model=self.model,
                    error_message=f"Model '{self.model}' not found in Ollama",
                    troubleshooting=(
                        f"Available models: {', '.join(model_names)}\n\n"
                        f"To fix this issue:\n"
                        f"1. Pull the model: ollama pull {self.model}\n"
                        f"2. Or update config.yaml to use one of the available models\n"
                        f"3. Check Ollama is running: ollama list"
                    ),
                    response_time_ms=(time.time() - start_time) * 1000
                )

            # Try a simple generation to verify the model works
            response = await self.generate(
                prompt="Say 'OK' if you can read this.",
                max_tokens=10,
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
                        "The model is loaded but returned no content.\n\n"
                        "To fix this issue:\n"
                        "1. Try restarting Ollama: ollama stop && ollama start\n"
                        "2. Try pulling the model again: ollama pull {self.model}\n"
                        "3. Check Ollama logs for errors"
                    ),
                    response_time_ms=response_time
                )

            return HealthCheckResult(
                provider_name=self.name,
                is_healthy=True,
                model=self.model,
                response_time_ms=response_time
            )

        except ConnectionError as e:
            return HealthCheckResult(
                provider_name=self.name,
                is_healthy=False,
                model=self.model,
                error_message=f"Cannot connect to Ollama: {str(e)}",
                troubleshooting=(
                    f"Failed to connect to Ollama at {self.base_url}\n\n"
                    f"To fix this issue:\n"
                    f"1. Check if Ollama is running: ollama list\n"
                    f"2. Start Ollama if not running: ollama serve\n"
                    f"3. Verify the base_url in config.yaml matches your Ollama installation\n"
                    f"4. On macOS: Ollama runs on http://localhost:11434\n"
                    f"5. On Linux with systemd: sudo systemctl status ollama"
                ),
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
                    f"To fix this issue:\n"
                    f"1. Check Ollama logs: ollama logs\n"
                    f"2. Verify Ollama version is up to date: ollama --version\n"
                    f"3. Try restarting Ollama: ollama stop && ollama serve\n"
                    f"4. Check system resources (disk space, memory)"
                ),
                response_time_ms=(time.time() - start_time) * 1000
            )
