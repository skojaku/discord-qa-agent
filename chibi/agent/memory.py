"""Conversation memory management for the main agent."""

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ConversationEntry:
    """A single entry in the conversation history."""

    role: str  # "user" or "assistant"
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)


class ConversationMemory:
    """In-memory conversation history manager.

    Manages conversation history per user/channel combination.
    History is stored in-memory only and lost on bot restart.
    """

    def __init__(self, max_history: int = 20):
        """Initialize conversation memory.

        Args:
            max_history: Maximum number of messages to retain per conversation
        """
        self.max_history = max_history
        # Key: (user_id, channel_id), Value: List of ConversationEntry
        self._history: Dict[tuple, List[ConversationEntry]] = defaultdict(list)

    def _get_key(self, user_id: str, channel_id: str) -> tuple:
        """Get the storage key for a user/channel combination."""
        return (user_id, channel_id)

    def add_message(
        self,
        user_id: str,
        channel_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Add a message to the conversation history.

        Args:
            user_id: Discord user ID
            channel_id: Discord channel ID
            role: "user" or "assistant"
            content: Message content
            metadata: Optional metadata (tool used, result summary, etc.)
        """
        key = self._get_key(user_id, channel_id)
        entry = ConversationEntry(
            role=role,
            content=content,
            metadata=metadata or {},
        )
        self._history[key].append(entry)

        # Trim to max history
        if len(self._history[key]) > self.max_history:
            self._history[key] = self._history[key][-self.max_history :]

    def get_history(
        self,
        user_id: str,
        channel_id: str,
        limit: Optional[int] = None,
    ) -> List[Dict[str, str]]:
        """Get conversation history for a user/channel.

        Args:
            user_id: Discord user ID
            channel_id: Discord channel ID
            limit: Maximum number of messages to return (most recent)

        Returns:
            List of message dicts with 'role' and 'content' keys
        """
        key = self._get_key(user_id, channel_id)
        history = self._history.get(key, [])

        if limit:
            history = history[-limit:]

        return [{"role": e.role, "content": e.content} for e in history]

    def get_context_summary(
        self,
        user_id: str,
        channel_id: str,
        max_messages: int = 5,
    ) -> str:
        """Get a brief summary of recent context for sub-agents.

        This provides minimal context to sub-agents without
        overwhelming them with full conversation history.

        Args:
            user_id: Discord user ID
            channel_id: Discord channel ID
            max_messages: Maximum messages to include in summary

        Returns:
            Condensed context string
        """
        history = self.get_history(user_id, channel_id, limit=max_messages)

        if not history:
            return ""

        summary_parts = []
        for msg in history:
            role = "User" if msg["role"] == "user" else "Assistant"
            # Truncate long messages
            content = msg["content"][:200] + "..." if len(msg["content"]) > 200 else msg["content"]
            summary_parts.append(f"{role}: {content}")

        return "\n".join(summary_parts)

    def get_recent_chunk_ids(
        self,
        user_id: str,
        channel_id: str,
        max_messages: int = 5,
    ) -> set:
        """Get chunk IDs from recent assistant responses.

        Used to avoid retrieving the same RAG chunks in subsequent turns.

        Args:
            user_id: Discord user ID
            channel_id: Discord channel ID
            max_messages: Maximum messages to look back

        Returns:
            Set of chunk IDs that were recently retrieved
        """
        key = self._get_key(user_id, channel_id)
        history = self._history.get(key, [])

        if not history:
            return set()

        chunk_ids = set()
        # Look at recent messages
        for entry in history[-max_messages:]:
            if entry.role == "assistant" and entry.metadata:
                # Get chunk IDs stored in metadata
                ids = entry.metadata.get("chunk_ids", [])
                chunk_ids.update(ids)

        return chunk_ids

    def clear_history(self, user_id: str, channel_id: str) -> None:
        """Clear conversation history for a user/channel.

        Args:
            user_id: Discord user ID
            channel_id: Discord channel ID
        """
        key = self._get_key(user_id, channel_id)
        if key in self._history:
            del self._history[key]

    def clear_all(self) -> None:
        """Clear all conversation history."""
        self._history.clear()
