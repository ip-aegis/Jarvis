# Tool registry and tool definitions
from app.tools.base import Tool, ToolRegistry, tool_registry

# Import tools to trigger registration
from app.tools.web_search import web_search_tool
from app.tools.server_tools import (
    list_servers_tool,
    get_server_metrics_tool,
    get_metric_history_tool,
)
from app.tools.project_tools import (
    list_projects_tool,
    get_project_details_tool,
    search_projects_tool,
)

# Export for easy access
__all__ = [
    "Tool",
    "ToolRegistry",
    "tool_registry",
    "web_search_tool",
    "list_servers_tool",
    "get_server_metrics_tool",
    "get_metric_history_tool",
    "list_projects_tool",
    "get_project_details_tool",
    "search_projects_tool",
]
