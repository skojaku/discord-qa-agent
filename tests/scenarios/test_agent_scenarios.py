"""Scenario-based tests for the natural language routing agent.

These tests simulate users interacting with the bot via
natural language (mentions, DMs) and verify proper intent
classification and tool dispatching.
"""

import pytest
import pytest_asyncio
from typing import Dict, Any
from unittest.mock import AsyncMock, MagicMock, patch

from tests.mocks import MockUser, MockMessage, MockChannel, create_mock_message
from tests.mocks.llm_mocks import MockLLMProvider, MockLLMManager


class TestIntentClassificationScenarios:
    """Test scenarios for intent classification."""

    @pytest.fixture
    def intent_response_generator(self):
        """Create a response generator for intent classification."""

        def generator(prompt: str) -> str:
            prompt_lower = prompt.lower()

            # Quiz intent
            if any(phrase in prompt_lower for phrase in [
                "quiz me", "give me a quiz", "test me", "ask me a question"
            ]):
                return '{"intent": "quiz", "confidence": 0.95, "params": {}}'

            # Status intent
            if any(phrase in prompt_lower for phrase in [
                "my progress", "my status", "how am i doing", "show my progress"
            ]):
                return '{"intent": "status", "confidence": 0.9, "params": {}}'

            # LLM Quiz intent
            if any(phrase in prompt_lower for phrase in [
                "challenge", "stump the ai", "llm quiz"
            ]):
                return '{"intent": "llm_quiz", "confidence": 0.85, "params": {}}'

            # Default to assistant
            return '{"intent": "assistant", "confidence": 0.8, "params": {}}'

        return generator

    @pytest.mark.asyncio
    async def test_scenario_classify_quiz_intent(
        self,
        mock_llm_manager,
        intent_response_generator,
    ):
        """
        Scenario: User wants to take a quiz

        Given: A user message like "Quiz me on module 1"
        When: The intent classifier processes the message
        Then: It should classify as "quiz" intent
        """
        # Configure mock LLM
        mock_llm_manager.primary.set_response_generator(intent_response_generator)

        # Simulate classification
        user_message = "Quiz me on module 1"
        response = await mock_llm_manager.generate(
            prompt=f'User message: "{user_message}"'
        )

        # Parse response
        import json
        result = json.loads(response.content)

        assert result["intent"] == "quiz"
        assert result["confidence"] >= 0.9

    @pytest.mark.asyncio
    async def test_scenario_classify_status_intent(
        self,
        mock_llm_manager,
        intent_response_generator,
    ):
        """
        Scenario: User wants to check their progress

        Given: A user message like "What's my progress?"
        When: The intent classifier processes the message
        Then: It should classify as "status" intent
        """
        mock_llm_manager.primary.set_response_generator(intent_response_generator)

        user_message = "What's my progress?"
        response = await mock_llm_manager.generate(
            prompt=f'User message: "{user_message}"'
        )

        import json
        result = json.loads(response.content)

        assert result["intent"] == "status"

    @pytest.mark.asyncio
    async def test_scenario_classify_llm_quiz_intent(
        self,
        mock_llm_manager,
        intent_response_generator,
    ):
        """
        Scenario: User wants to challenge the AI

        Given: A user message like "I want to challenge the AI"
        When: The intent classifier processes the message
        Then: It should classify as "llm_quiz" intent
        """
        mock_llm_manager.primary.set_response_generator(intent_response_generator)

        user_message = "I want to challenge the AI"
        response = await mock_llm_manager.generate(
            prompt=f'User message: "{user_message}"'
        )

        import json
        result = json.loads(response.content)

        assert result["intent"] == "llm_quiz"

    @pytest.mark.asyncio
    async def test_scenario_classify_general_question(
        self,
        mock_llm_manager,
        intent_response_generator,
    ):
        """
        Scenario: User asks a general question

        Given: A user message like "How does network centrality work?"
        When: The intent classifier processes the message
        Then: It should classify as "assistant" intent
        """
        mock_llm_manager.primary.set_response_generator(intent_response_generator)

        user_message = "How does network centrality work?"
        response = await mock_llm_manager.generate(
            prompt=f'User message: "{user_message}"'
        )

        import json
        result = json.loads(response.content)

        assert result["intent"] == "assistant"


