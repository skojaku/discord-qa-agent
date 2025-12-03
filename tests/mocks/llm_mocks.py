"""Mock LLM providers for testing without real API calls."""

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Union
from unittest.mock import AsyncMock


@dataclass
class MockLLMResponse:
    """Mock LLM response matching the real LLMResponse interface."""

    content: str
    model: str = "mock-model"
    provider: str = "mock"
    tokens_used: int = 100


class MockLLMProvider:
    """Mock LLM provider for testing.

    Can be configured with predefined responses or response generators.
    """

    def __init__(
        self,
        name: str = "MockProvider",
        is_available: bool = True,
        default_response: str = "This is a mock response.",
    ):
        self._name = name
        self._is_available_value = is_available
        self._default_response = default_response
        self._response_queue: List[str] = []
        self._response_patterns: Dict[str, str] = {}
        self._response_generator: Optional[Callable[[str], str]] = None
        self._call_history: List[Dict] = []

    @property
    def name(self) -> str:
        return self._name

    async def is_available(self) -> bool:
        return self._is_available_value

    def set_available(self, available: bool) -> None:
        """Set whether the provider is available."""
        self._is_available_value = available

    def set_response(self, response: str) -> None:
        """Set a fixed response for all calls."""
        self._default_response = response

    def queue_response(self, response: str) -> None:
        """Queue a response to be returned on the next call."""
        self._response_queue.append(response)

    def queue_responses(self, responses: List[str]) -> None:
        """Queue multiple responses."""
        self._response_queue.extend(responses)

    def set_response_pattern(self, pattern: str, response: str) -> None:
        """Set a response for prompts containing a specific pattern."""
        self._response_patterns[pattern.lower()] = response

    def set_response_generator(self, generator: Callable[[str], str]) -> None:
        """Set a function that generates responses based on prompt."""
        self._response_generator = generator

    def get_call_history(self) -> List[Dict]:
        """Get the history of calls made to this provider."""
        return self._call_history

    def clear_history(self) -> None:
        """Clear call history."""
        self._call_history = []

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
    ) -> MockLLMResponse:
        """Generate a mock response."""
        # Record the call
        self._call_history.append({
            "prompt": prompt,
            "system_prompt": system_prompt,
            "max_tokens": max_tokens,
            "temperature": temperature,
        })

        # Determine response
        content = self._default_response

        # Check queue first
        if self._response_queue:
            content = self._response_queue.pop(0)
        # Then check patterns
        elif self._response_patterns:
            prompt_lower = prompt.lower()
            for pattern, response in self._response_patterns.items():
                if pattern in prompt_lower:
                    content = response
                    break
        # Then use generator if available
        elif self._response_generator:
            content = self._response_generator(prompt)

        return MockLLMResponse(
            content=content,
            model=f"{self._name}-model",
            provider=self._name,
        )


class MockLLMManager:
    """Mock LLM manager that mimics the real LLMManager interface."""

    def __init__(
        self,
        primary_provider: Optional[MockLLMProvider] = None,
        fallback_provider: Optional[MockLLMProvider] = None,
    ):
        self.primary = primary_provider or MockLLMProvider(name="MockPrimary")
        self.fallback = fallback_provider or MockLLMProvider(name="MockFallback")
        self._primary_failures = 0
        self._max_failures = 3

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
    ) -> Optional[MockLLMResponse]:
        """Generate a response using mock providers."""
        # Try primary first
        if self._primary_failures < self._max_failures:
            try:
                if await self.primary.is_available():
                    response = await self.primary.generate(
                        prompt=prompt,
                        system_prompt=system_prompt,
                        max_tokens=max_tokens,
                        temperature=temperature,
                    )
                    self._primary_failures = 0
                    return response
            except Exception:
                self._primary_failures += 1

        # Try fallback
        try:
            if await self.fallback.is_available():
                return await self.fallback.generate(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
        except Exception:
            pass

        return None

    def get_error_message(self) -> str:
        """Get a user-friendly error message."""
        return "Mock LLM error: Both providers failed."

    def reset_primary_failures(self) -> None:
        """Reset the primary failure counter."""
        self._primary_failures = 0

    @property
    def primary_provider_name(self) -> str:
        return self.primary.name

    @property
    def fallback_provider_name(self) -> str:
        return self.fallback.name


# Pre-configured response generators for common test scenarios


def quiz_question_generator(prompt: str) -> str:
    """Generate mock quiz questions based on the prompt."""
    if "question" in prompt.lower() or "quiz" in prompt.lower():
        return """What is the primary purpose of network centrality measures in social network analysis?

Network centrality measures help identify the most important or influential nodes in a network. They quantify how central or connected a node is relative to other nodes in the network.

[EXPECTED: To identify important or influential nodes in a network]"""
    return "Mock response for: " + prompt[:50]


def quiz_evaluation_generator(prompt: str) -> str:
    """Generate mock quiz evaluations."""
    prompt_lower = prompt.lower()

    # Check for keywords suggesting correct answer
    if any(word in prompt_lower for word in ["correct", "right", "accurate", "good"]):
        return """PASS
4
Your answer demonstrates a solid understanding of the concept. You correctly identified the key aspects and provided relevant details."""

    # Check for keywords suggesting partial answer
    if any(word in prompt_lower for word in ["partial", "some", "incomplete"]):
        return """PARTIAL
3
Your answer shows some understanding but is incomplete. Consider expanding on the key mechanisms involved."""

    # Default to a pass
    return """PASS
4
Good answer that covers the main points of the concept."""


def llm_quiz_challenge_generator(prompt: str) -> str:
    """Generate mock responses for LLM Quiz Challenge."""
    prompt_lower = prompt.lower()

    if "answer" in prompt_lower or "respond" in prompt_lower:
        return "Based on the context provided, network centrality measures such as degree centrality, betweenness centrality, and eigenvector centrality help identify influential nodes in a network."

    if "evaluate" in prompt_lower or "judge" in prompt_lower:
        return """STUDENT: CORRECT
LLM: CORRECT
WINNER: TIE

Both the student and the LLM provided accurate answers that align with the course content. Neither answer contains significant errors."""

    return "Mock LLM challenge response"


def assistant_response_generator(prompt: str) -> str:
    """Generate mock responses for the assistant tool."""
    return f"Based on the course materials, here is information about your question: This is a mock assistant response that would normally contain relevant context from the course content."


# Factory functions for creating pre-configured mock providers


def create_quiz_mock_provider() -> MockLLMProvider:
    """Create a mock provider configured for quiz testing."""
    provider = MockLLMProvider(name="QuizMock")
    provider.set_response_generator(quiz_question_generator)
    return provider


def create_evaluation_mock_provider() -> MockLLMProvider:
    """Create a mock provider configured for answer evaluation."""
    provider = MockLLMProvider(name="EvaluationMock")
    provider.set_response_generator(quiz_evaluation_generator)
    return provider


def create_llm_challenge_mock_provider() -> MockLLMProvider:
    """Create a mock provider configured for LLM Quiz Challenge."""
    provider = MockLLMProvider(name="ChallengeMock")
    provider.set_response_generator(llm_quiz_challenge_generator)
    return provider
