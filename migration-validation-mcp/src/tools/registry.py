"""Declarative MCP tool registry.

Each tool is a :class:`ToolSpec`: a name, a description, a Pydantic input
model, and an async handler taking that model. The JSON schema the MCP
client sees is generated from the input model, so the schema, validation,
and handler signature can never drift apart (the old code maintained all
three by hand).
"""

from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from mcp.types import Tool
from pydantic import BaseModel


@dataclass(frozen=True)
class ToolSpec:
    """One MCP tool: schema derived from ``input_model``, executed by ``handler``."""

    name: str
    description: str
    input_model: type[BaseModel]
    handler: Callable[[BaseModel], Awaitable[dict[str, Any]]]

    def to_mcp_tool(self) -> Tool:
        return Tool(
            name=self.name,
            description=self.description,
            inputSchema=self.input_model.model_json_schema(),
        )

    async def call(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Validate raw MCP arguments against the input model, then execute."""
        return await self.handler(self.input_model.model_validate(arguments or {}))
