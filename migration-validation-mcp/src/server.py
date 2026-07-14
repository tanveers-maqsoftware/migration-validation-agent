"""
MCP server for the Migration Validation Agent.

This is the bridge between an LLM agent (Claude Code / VS Code Copilot) and a
real Chromium browser. The agent cannot touch a browser directly — instead it
speaks the Model Context Protocol (MCP) over stdio, and this server translates
each MCP tool call into a Playwright browser action.

How a single tool call flows through the system:

    LLM agent                       this file                  Playwright
    ─────────                       ─────────                  ──────────
    "call navigate_to_url"  ──►  call_tool() looks up   ──►  BrowserTools.navigate_to_url()
        (JSON-RPC / stdio)        the handler in              └─► BrowserAutomationService.navigate()
                                  TOOL_HANDLERS                     └─► page.goto(url) in Chromium
    JSON result  ◄──────────  result serialized as       ◄──  {"success": True, "title": ...}
                              TextContent

The three layers are deliberately separate:
  * server.py                 — MCP protocol plumbing only (this file)
  * tools/browser_tools.py    — tool schemas + thin wrappers the agent sees
  * services/browser_automation.py — actual Playwright browser logic
"""

import asyncio
import json
from typing import Any, Awaitable, Callable, Dict, List

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from src.config.logging_config import logger
from src.services.browser_automation import BrowserAutomationService
from src.tools.browser_tools import BrowserTools
from src.tools.health import health_check

# ---------------------------------------------------------------------------
# Wiring: one browser service shared by all tools, wrapped once for MCP.
# ---------------------------------------------------------------------------

server = Server("migration-validation-mcp")

browser_service = BrowserAutomationService()
browser_tools = BrowserTools(browser_service)


async def _health_check(**_: Any) -> Dict[str, Any]:
    """Async wrapper so the sync health probe fits the handler table below."""
    return health_check()


# Maps an MCP tool name to the coroutine that executes it. Each handler
# receives the tool arguments as keyword args; defaults (e.g. timeout) are
# defined on the BrowserTools method signatures themselves, so no per-tool
# argument unpacking is needed here.
TOOL_HANDLERS: Dict[str, Callable[..., Awaitable[Dict[str, Any]]]] = {
    "health_check": _health_check,
    "initialize_browser": browser_tools.initialize_browser,
    "navigate_to_url": browser_tools.navigate_to_url,
    "take_screenshot": browser_tools.take_screenshot,
    "get_page_snapshot": browser_tools.get_page_snapshot,
    "hover_element": browser_tools.hover_element,
    "click_element": browser_tools.click_element,
    "execute_javascript": browser_tools.execute_javascript,
    "wait_for_element": browser_tools.wait_for_element,
    "close_browser": browser_tools.close_browser,
}


# ---------------------------------------------------------------------------
# MCP protocol endpoints. The agent calls list_tools() once at startup to
# discover what it can do, then call_tool() for every action it takes.
# ---------------------------------------------------------------------------

@server.list_tools()
async def list_tools() -> List[Tool]:
    """Advertise every available tool (name + JSON schema) to the agent."""
    tools = browser_tools.get_tool_definitions()

    tools.append({
        "name": "health_check",
        "description": "Check the health status of the MCP server and browser",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    })

    return [Tool(**tool) for tool in tools]


@server.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
    """Execute one tool call from the agent and return its result as JSON text."""
    logger.info(f"Tool called: {name} with arguments: {arguments}")

    handler = TOOL_HANDLERS.get(name)
    if handler is None:
        return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]

    try:
        result = await handler(**(arguments or {}))
        return [TextContent(type="text", text=json.dumps(result))]
    except Exception as e:
        # Never let an exception kill the stdio session — report it to the
        # agent instead so it can retry or work around the failure.
        logger.error(f"Error executing tool {name}: {e}")
        return [TextContent(type="text", text=json.dumps({"error": str(e), "tool": name}))]


# ---------------------------------------------------------------------------
# Entry points.
# ---------------------------------------------------------------------------

async def main():
    """Launch the browser, then serve MCP requests over stdin/stdout forever."""
    logger.info("Starting Migration Validation MCP server...")

    # Launch Chromium up front so the agent's first navigate call is instant.
    await browser_tools.initialize_browser()

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
