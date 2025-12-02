"""Router node for intent classification."""

from __future__ import annotations

import json
import logging
import re
from typing import TYPE_CHECKING, Any, Literal

from ..state import MainAgentState

if TYPE_CHECKING:
    from ...llm.manager import LLMManager
    from ...tools.registry import ToolRegistry

logger = logging.getLogger(__name__)

# Global references set during graph creation
_llm_manager: "LLMManager" = None
_tool_registry: "ToolRegistry" = None


def set_router_dependencies(llm_manager: "LLMManager", tool_registry: "ToolRegistry") -> None:
    """Set the dependencies for the router node.

    Called during graph creation to inject dependencies.

    Args:
        llm_manager: LLM manager for intent classification
        tool_registry: Tool registry for available tools
    """
    global _llm_manager, _tool_registry
    _llm_manager = llm_manager
    _tool_registry = tool_registry


INTENT_PROMPT_TEMPLATE = """You are an intent classifier for a Discord educational bot.
Analyze the user's message and determine which tool should handle it.

Available tools:
{tool_descriptions}

User message: "{user_message}"

Respond with a JSON object containing:
- "intent": The tool name that best matches the user's intent (or "assistant" for general questions)
- "confidence": A confidence score between 0 and 1
- "params": Any extracted parameters (e.g., module name, topic)

Examples:
- "Quiz me on module 1" -> {{"intent": "quiz", "confidence": 0.95, "params": {{"module": "module-1"}}}}
- "What's my progress?" -> {{"intent": "status", "confidence": 0.9, "params": {{}}}}
- "I want to challenge the AI" -> {{"intent": "llm_quiz", "confidence": 0.85, "params": {{}}}}
- "How does network analysis work?" -> {{"intent": "assistant", "confidence": 0.8, "params": {{"topic": "network analysis"}}}}

Respond ONLY with the JSON object, no other text."""


async def classify_intent(state: "MainAgentState") -> dict[str, Any]:
    """Use LLM to classify user intent and extract parameters.

    Args:
        state: Current agent state with user message

    Returns:
        Updated state fields with intent classification
    """
    if _llm_manager is None or _tool_registry is None:
        logger.error("Router dependencies not set")
        return {
            "detected_intent": "assistant",
            "intent_confidence": 0.0,
            "extracted_params": {},
        }

    messages = state.get("messages", [])
    if not messages:
        return {
            "detected_intent": "assistant",
            "intent_confidence": 0.0,
            "extracted_params": {},
        }

    user_message = messages[-1].get("content", "")

    # Build tool descriptions for the prompt
    tool_descriptions = _tool_registry.get_tool_descriptions()

    prompt = INTENT_PROMPT_TEMPLATE.format(
        tool_descriptions=tool_descriptions,
        user_message=user_message,
    )

    try:
        response = await _llm_manager.generate(
            prompt=prompt,
            system_prompt="You are a helpful intent classifier. Always respond with valid JSON.",
            max_tokens=256,
            temperature=0.1,  # Low temperature for consistent classification
        )

        # Parse JSON response
        content = response.content.strip()
        # Extract JSON from potential markdown code blocks
        if "```" in content:
            match = re.search(r"```(?:json)?\s*(.*?)\s*```", content, re.DOTALL)
            if match:
                content = match.group(1)

        result = json.loads(content)

        intent = result.get("intent", "assistant")
        confidence = float(result.get("confidence", 0.5))
        params = result.get("params", {})

        logger.info(f"Classified intent: {intent} (confidence: {confidence})")

        return {
            "detected_intent": intent,
            "intent_confidence": confidence,
            "extracted_params": params,
            "selected_tool": intent,
        }

    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse intent JSON: {e}")
        return {
            "detected_intent": "assistant",
            "intent_confidence": 0.5,
            "extracted_params": {},
            "selected_tool": "assistant",
        }
    except Exception as e:
        logger.error(f"Error classifying intent: {e}")
        return {
            "detected_intent": "assistant",
            "intent_confidence": 0.0,
            "extracted_params": {},
            "selected_tool": "assistant",
        }


def should_use_tool(state: "MainAgentState") -> Literal["use_tool", "direct_response"]:
    """Decide whether to dispatch to a tool or respond directly.

    Args:
        state: Current agent state with intent classification

    Returns:
        "use_tool" if a specific tool should handle this, "direct_response" otherwise
    """
    intent = state.get("detected_intent")
    confidence = state.get("intent_confidence", 0.0)

    # Always use tools for quiz-related intents
    if intent in ["quiz", "llm_quiz", "status"]:
        return "use_tool"

    # For assistant intent, also use the assistant tool
    return "use_tool"
