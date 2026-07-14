"""
Browser tools wrapper for MCP server.

Provides tool definitions that wrap BrowserAutomationService methods
for use with the MCP protocol.
"""

from typing import Any, Dict, Optional

from loguru import logger

from src.services.browser_automation import BrowserAutomationService


class BrowserTools:
    """
    Wrapper class that exposes browser automation methods as MCP tools.
    
    Each method corresponds to an MCP tool that can be invoked by the AI agent.
    """

    def __init__(self, browser_service: BrowserAutomationService):
        """
        Initialize browser tools with a browser automation service instance.
        
        Args:
            browser_service: BrowserAutomationService instance to wrap
        """
        self._browser = browser_service
        logger.info("BrowserTools initialized")

    async def navigate_to_url(self, url: str, page_type: str = "tableau", timeout: int = 60000) -> Dict[str, Any]:
        """
        Navigate to a URL and wait for page load.
        
        Tool: navigate_to_url
        Description: Navigate browser to specified URL for Tableau or Power BI report
        
        Args:
            url: The URL to navigate to
            page_type: 'tableau' or 'powerbi' - determines which browser tab to use
            timeout: Maximum wait time in milliseconds (default: 60000)
            
        Returns:
            Dictionary with success status, URL, title, and screenshot path
        """
        logger.info(f"Tool: navigate_to_url({url}, {page_type})")
        return await self._browser.navigate(url, page_type, timeout)

    async def take_screenshot(self, page_type: str, name: Optional[str] = None) -> Dict[str, Any]:
        """
        Take a screenshot of the current page.
        
        Tool: take_screenshot
        Description: Capture screenshot of current Tableau or Power BI report page
        
        Args:
            page_type: 'tableau' or 'powerbi'
            name: Optional name prefix for the screenshot file
            
        Returns:
            Dictionary with success status and screenshot file path
        """
        logger.info(f"Tool: take_screenshot({page_type}, {name})")
        return await self._browser.take_screenshot(page_type, name)

    async def get_page_snapshot(self, page_type: str = "tableau") -> Dict[str, Any]:
        """
        Capture accessibility snapshot of the current page.
        
        Tool: get_page_snapshot
        Description: Get accessibility tree snapshot for analyzing page structure
        
        Args:
            page_type: 'tableau' or 'powerbi'
            
        Returns:
            Dictionary with accessibility tree, URL, and title
        """
        logger.info(f"Tool: get_page_snapshot({page_type})")
        return await self._browser.snapshot(page_type)

    async def hover_element(self, page_type: str, selector: str, timeout: int = 5000) -> Dict[str, Any]:
        """
        Hover over an element to reveal tooltips.
        
        Tool: hover_element
        Description: Hover over page element to reveal tooltip or additional data
        
        Args:
            page_type: 'tableau' or 'powerbi'
            selector: CSS selector of element to hover over
            timeout: Maximum wait time in milliseconds
            
        Returns:
            Dictionary with success status and tooltip content if available
        """
        logger.info(f"Tool: hover_element({page_type}, {selector})")
        return await self._browser.hover(page_type, selector, timeout)

    async def click_element(self, page_type: str, selector: str, timeout: int = 5000) -> Dict[str, Any]:
        """
        Click on an element.
        
        Tool: click_element
        Description: Click on page element (button, filter, visual, etc.)
        
        Args:
            page_type: 'tableau' or 'powerbi'
            selector: CSS selector of element to click
            timeout: Maximum wait time in milliseconds
            
        Returns:
            Dictionary with success status
        """
        logger.info(f"Tool: click_element({page_type}, {selector})")
        return await self._browser.click(page_type, selector, timeout)

    async def execute_javascript(self, page_type: str, javascript: str) -> Dict[str, Any]:
        """
        Execute JavaScript in the page context.
        
        Tool: execute_javascript
        Description: Run JavaScript code in the browser page context
        
        Args:
            page_type: 'tableau' or 'powerbi'
            javascript: JavaScript code to execute
            
        Returns:
            Dictionary with success status and execution result
        """
        logger.info(f"Tool: execute_javascript({page_type})")
        return await self._browser.evaluate(page_type, javascript)

    async def wait_for_element(self, page_type: str, selector: str, timeout: int = 10000) -> Dict[str, Any]:
        """
        Wait for an element to appear on the page.
        
        Tool: wait_for_element
        Description: Wait for specified element to become visible
        
        Args:
            page_type: 'tableau' or 'powerbi'
            selector: CSS selector to wait for
            timeout: Maximum wait time in milliseconds
            
        Returns:
            Dictionary with success status indicating if element appeared
        """
        logger.info(f"Tool: wait_for_element({page_type}, {selector})")
        return await self._browser.wait_for(page_type, selector, timeout)

    async def initialize_browser(self) -> Dict[str, Any]:
        """
        Initialize the browser instance.
        
        Tool: initialize_browser
        Description: Launch browser and prepare for automation
        
        Returns:
            Dictionary with success status
        """
        logger.info("Tool: initialize_browser()")
        success = await self._browser.initialize()
        return {"success": success, "is_initialized": self._browser.is_initialized}

    async def close_browser(self) -> Dict[str, Any]:
        """
        Close the browser instance.
        
        Tool: close_browser
        Description: Close browser and cleanup resources
        
        Returns:
            Dictionary with success status
        """
        logger.info("Tool: close_browser()")
        await self._browser.close()
        return {"success": True, "is_initialized": self._browser.is_initialized}

    def get_tool_definitions(self) -> list:
        """
        Get list of all available tool definitions for MCP registration.
        
        Returns:
            List of tool definition dictionaries
        """
        return [
            {
                "name": "initialize_browser",
                "description": "Launch browser and prepare for automation",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },
            {
                "name": "navigate_to_url",
                "description": "Navigate browser to specified URL for Tableau or Power BI report",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "The URL to navigate to"
                        },
                        "page_type": {
                            "type": "string",
                            "enum": ["tableau", "powerbi"],
                            "description": "Type of report page (tableau or powerbi)"
                        },
                        "timeout": {
                            "type": "integer",
                            "description": "Maximum wait time in milliseconds",
                            "default": 60000
                        }
                    },
                    "required": ["url"]
                }
            },
            {
                "name": "take_screenshot",
                "description": "Capture screenshot of current Tableau or Power BI report page",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "page_type": {
                            "type": "string",
                            "enum": ["tableau", "powerbi"],
                            "description": "Type of report page"
                        },
                        "name": {
                            "type": "string",
                            "description": "Optional name prefix for screenshot file"
                        }
                    },
                    "required": ["page_type"]
                }
            },
            {
                "name": "get_page_snapshot",
                "description": "Get accessibility tree snapshot for analyzing page structure",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "page_type": {
                            "type": "string",
                            "enum": ["tableau", "powerbi"],
                            "description": "Type of report page"
                        }
                    },
                    "required": ["page_type"]
                }
            },
            {
                "name": "hover_element",
                "description": "Hover over page element to reveal tooltip or additional data",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "page_type": {
                            "type": "string",
                            "enum": ["tableau", "powerbi"],
                            "description": "Type of report page"
                        },
                        "selector": {
                            "type": "string",
                            "description": "CSS selector of element to hover over"
                        },
                        "timeout": {
                            "type": "integer",
                            "description": "Maximum wait time in milliseconds",
                            "default": 5000
                        }
                    },
                    "required": ["page_type", "selector"]
                }
            },
            {
                "name": "click_element",
                "description": "Click on page element (button, filter, visual, etc.)",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "page_type": {
                            "type": "string",
                            "enum": ["tableau", "powerbi"],
                            "description": "Type of report page"
                        },
                        "selector": {
                            "type": "string",
                            "description": "CSS selector of element to click"
                        },
                        "timeout": {
                            "type": "integer",
                            "description": "Maximum wait time in milliseconds",
                            "default": 5000
                        }
                    },
                    "required": ["page_type", "selector"]
                }
            },
            {
                "name": "execute_javascript",
                "description": "Run JavaScript code in the browser page context",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "page_type": {
                            "type": "string",
                            "enum": ["tableau", "powerbi"],
                            "description": "Type of report page"
                        },
                        "javascript": {
                            "type": "string",
                            "description": "JavaScript code to execute"
                        }
                    },
                    "required": ["page_type", "javascript"]
                }
            },
            {
                "name": "wait_for_element",
                "description": "Wait for specified element to become visible",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "page_type": {
                            "type": "string",
                            "enum": ["tableau", "powerbi"],
                            "description": "Type of report page"
                        },
                        "selector": {
                            "type": "string",
                            "description": "CSS selector to wait for"
                        },
                        "timeout": {
                            "type": "integer",
                            "description": "Maximum wait time in milliseconds",
                            "default": 10000
                        }
                    },
                    "required": ["page_type", "selector"]
                }
            },
            {
                "name": "close_browser",
                "description": "Close browser and cleanup resources",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            }
        ]
