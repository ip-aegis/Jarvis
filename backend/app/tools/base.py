from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional


class ActionType(str, Enum):
    """Classification of action risk level."""

    READ = "read"  # Safe, read-only queries
    WRITE = "write"  # Modifies state but generally reversible
    DESTRUCTIVE = "destructive"  # Potentially dangerous, may be irreversible


class ActionCategory(str, Enum):
    """Category of infrastructure being acted upon."""

    SERVER = "server"
    NETWORK = "network"
    FIREWALL = "firewall"
    SERVICE = "service"
    MONITORING = "monitoring"
    PROJECT = "project"
    SEARCH = "search"
    SYSTEM = "system"


@dataclass
class Tool:
    """Definition of a tool that can be called by the LLM."""

    name: str
    description: str
    parameters: dict[str, Any]
    handler: Callable

    def to_ollama_format(self) -> dict[str, Any]:
        """Convert to Ollama tool format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    def to_openai_format(self) -> dict[str, Any]:
        """Convert to OpenAI tool format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


@dataclass
class ActionTool(Tool):
    """
    Extended tool with action metadata for infrastructure management.
    Supports confirmation workflows, audit logging, and rollback.
    """

    # Action classification
    action_type: ActionType = ActionType.READ
    category: ActionCategory = ActionCategory.SYSTEM

    # Confirmation settings
    requires_confirmation: bool = False
    confirmation_message: Optional[str] = None

    # Rollback support
    rollback_handler: Optional[Callable] = None

    # Targeting
    target_type: Optional[str] = None  # 'server', 'network_device', 'service'

    def to_ollama_format(self) -> dict[str, Any]:
        """Convert to Ollama tool format with action hints in description."""
        # Add action type hints to description for LLM awareness
        description = self.description
        if self.action_type == ActionType.DESTRUCTIVE:
            description = f"[REQUIRES CONFIRMATION] {description}"
        elif self.action_type == ActionType.WRITE:
            description = f"[MODIFIES STATE] {description}"

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": description,
                "parameters": self.parameters,
            },
        }

    def to_openai_format(self) -> dict[str, Any]:
        """Convert to OpenAI tool format with action hints in description."""
        # Add action type hints to description for LLM awareness
        description = self.description
        if self.action_type == ActionType.DESTRUCTIVE:
            description = f"[REQUIRES CONFIRMATION] {description}"
        elif self.action_type == ActionType.WRITE:
            description = f"[MODIFIES STATE] {description}"

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": description,
                "parameters": self.parameters,
            },
        }

    def get_confirmation_prompt(self, parameters: dict[str, Any]) -> str:
        """Generate confirmation prompt with parameters filled in."""
        if self.confirmation_message:
            try:
                return self.confirmation_message.format(**parameters)
            except KeyError:
                return self.confirmation_message
        return f"Confirm execution of {self.name}?"


class ToolRegistry:
    """Registry for managing available tools."""

    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool):
        """Register a tool."""
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool:
        """Get a tool by name."""
        return self._tools.get(name)

    def get_all(self) -> list[Tool]:
        """Get all registered tools."""
        return list(self._tools.values())

    def to_ollama_format(self) -> list[dict[str, Any]]:
        """Convert all tools to Ollama format."""
        return [tool.to_ollama_format() for tool in self._tools.values()]

    def to_openai_format(self) -> list[dict[str, Any]]:
        """Convert all tools to OpenAI format."""
        return [tool.to_openai_format() for tool in self._tools.values()]

    async def execute(self, name: str, arguments: dict[str, Any]) -> Any:
        """Execute a tool by name."""
        tool = self._tools.get(name)
        if not tool:
            return {"error": f"Tool '{name}' not found"}

        try:
            result = await tool.handler(**arguments)
            return result
        except Exception as e:
            return {"error": str(e)}


# Global registry
tool_registry = ToolRegistry()
