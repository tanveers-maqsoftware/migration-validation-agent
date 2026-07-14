"""MCP server exposing the migration-validation *domain* tools.

Browser automation is handled by the official Playwright MCP server (see
``.mcp.json`` at the repository root) — this server only provides what
Playwright cannot: deterministic value comparison and report generation.

    LLM agent ──(MCP/stdio)──► this server ──► ValidationToolbox
                                                 ├─ ValueComparator
                                                 └─ MarkdownReportBuilder
"""

import asyncio
import json
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from src.config.logging_config import logger
from src.config.settings import settings
from src.tools.registry import ToolSpec
from src.tools.validation_tools import (
    CompareValuesInput,
    CompareVisualsInput,
    EmptyInput,
    GenerateReportInput,
    RecordRunInput,
    ValidationToolbox,
)


def build_tool_specs(toolbox: ValidationToolbox) -> dict[str, ToolSpec]:
    """The single place where tools are declared."""
    specs = [
        ToolSpec(
            name="health_check",
            description="Check the health status of the validation MCP server",
            input_model=EmptyInput,
            handler=toolbox.health_check,
        ),
        ToolSpec(
            name="compare_values",
            description=(
                "Compare rendered value pairs (Tableau vs Power BI) using the "
                "migration tolerance rules: numbers banded (0% pass, <=0.5% "
                "warning, above fail), percentages within 1 point, text "
                "case-insensitive, dates normalized"
            ),
            input_model=CompareValuesInput,
            handler=toolbox.compare_values,
        ),
        ToolSpec(
            name="compare_visuals",
            description=(
                "Compare two matched visuals data-point by data-point and "
                "return a VisualComparison with pass/warning/fail per value"
            ),
            input_model=CompareVisualsInput,
            handler=toolbox.compare_visuals,
        ),
        ToolSpec(
            name="generate_validation_report",
            description=(
                "Render all visual comparisons into a Markdown validation "
                "report in the validation-reports directory"
            ),
            input_model=GenerateReportInput,
            handler=toolbox.generate_validation_report,
        ),
        ToolSpec(
            name="record_validation_run",
            description=(
                "Append a completed run (summary counts + self-harness check "
                "outcomes) to harness-log.json and get cumulative statistics"
            ),
            input_model=RecordRunInput,
            handler=toolbox.record_validation_run,
        ),
        ToolSpec(
            name="get_validation_history",
            description=(
                "Read all recorded validation runs and cumulative statistics "
                "(average pass rate, most common failed harness check)"
            ),
            input_model=EmptyInput,
            handler=toolbox.get_validation_history,
        ),
    ]
    return {spec.name: spec for spec in specs}


def create_server() -> Server:
    """Wire the toolbox into an MCP server instance."""
    server = Server("migration-validation-mcp")
    tool_specs = build_tool_specs(ValidationToolbox())

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return [spec.to_mcp_tool() for spec in tool_specs.values()]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        logger.info(f"Tool called: {name}")
        spec = tool_specs.get(name)
        if spec is None:
            result: dict[str, Any] = {"error": f"Unknown tool: {name}"}
        else:
            try:
                result = await spec.call(arguments)
            except Exception as error:
                # Never let an exception kill the stdio session — report it to
                # the agent instead so it can retry or work around the failure.
                logger.error(f"Error executing tool {name}: {error}")
                result = {"error": str(error), "tool": name}
        return [TextContent(type="text", text=json.dumps(result, default=str))]

    return server


async def main() -> None:
    logger.info(f"Starting {settings.app_name} server...")
    server = create_server()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


def run() -> None:
    """Synchronous entry point for console scripts (`uv run` / installed script)."""
    asyncio.run(main())


if __name__ == "__main__":
    run()
