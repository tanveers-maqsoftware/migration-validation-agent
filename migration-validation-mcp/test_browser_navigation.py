"""
Test script for basic browser navigation and automation.

This script tests the core browser automation capabilities:
- Browser initialization
- URL navigation
- Screenshot capture
- Page snapshot
- Browser cleanup
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from services.browser_automation import BrowserAutomationService
from config.logging_config import logger


async def test_browser_navigation():
    """Test basic browser navigation and screenshot capture."""
    browser_service = BrowserAutomationService()
    
    try:
        # Test 1: Initialize browser
        logger.info("Test 1: Initializing browser...")
        await browser_service.initialize()
        logger.info("✓ Browser initialized successfully")
        
        # Test 2: Navigate to a simple test URL
        test_url = "https://example.com"
        logger.info(f"Test 2: Navigating to {test_url}...")
        await browser_service.navigate(test_url, page_type="tableau")
        logger.info("✓ Navigation successful")

        # Test 3: Take screenshot
        logger.info("Test 3: Taking screenshot...")
        screenshot_path = await browser_service.take_screenshot(
            page_type="tableau",
            name="test_page_test_visual",
        )
        logger.info(f"✓ Screenshot saved to: {screenshot_path}")

        # Test 4: Get page snapshot
        logger.info("Test 4: Getting page snapshot...")
        snapshot = await browser_service.snapshot(page_type="tableau")
        logger.info(f"✓ Page snapshot received (length: {len(str(snapshot))} chars)")
        
        # Test 5: Navigate to Power BI URL
        powerbi_url = "https://app.powerbi.com/view?r=eyJrIjoiMTIzNDU2NzgtYWJjZC1lZmdoLWlqa2wtbW5vcHFyc3R1dnd4In0"
        logger.info(f"Test 5: Navigating to Power BI URL...")
        await browser_service.navigate(powerbi_url, page_type="powerbi")
        logger.info("✓ Power BI navigation successful")

        # Test 6: Take Power BI screenshot
        logger.info("Test 6: Taking Power BI screenshot...")
        screenshot_path = await browser_service.take_screenshot(
            page_type="powerbi",
            name="test_page_test_visual",
        )
        logger.info(f"✓ Power BI screenshot saved to: {screenshot_path}")
        
        # Test 7: Close browser
        logger.info("Test 7: Closing browser...")
        await browser_service.close()
        logger.info("✓ Browser closed successfully")
        
        logger.info("\n" + "=" * 50)
        logger.info("ALL TESTS PASSED ✓")
        logger.info("=" * 50)
        
    except Exception as e:
        logger.error(f"✗ Test failed with error: {e}")
        logger.error(f"Error type: {type(e).__name__}")
        logger.error(f"Error details: {str(e)}")
        
        # Ensure browser is closed even on error
        try:
            await browser_service.close()
            logger.info("Browser closed after error")
        except Exception:
            pass
        
        raise


if __name__ == "__main__":
    logger.info("Starting browser navigation tests...")
    logger.info("=" * 50)
    
    # Run the test
    asyncio.run(test_browser_navigation())