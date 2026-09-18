"""Central tool registry for dynamic tool discovery and execution."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from tools.base import BaseLegalTool, ToolResult
from tools.crag_search import CragSearchTool
from tools.web_search import ControlledWebSearchTool


class ToolRegistry:
    """Registry managing available tools and their schemas."""

    def __init__(self):
        self._tools: Dict[str, BaseLegalTool] = {}
        self._register_defaults()

    def _register_defaults(self):
        """Register default agent-visible tools."""
        self.register(CragSearchTool())
        self.register(ControlledWebSearchTool())

    def register(self, tool: BaseLegalTool) -> None:
        """Register a tool instance."""
        self._tools[tool.name] = tool

    def get(self, name: str) -> Optional[BaseLegalTool]:
        """Retrieve tool by name."""
        return self._tools.get(name)

    def list_tools(self) -> List[Dict[str, Any]]:
        """List registered tools with their schemas and descriptions."""
        catalog = []
        for name, tool in self._tools.items():
            schema = tool.args_schema.model_json_schema() if tool.args_schema else {}
            catalog.append({
                "name": name,
                "description": tool.description,
                "parameters": schema,
            })
        return catalog

    def execute(self, tool_name: str, **kwargs) -> ToolResult:
        """Execute a tool by name with arguments."""
        tool = self.get(tool_name)
        if not tool:
            return ToolResult(
                tool_name=tool_name,
                success=False,
                error=f"Tool '{tool_name}' not found in registry. Available: {list(self._tools.keys())}",
            )
        return tool.run(**kwargs)

    def to_openai_tools(self) -> List[Dict[str, Any]]:
        """Export tool specifications formatted for OpenAI / OpenRouter function calling."""
        tools_spec = []
        for name, tool in self._tools.items():
            schema = tool.args_schema.model_json_schema() if tool.args_schema else {"type": "object", "properties": {}}
            tools_spec.append({
                "type": "function",
                "function": {
                    "name": name,
                    "description": tool.description,
                    "parameters": schema,
                },
            })
        return tools_spec


_GLOBAL_REGISTRY: Optional[ToolRegistry] = None


def get_tool_registry() -> ToolRegistry:
    """Get the global tool registry singleton."""
    global _GLOBAL_REGISTRY
    if _GLOBAL_REGISTRY is None:
        _GLOBAL_REGISTRY = ToolRegistry()
    return _GLOBAL_REGISTRY