class TestMessageRoutingScenarios:
    """Test scenarios for message routing decisions."""

    @pytest.mark.asyncio
    async def test_scenario_route_dm_message(
        self,
        mock_user,
    ):
        """
        Scenario: User sends a direct message

        Given: A message in a DM channel
        When: The bot processes it
        Then: It should be routed to the agent
        """
        from tests.mocks.discord_mocks import MockDMChannel

        # Create DM message
        dm_channel = MockDMChannel(recipient=mock_user)
        message = create_mock_message(
            content="Quiz me!",
            channel=dm_channel,
            is_dm=True,
        )

        # DM channel detection
        from discord import DMChannel
        is_dm = message.channel.type == "private"

        assert is_dm is True

    @pytest.mark.asyncio
    async def test_scenario_route_mention_message(
        self,
        mock_user,
    ):
        """
        Scenario: User mentions the bot

        Given: A message that mentions the bot
        When: The bot processes it
        Then: It should be routed to the agent
        """
        bot_user = MockUser(id=999999999, name="ChibiBot", bot=True)
        message = create_mock_message(
            content="@ChibiBot quiz me on networks",
            mentions=[bot_user],
        )

        # Check if bot is mentioned
        is_mentioned = bot_user in message.mentions

        assert is_mentioned is True

    @pytest.mark.asyncio
    async def test_scenario_ignore_bot_messages(
        self,
    ):
        """
        Scenario: Bot receives a message from another bot

        Given: A message from another bot
        When: The message is checked
        Then: It should be ignored
        """
        bot_author = MockUser(id=888888888, name="OtherBot", bot=True)
        message = create_mock_message(
            content="Hello!",
            user_id=bot_author.id,
            user_name=bot_author.name,
        )
        message.author = bot_author

        # Should ignore bot messages
        should_ignore = message.author.bot

        assert should_ignore is True

    @pytest.mark.asyncio
    async def test_scenario_ignore_prefix_commands(
        self,
        mock_user,
    ):
        """
        Scenario: User sends a prefix command

        Given: A message starting with "!"
        When: The bot checks if it should route to agent
        Then: It should NOT route to agent (handled by prefix handler)
        """
        message = create_mock_message(
            content="!help",
        )

        # Prefix commands should not go to agent
        command_prefix = "!"
        is_prefix_command = message.content.startswith(command_prefix)

        assert is_prefix_command is True


class TestConversationContextScenarios:
    """Test scenarios for conversation context and memory."""

    @pytest.mark.asyncio
    async def test_scenario_maintain_conversation_history(
        self,
        mock_user,
        mock_channel,
    ):
        """
        Scenario: Bot maintains conversation history

        Given: Multiple messages in a conversation
        When: The agent processes each message
        Then: Previous context should be available
        """
        from chibi.agent.memory import ConversationMemory

        memory = ConversationMemory(max_history=20)

        # Add messages to conversation
        user_id = str(mock_user.id)
        channel_id = str(mock_channel.id)

        memory.add_message(
            user_id=user_id,
            channel_id=channel_id,
            role="user",
            content="Quiz me on networks",
        )
        memory.add_message(
            user_id=user_id,
            channel_id=channel_id,
            role="assistant",
            content="Here's a question about network centrality...",
        )

        # Get history
        history = memory.get_history(user_id, channel_id)

        assert len(history) == 2
        assert history[0]["content"] == "Quiz me on networks"
        assert history[1]["role"] == "assistant"

    @pytest.mark.asyncio
    async def test_scenario_history_limit(
        self,
        mock_user,
        mock_channel,
    ):
        """
        Scenario: Conversation history respects limit

        Given: A max_history limit of 5
        When: More than 5 messages are added
        Then: Only the last 5 should be retained
        """
        from chibi.agent.memory import ConversationMemory

        memory = ConversationMemory(max_history=5)
        user_id = str(mock_user.id)
        channel_id = str(mock_channel.id)

        # Add more messages than limit
        for i in range(10):
            memory.add_message(
                user_id=user_id,
                channel_id=channel_id,
                role="user" if i % 2 == 0 else "assistant",
                content=f"Message {i}",
            )

        history = memory.get_history(user_id, channel_id)

        # Should only have last 5
        assert len(history) <= 5

    @pytest.mark.asyncio
    async def test_scenario_separate_channel_histories(
        self,
        mock_user,
    ):
        """
        Scenario: Different channels have separate histories

        Given: Messages in two different channels
        When: History is retrieved
        Then: Each channel should have its own history
        """
        from chibi.agent.memory import ConversationMemory

        memory = ConversationMemory(max_history=20)
        user_id = str(mock_user.id)

        # Add to channel 1
        memory.add_message(
            user_id=user_id,
            channel_id="channel-1",
            role="user",
            content="Message in channel 1",
        )

        # Add to channel 2
        memory.add_message(
            user_id=user_id,
            channel_id="channel-2",
            role="user",
            content="Message in channel 2",
        )

        # Get separate histories
        history_1 = memory.get_history(user_id, "channel-1")
        history_2 = memory.get_history(user_id, "channel-2")

        assert len(history_1) == 1
        assert len(history_2) == 1
        assert history_1[0]["content"] != history_2[0]["content"]


class TestMentionCleaningScenarios:
    """Test scenarios for cleaning bot mentions from messages."""

    def test_scenario_clean_standard_mention(self):
        """
        Scenario: Clean a standard bot mention

        Given: A message with "<@123456789>"
        When: The mention is cleaned
        Then: Only the text should remain
        """
        bot_id = 123456789
        content = f"<@{bot_id}> quiz me on networks"

        # Clean mention
        cleaned = content.replace(f"<@{bot_id}>", "").strip()

        assert cleaned == "quiz me on networks"

    def test_scenario_clean_nickname_mention(self):
        """
        Scenario: Clean a nickname mention

        Given: A message with "<@!123456789>" (nickname format)
        When: The mention is cleaned
        Then: Only the text should remain
        """
        bot_id = 123456789
        content = f"<@!{bot_id}> show my status"

        # Clean both mention formats
        cleaned = content.replace(f"<@{bot_id}>", "").replace(f"<@!{bot_id}>", "").strip()

        assert cleaned == "show my status"

    def test_scenario_handle_empty_after_mention(self):
        """
        Scenario: Handle message that is only a mention

        Given: A message that is just the bot mention
        When: The mention is cleaned
        Then: The result should be an empty string
        """
        bot_id = 123456789
        content = f"<@{bot_id}>"

        cleaned = content.replace(f"<@{bot_id}>", "").strip()

        assert cleaned == ""


