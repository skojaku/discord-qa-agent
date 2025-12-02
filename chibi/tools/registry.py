"""Tool registry for discovering and loading tools."""

import importlib
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import yaml

from .base import BaseTool, ToolConfig

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class ToolRegistry:
    """Registry for discovering, loading, and managing tools.

    Tools are loaded from the tools/ directory structure:
    - tools/<name>/config.yaml - Tool configuration
    - tools/<name>/tool.py - Tool implementation (must have create_tool function)
    """

    def __init__(self, bot: Any):
        """Initialize the tool registry.

        Args:
            bot: Reference to the ChibiBot instance
        """
        self.bot = bot
        self._tools: Dict[str, BaseTool] = {}
        self._configs: Dict[str, ToolConfig] = {}

    def register_tool(self, tool: BaseTool) -> None:
        """Register a tool instance.

        Args:
            tool: Tool instance to register
        """
        self._tools[tool.name] = tool
        self._configs[tool.name] = tool.config
        logger.info(f"Registered tool: {tool.name}")

    def get_tool(self, name: str) -> Optional[BaseTool]:
        """Get a tool by name.

        Args:
            name: Tool name

        Returns:
            Tool instance or None if not found
        """
        return self._tools.get(name)

    def get_all_tools(self) -> Dict[str, BaseTool]:
        """Get all registered tools.

        Returns:
            Dict mapping tool names to tool instances
        """
        return self._tools.copy()

    def get_tool_names(self) -> List[str]:
        """Get list of registered tool names.

        Returns:
            List of tool names
        """
        return list(self._tools.keys())

    def get_tool_descriptions(self) -> str:
        """Get formatted descriptions of all tools for intent classification.

        Returns:
            Formatted string with tool names and descriptions
        """
        descriptions = []
        for name, config in self._configs.items():
            keywords = ", ".join(config.trigger_keywords) if config.trigger_keywords else "N/A"
            descriptions.append(f"- {name}: {config.description} (keywords: {keywords})")
        return "\n".join(descriptions)

    async def load_tools_from_directory(self, tools_dir: Optional[Path] = None) -> None:
        """Load all tools from the tools directory.

        Each tool directory should contain:
        - config.yaml: Tool configuration
        - tool.py: Tool implementation with create_tool(bot, config) function

        Args:
            tools_dir: Path to tools directory (defaults to chibi/tools/)
        """
        if tools_dir is None:
            tools_dir = Path(__file__).parent

        for tool_path in tools_dir.iterdir():
            if not tool_path.is_dir():
                continue
            if tool_path.name.startswith("_") or tool_path.name.startswith("."):
                continue
            if tool_path.name in ["__pycache__"]:
                continue

            config_file = tool_path / "config.yaml"
            tool_module_file = tool_path / "tool.py"

            if not config_file.exists() or not tool_module_file.exists():
                continue

            try:
                await self._load_tool(tool_path.name, config_file, tool_path)
            except Exception as e:
                logger.error(f"Failed to load tool {tool_path.name}: {e}", exc_info=True)

    async def _load_tool(
        self,
        tool_name: str,
        config_file: Path,
        tool_path: Path,
    ) -> None:
        """Load a single tool from its directory.

        Args:
            tool_name: Name of the tool (directory name)
            config_file: Path to config.yaml
            tool_path: Path to tool directory
        """
        # Load config
        with open(config_file, "r") as f:
            config_data = yaml.safe_load(f)

        config = ToolConfig(
            name=config_data.get("name", tool_name),
            description=config_data.get("description", ""),
            trigger_keywords=config_data.get("trigger_keywords", []),
            requires_module=config_data.get("requires_module", False),
            requires_user_input=config_data.get("requires_user_input", False),
            parameters_schema=config_data.get("parameters", None),
        )

        # Import tool module
        module_name = f"chibi.tools.{tool_name}.tool"
        try:
            module = importlib.import_module(module_name)
        except ModuleNotFoundError as e:
            logger.error(f"Could not import tool module {module_name}: {e}")
            return

        # Create tool instance
        if not hasattr(module, "create_tool"):
            logger.error(f"Tool module {module_name} missing create_tool function")
            return

        tool = await module.create_tool(self.bot, config)
        self.register_tool(tool)

    def clear(self) -> None:
        """Clear all registered tools."""
        self._tools.clear()
        self._configs.clear()
