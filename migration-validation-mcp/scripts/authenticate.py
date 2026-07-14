"""Interactive one-time sign-in to capture an authenticated browser session.

Private Power BI reports (``app.powerbi.com/groups/...``) and Tableau Server
sit behind a login wall. Run this ONCE on a machine with a display, from the
``migration-validation-mcp`` directory:

    uv run python scripts/authenticate.py

A real Microsoft Edge window opens. Sign in to Power BI (and Tableau Server if
you need it), navigate until you can actually see your report content, then
return to this terminal and press Enter. The session (cookies + localStorage)
is saved to ``auth-state.json`` and passed to the Playwright MCP server via
its ``--storage-state`` flag (see ``.mcp.json``), so validation runs no longer
hit the sign-in page.

Uses the ``msedge`` channel so the captured session matches the browser
validation runs use (see ``--browser=msedge`` in ``.mcp.json``) — useful when
your org's conditional access / SSO is tied to a specific browser.

Re-run this whenever the saved session expires (you'll see the login wall again).
"""

import asyncio

from playwright.async_api import async_playwright

from src.config.settings import settings

# Where to land first so you can sign in. Change if you only use Tableau Server.
LOGIN_START_URL = "https://app.powerbi.com/"


async def main() -> None:
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=False, channel="msedge")
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
        )
        page = await context.new_page()
        await page.goto(LOGIN_START_URL)

        print("\n" + "=" * 64)
        print(" A browser window has opened.")
        print(" 1. Sign in to Power BI (and Tableau Server, if you use it).")
        print(" 2. Open your report and confirm you can see its content.")
        print(" 3. Come back here and press Enter to save the session.")
        print("=" * 64)
        input("\n Press Enter once you are signed in and can see the report... ")

        await context.storage_state(path=str(settings.auth_state_path))
        print(f"\n Saved authenticated session to '{settings.auth_state_path}'.")
        print(" Playwright MCP will now load private reports without a login wall.")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
