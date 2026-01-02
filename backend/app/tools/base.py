from typing import Dict, Any, Callable, List
from dataclasses import dataclass


@dataclass
class Tool:
    """Definition of a tool that can be called by the LLM."""
    name: str
    description: str
    parameters: Dict[str, Any]
    handler: Callable

    def to_ollama_format(self) -> Dict[str, Any]:
        """Convert to Ollama tool format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            }
        }


class ToolRegistry:
    """Registry for managing available tools."""

    def __init__(self):
        self._tools: Dict[str, Tool] = {}

    def register(self, tool: Tool):
        """Register a tool."""
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool:
        """Get a tool by name."""
        return self._tools.get(name)

    def get_all(self) -> List[Tool]:
        """Get all registered tools."""
        return list(self._tools.values())

    def to_ollama_format(self) -> List[Dict[str, Any]]:
        """Convert all tools to Ollama format."""
        return [tool.to_ollama_format() for tool in self._tools.values()]

    async def execute(self, name: str, arguments: Dict[str, Any]) -> Any:
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
