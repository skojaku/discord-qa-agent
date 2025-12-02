"""Base tool protocol and configuration."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from ..agent.state import SubAgentState, ToolResult


@dataclass
class ToolConfig:
    """Configuration for a tool loaded from config.yaml.

    Attributes:
        name: Unique tool identifier
        description: Human-readable description for intent classification
        trigger_keywords: Keywords that indicate this tool should be used
        requires_module: Whether the tool needs a module parameter
        requires_user_input: Whether the tool needs user text input
        parameters_schema: JSON schema for tool parameters
    """

    name: str
    description: str
    trigger_keywords: List[str] = field(default_factory=list)
    requires_module: bool = False
    requires_user_input: bool = False
    parameters_schema: Optional[Dict[str, Any]] = None


class BaseTool(ABC):
    """Base class for all tools (sub-agents).

    Tools are self-contained units that handle specific functionality.
    Each tool receives a minimal SubAgentState and returns a ToolResult.
    The sub-agent state is discarded after execution.
    """

    def __init__(self, bot: Any, config: ToolConfig):
        """Initialize the tool.

        Args:
            bot: Reference to the ChibiBot instance
            config: Tool configuration
        """
        self.bot = bot
        self.config = config

    @property
    def name(self) -> str:
        """Get the tool name."""
        return self.config.name

    @property
    def description(self) -> str:
        """Get the tool description."""
        return self.config.description

    @abstractmethod
    async def execute(self, state: "SubAgentState") -> "ToolResult":
        """Execute the tool with the given sub-agent state.

        The sub-agent state is minimal and discarded after execution.
        Returns ToolResult with success status, result data, summary, and metadata.

        Args:
            state: Minimal sub-agent state with task description and parameters

        Returns:
            ToolResult containing execution outcome
        """
        pass

    def get_schema(self) -> Dict[str, Any]:
        """Return JSON schema for tool parameters.

        Returns:
            JSON schema dict or empty dict if no schema
        """
        return self.config.parameters_schema or {}

    async def validate_params(
        self, params: Dict[str, Any]
    ) -> tuple[bool, Optional[str]]:
        """Validate parameters before execution.

        Override this method to add custom validation logic.

        Args:
            params: Parameters to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        return True, None

    def get_trigger_keywords(self) -> List[str]:
        """Get keywords that trigger this tool.

        Returns:
            List of trigger keywords
        """
        return self.config.trigger_keywords
