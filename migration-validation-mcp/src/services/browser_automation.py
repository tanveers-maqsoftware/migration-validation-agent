"""
Browser automation service for Tableau→Power BI validation.

This is the ONLY layer that talks to Playwright. It owns one Chromium browser
with a single shared context holding two tabs — one for the Tableau report,
one for the Power BI report — so the agent can flip between platforms without
re-authenticating or re-loading.

Everything above this layer (tools/browser_tools.py, server.py) is protocol
plumbing; everything the browser actually *does* happens here.

Lifecycle of a validation run:
    initialize()  → launch Chromium, restore saved auth session if present
    navigate()    → open a report URL in the tab for that platform
    hover/click/evaluate/wait_for/snapshot/take_screenshot → extraction loop
    close()       → tear everything down
"""

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from playwright.async_api import Browser, BrowserContext, Page, Playwright, async_playwright

from src.config.logging_config import logger
from src.config.settings import settings


class BrowserAutomationService:
    """
    Manages one Chromium browser with two long-lived tabs (pages):
    one for Tableau, one for Power BI.

    Every public method takes a ``page_type`` ("tableau" | "powerbi") that
    selects which tab the action targets. Methods never raise to the caller —
    they return ``{"success": bool, ...}`` dicts so the LLM agent driving them
    can read failures and decide how to recover.
    """

    def __init__(self):
        # Playwright object tree: playwright → browser → context → pages.
        # All start as None; initialize() populates them.
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._tableau_page: Optional[Page] = None
        self._powerbi_page: Optional[Page] = None
        self._is_initialized: bool = False
        
        # Screenshot output directory
        self.screenshot_dir = Path("validation-screenshots")
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info("BrowserAutomationService initialized")

    # ------------------------------------------------------------------
    # Lifecycle: initialize() ... close()
    # ------------------------------------------------------------------

    async def initialize(self) -> bool:
        """Launch browser and create context for browser automation."""
        try:
            logger.info("Initializing browser automation...")
            
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(
                headless=settings.PLAYWRIGHT_HEADLESS,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                ]
            )
            
            context_kwargs: Dict[str, Any] = {
                "viewport": {"width": 1920, "height": 1080},
                "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            }

            # Reuse a previously captured authenticated session (see authenticate.py)
            # so private Power BI / Tableau Server reports load without a login wall.
            auth_state = Path(settings.AUTH_STATE_PATH)
            if auth_state.exists():
                context_kwargs["storage_state"] = str(auth_state)
                logger.info(f"Loading saved auth session from {auth_state}")

            self._context = await self._browser.new_context(**context_kwargs)
            
            # Enable extra HTTP headers for better compatibility
            await self._context.set_extra_http_headers({
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            })
            
            self._is_initialized = True
            logger.info("Browser automation initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize browser: {e}")
            await self.close()
            return False

    async def navigate(self, url: str, page_type: str = "tableau", timeout: int = 60000) -> Dict[str, Any]:
        """
        Navigate to a URL and wait for page load.
        
        Args:
            url: The URL to navigate to
            page_type: 'tableau' or 'powerbi' - determines which page to use
            timeout: Maximum wait time in milliseconds
            
        Returns:
            Dictionary with navigation result and page info
        """
        try:
            logger.info(f"Navigating to {page_type} URL: {url}")
            
            # Get or create page for this type
            page = self._get_page_for_type(page_type)
            if page is None:
                page = await self._create_new_page(page_type)
            
            # Navigate to URL. Use "domcontentloaded" rather than "networkidle":
            # dashboards like Tableau Public hold connections open and never go idle,
            # which made the strict wait time out on otherwise-healthy pages.
            response = await page.goto(url, wait_until="domcontentloaded", timeout=timeout)

            # Dismiss cookie/consent banners and prompts that overlay the report.
            await self._dismiss_overlays(page)

            # Platform-specific wait conditions
            if page_type == "tableau":
                await self._wait_for_tableau_load(page)
            elif page_type == "powerbi":
                await self._wait_for_powerbi_load(page)
            
            # Capture initial screenshot
            screenshot_path = await self._capture_screenshot(page, f"{page_type}_initial")
            
            logger.info(f"Successfully navigated to {page_type} URL")
            
            return {
                "success": True,
                "url": url,
                "status": response.status if response else 200,
                "title": await page.title(),
                "screenshot": str(screenshot_path),
            }
            
        except Exception as e:
            logger.error(f"Navigation failed for {url}: {e}")
            return {
                "success": False,
                "url": url,
                "error": str(e),
            }

    async def snapshot(self, page_type: str = "tableau") -> Dict[str, Any]:
        """
        Capture accessibility snapshot of the current page.
        
        Args:
            page_type: 'tableau' or 'powerbi'
            
        Returns:
            Dictionary with page accessibility tree
        """
        try:
            page = self._get_page_for_type(page_type)
            if not page:
                return {"success": False, "error": f"No {page_type} page available"}
            
            # Get accessibility snapshot
            accessibility_tree = await page.accessibility.snapshot(
                interesting_only=True
            )
            
            # Get page URL and title
            url = page.url
            title = await page.title()
            
            logger.info(f"Captured snapshot for {page_type}: {title}")
            
            return {
                "success": True,
                "url": url,
                "title": title,
                "accessibility_tree": accessibility_tree,
            }
            
        except Exception as e:
            logger.error(f"Snapshot failed for {page_type}: {e}")
            return {"success": False, "error": str(e)}

    async def hover(self, page_type: str, selector: str, timeout: int = 5000) -> Dict[str, Any]:
        """
        Hover over an element to reveal tooltips or additional info.
        
        Args:
            page_type: 'tableau' or 'powerbi'
            selector: CSS selector or XPath of element to hover
            timeout: Maximum wait time
            
        Returns:
            Dictionary with hover result
        """
        try:
            page = self._get_page_for_type(page_type)
            if not page:
                return {"success": False, "error": f"No {page_type} page available"}
            
            # Wait for element to be visible
            element = await page.wait_for_selector(selector, state="visible", timeout=timeout)
            
            if not element:
                return {"success": False, "error": f"Element not found: {selector}"}
            
            # Hover over element
            await element.hover()
            
            # Wait for tooltip to appear (platform-specific)
            if page_type == "tableau":
                tooltip_selector = ".tab-tooltip"
            else:  # powerbi
                tooltip_selector = ".tooltip-container, .enhancedTooltips"
            
            # Wait briefly for tooltip
            await page.wait_for_timeout(500)
            
            # Try to extract tooltip content
            tooltip_content = None
            try:
                tooltip = await page.query_selector(tooltip_selector)
                if tooltip:
                    tooltip_content = await tooltip.inner_text()
            except Exception:
                pass
            
            return {
                "success": True,
                "selector": selector,
                "tooltip": tooltip_content,
            }
            
        except Exception as e:
            logger.error(f"Hover failed for {selector}: {e}")
            return {"success": False, "error": str(e)}

    async def click(self, page_type: str, selector: str, timeout: int = 5000) -> Dict[str, Any]:
        """
        Click on an element.
        
        Args:
            page_type: 'tableau' or 'powerbi'
            selector: CSS selector or XPath of element to click
            timeout: Maximum wait time
            
        Returns:
            Dictionary with click result
        """
        try:
            page = self._get_page_for_type(page_type)
            if not page:
                return {"success": False, "error": f"No {page_type} page available"}
            
            # Wait for element to be clickable
            element = await page.wait_for_selector(selector, state="visible", timeout=timeout)
            
            if not element:
                return {"success": False, "error": f"Element not found: {selector}"}
            
            # Click element
            await element.click()
            
            # Wait for any resulting navigation or update
            await page.wait_for_timeout(1000)
            
            return {
                "success": True,
                "selector": selector,
            }
            
        except Exception as e:
            logger.error(f"Click failed for {selector}: {e}")
            return {"success": False, "error": str(e)}

    async def evaluate(self, page_type: str, javascript: str) -> Dict[str, Any]:
        """
        Execute JavaScript in the context of the page.
        
        Args:
            page_type: 'tableau' or 'powerbi'
            javascript: JavaScript code to execute
            
        Returns:
            Dictionary with evaluation result
        """
        try:
            page = self._get_page_for_type(page_type)
            if not page:
                return {"success": False, "error": f"No {page_type} page available"}
            
            # Execute JavaScript
            result = await page.evaluate(javascript)
            
            return {
                "success": True,
                "result": result,
            }
            
        except Exception as e:
            logger.error(f"Evaluate failed: {e}")
            return {"success": False, "error": str(e)}

    async def wait_for(self, page_type: str, selector: str, timeout: int = 10000) -> Dict[str, Any]:
        """
        Wait for an element to appear on the page.
        
        Args:
            page_type: 'tableau' or 'powerbi'
            selector: CSS selector to wait for
            timeout: Maximum wait time in milliseconds
            
        Returns:
            Dictionary with wait result
        """
        try:
            page = self._get_page_for_type(page_type)
            if not page:
                return {"success": False, "error": f"No {page_type} page available"}
            
            # Wait for element
            element = await page.wait_for_selector(selector, state="visible", timeout=timeout)
            
            return {
                "success": element is not None,
                "selector": selector,
            }
            
        except Exception as e:
            logger.error(f"Wait for failed: {selector} - {e}")
            return {"success": False, "error": str(e)}

    async def take_screenshot(self, page_type: str, name: Optional[str] = None) -> Dict[str, Any]:
        """
        Take a screenshot of the current page.
        
        Args:
            page_type: 'tableau' or 'powerbi'
            name: Optional name for the screenshot file
            
        Returns:
            Dictionary with screenshot path
        """
        try:
            page = self._get_page_for_type(page_type)
            if not page:
                return {"success": False, "error": f"No {page_type} page available"}

            screenshot_path = await self._capture_screenshot(page, name or f"{page_type}_screenshot")

            return {
                "success": True,
                "path": str(screenshot_path),
            }
            
        except Exception as e:
            logger.error(f"Screenshot failed: {e}")
            return {"success": False, "error": str(e)}

    async def close(self) -> None:
        """Close browser and cleanup resources."""
        try:
            if self._context:
                await self._context.close()
            if self._browser:
                await self._browser.close()
            if self._playwright:
                await self._playwright.stop()
            
            self._is_initialized = False
            logger.info("Browser automation closed")
            
        except Exception as e:
            logger.error(f"Error closing browser: {e}")

    async def _dismiss_overlays(self, page: Page) -> None:
        """Best-effort dismissal of cookie/consent banners that overlay the report.

        Tableau Public uses a OneTrust consent modal that injects a moment after
        load, so we actively wait for it. Failures are swallowed — an absent
        banner is the normal case (e.g. the Power BI sign-in page has none).
        """
        # OneTrust consent (Tableau Public and many others) appears shortly after load.
        try:
            button = await page.wait_for_selector(
                "#onetrust-accept-btn-handler", timeout=4000, state="visible"
            )
            if button:
                await button.click(timeout=2000)
                await page.wait_for_timeout(500)
                logger.info("Dismissed cookie consent (OneTrust)")
                return
        except Exception:
            pass

        # Fallback: generic 'Accept all' buttons already present in the DOM.
        fallbacks = [
            "button:has-text('Accept All Cookies')",
            "button:has-text('Accept all')",
            "[aria-label='Accept all cookies']",
        ]
        for selector in fallbacks:
            try:
                element = await page.query_selector(selector)
                if element and await element.is_visible():
                    await element.click(timeout=2000)
                    await page.wait_for_timeout(500)
                    logger.info(f"Dismissed overlay via '{selector}'")
                    return
            except Exception:
                continue

    async def save_auth_state(self) -> str:
        """Persist the current session (cookies + localStorage) to AUTH_STATE_PATH.

        Loaded automatically by initialize() on later runs so signed-in reports
        open without a login wall. Captured interactively via authenticate.py.
        """
        path = settings.AUTH_STATE_PATH
        await self._context.storage_state(path=path)
        logger.info(f"Saved auth session to {path}")
        return path

    def _get_page_for_type(self, page_type: str) -> Optional[Page]:
        """Get existing page for the given type."""
        if page_type == "tableau":
            return self._tableau_page
        elif page_type == "powerbi":
            return self._powerbi_page
        return None

    async def _create_new_page(self, page_type: str) -> Page:
        """Create a new page and assign it to the given type."""
        page = await self._context.new_page()
        
        if page_type == "tableau":
            self._tableau_page = page
        elif page_type == "powerbi":
            self._powerbi_page = page
        
        logger.info(f"Created new page for {page_type}")
        return page

    async def _wait_for_tableau_load(self, page: Page, timeout: int = 15000) -> None:
        """Wait for Tableau-specific load indicators."""
        try:
            # Wait for Tableau viz to be present
            await page.wait_for_selector(".tab-zone, .tab-widget, .viz-preview", timeout=timeout)
            
            # Additional wait for rendering to complete
            await page.wait_for_timeout(2000)
            
        except Exception:
            # If specific selectors not found, just wait a bit
            logger.warning("Tableau load indicators not found, using default wait")
            await page.wait_for_timeout(3000)

    async def _wait_for_powerbi_load(self, page: Page, timeout: int = 15000) -> None:
        """Wait for Power BI-specific load indicators."""
        try:
            # Wait for Power BI visual containers
            await page.wait_for_selector(".visual-container, [role='img']", timeout=timeout)
            
            # Additional wait for rendering
            await page.wait_for_timeout(2000)
            
        except Exception:
            logger.warning("Power BI load indicators not found, using default wait")
            await page.wait_for_timeout(3000)

    async def _capture_screenshot(self, page: Page, name: str) -> Path:
        """Capture a screenshot of the given page and save it to file."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{name}_{timestamp}.png"
        filepath = self.screenshot_dir / filename

        await page.screenshot(path=str(filepath), full_page=True)
        logger.info(f"Screenshot saved: {filepath}")

        return filepath

    @property
    def is_initialized(self) -> bool:
        """Check if browser is initialized."""
        return self._is_initialized
