"""Base Tool Definition and Schema Contracts for Legal CRAG Assistant V3.

Modeled after Hermes Agent (tools/web_tools.py) and OpenClaw (src/agents/tools/common.js).
Provides strict Pydantic argument validation, error recovery, and standardized result packaging.
"""
from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Type

from pydantic import BaseModel, Field


class ToolResult(BaseModel):
    """Standardized result envelope returned by any legal tool."""
    tool_name: str
    success: bool
    data: Any = None
    error: Optional[str] = None
    execution_time_ms: float = 0.0
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class BaseLegalTool(ABC):
    """Abstract base class for all callable tools in the Legal CRAG ecosystem."""

    name: str = "base_tool"
    description: str = "Base tool description"
    args_schema: Optional[Type[BaseModel]] = None

    def run(self, **kwargs) -> ToolResult:
        """Execute tool with input validation, timing, and error rescue."""
        start_time = time.perf_counter()

        # 1. Validate inputs against Pydantic args_schema if declared
        validated_args = kwargs
        if self.args_schema:
            try:
                model_instance = self.args_schema(**kwargs)
                validated_args = model_instance.model_dump()
            except Exception as val_err:
                elapsed = (time.perf_counter() - start_time) * 1000
                return ToolResult(
                    tool_name=self.name,
                    success=False,
                    error=f"Invalid arguments for {self.name}: {str(val_err)}",
                    execution_time_ms=round(elapsed, 2),
                )

        # 2. Execute concrete tool logic
        try:
            result_data = self.execute(**validated_args)
            elapsed = (time.perf_counter() - start_time) * 1000
            return ToolResult(
                tool_name=self.name,
                success=True,
                data=result_data,
                execution_time_ms=round(elapsed, 2),
            )
        except Exception as exec_err:
            elapsed = (time.perf_counter() - start_time) * 1000
            return ToolResult(
                tool_name=self.name,
                success=False,
                error=f"Tool execution failed in {self.name}: {str(exec_err)}",
                execution_time_ms=round(elapsed, 2),
            )

    @abstractmethod
    def execute(self, **kwargs) -> Any:
        """Concrete tool implementation to be overridden by subclasses."""
        pass