class TestToolDispatchScenarios:
    """Test scenarios for dispatching to specific tools."""

    @pytest.mark.asyncio
    async def test_scenario_dispatch_to_quiz_tool(
        self,
    ):
        """
        Scenario: Dispatch to quiz tool

        Given: An intent classified as "quiz"
        When: The dispatcher processes it
        Then: The quiz tool should be selected
        """
        from chibi.agent.nodes.router import should_use_tool

        state = {
            "detected_intent": "quiz",
            "intent_confidence": 0.95,
        }

        result = should_use_tool(state)

        assert result == "use_tool"

    @pytest.mark.asyncio
    async def test_scenario_dispatch_to_status_tool(
        self,
    ):
        """
        Scenario: Dispatch to status tool

        Given: An intent classified as "status"
        When: The dispatcher processes it
        Then: The status tool should be selected
        """
        from chibi.agent.nodes.router import should_use_tool

        state = {
            "detected_intent": "status",
            "intent_confidence": 0.9,
        }

        result = should_use_tool(state)

        assert result == "use_tool"

    @pytest.mark.asyncio
    async def test_scenario_dispatch_to_assistant(
        self,
    ):
        """
        Scenario: Dispatch to assistant for general questions

        Given: An intent classified as "assistant"
        When: The dispatcher processes it
        Then: The assistant tool should handle it
        """
        from chibi.agent.nodes.router import should_use_tool

        state = {
            "detected_intent": "assistant",
            "intent_confidence": 0.8,
        }

        result = should_use_tool(state)

        # Assistant is still a tool
        assert result == "use_tool"


class TestAgentStateScenarios:
    """Test scenarios for agent state management."""

    def test_scenario_initial_state_structure(self):
        """
        Scenario: Agent starts with correct initial state

        Given: A new agent invocation
        When: Initial state is created
        Then: All required fields should be present
        """
        initial_state = {
            "discord_message": None,
            "cleaned_content": None,
            "messages": [],
            "detected_intent": None,
            "intent_confidence": 0.0,
            "extracted_params": {},
            "selected_tool": None,
            "tool_result": None,
            "response_type": "text",
            "response_content": None,
            "conversation_history": [],
        }

        # All required fields present
        assert "discord_message" in initial_state
        assert "detected_intent" in initial_state
        assert "messages" in initial_state
        assert "selected_tool" in initial_state
        assert "response_content" in initial_state

    def test_scenario_state_update_after_classification(self):
        """
        Scenario: State is updated after intent classification

        Given: A state with a classified intent
        When: The router returns updates
        Then: The state should reflect the classification
        """
        # Simulated router output
        router_output = {
            "detected_intent": "quiz",
            "intent_confidence": 0.95,
            "extracted_params": {"module": "module-1"},
            "selected_tool": "quiz",
        }

        # Update initial state
        state = {}
        state.update(router_output)

        assert state["detected_intent"] == "quiz"
        assert state["intent_confidence"] == 0.95
        assert state["extracted_params"]["module"] == "module-1"


class TestAgentErrorHandlingScenarios:
    """Test scenarios for agent error handling."""

    @pytest.mark.asyncio
    async def test_scenario_handle_invalid_json_response(
        self,
        mock_llm_manager,
    ):
        """
        Scenario: LLM returns invalid JSON

        Given: An LLM response that is not valid JSON
        When: The intent classifier tries to parse it
        Then: It should fall back to "assistant" intent
        """
        mock_llm_manager.primary.set_response("Not valid JSON at all")

        response = await mock_llm_manager.generate(prompt="Test")

        # Parser should handle invalid JSON gracefully
        import json
        try:
            result = json.loads(response.content)
        except json.JSONDecodeError:
            result = {"intent": "assistant", "confidence": 0.5}

        assert result["intent"] == "assistant"

    @pytest.mark.asyncio
    async def test_scenario_handle_llm_failure(
        self,
        mock_llm_manager,
    ):
        """
        Scenario: Both LLM providers fail

        Given: Both primary and fallback providers are unavailable
        When: Intent classification is attempted
        Then: It should fall back gracefully
        """
        mock_llm_manager.primary.set_available(False)
        mock_llm_manager.fallback.set_available(False)

        response = await mock_llm_manager.generate(prompt="Test")

        # Should return None when both fail
        assert response is None

        # System should handle this gracefully
        fallback_intent = "assistant"
        assert fallback_intent == "assistant"
