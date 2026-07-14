"""Interactive one-time sign-in to capture an authenticated browser session.

Private Power BI reports (``app.powerbi.com/groups/...``) and Tableau Server /
Tableau Cloud reports sit behind a login wall. Run this ONCE on a machine with
a display, from the ``migration-validation-mcp`` directory:

    uv run python scripts/authenticate.py

A real Microsoft Edge window opens. Sign in to Power BI (and Tableau if your
reports need it), navigate until you can actually see your report content,
then return to this terminal and press Enter. The session (cookies +
localStorage) is saved to ``auth-state.json``.

The shared MCP configs launch Playwright through
``scripts/run-playwright-mcp.mjs`` (repo root), which passes this file via
``--storage-state`` automatically — no config editing needed. Restart the MCP
servers (reload the VS Code window / restart Claude Code) after capturing so
the new session is picked up. Validation runs then load private reports
without hitting the sign-in page — and without the agent stalling mid-run on
an Authenticator prompt.

Uses the ``msedge`` channel so the captured session matches the browser
validation runs use — useful when your org's conditional access / SSO is tied
to a specific browser.

Re-run this whenever the saved session expires (you'll see the login wall again).
"""

import asyncio

from playwright.async_api import async_playwright

from src.config.settings import settings

# Where to land first so you can sign in.
POWERBI_URL = "https://app.powerbi.com/"

MFA_HELP = """
 If sign-in asks you to APPROVE ON YOUR PHONE (Microsoft Authenticator
 number matching):
   - The screen shows a 2-digit number. Open Authenticator and enter it.
   - Notification never arrived? Open the Authenticator app MANUALLY and
     pull down to refresh — the pending request shows up there even when
     the push notification fails to deliver.
   - Still stuck? On the sign-in page choose "Use your password instead"
     or "Sign in another way" and pick a different method.
"""


def _summarize_capture(state: dict) -> list[str]:
    """Report which platforms the captured cookies actually cover."""
    domains = {c.get("domain", "") for c in state.get("cookies", [])}

    def covers(*fragments: str) -> bool:
        return any(f in d for d in domains for f in fragments)

    lines = []
    lines.append(
        " [ok] Power BI / Microsoft session captured"
        if covers("powerbi.com", "microsoftonline.com", "microsoft.com")
        else " [!!] No Power BI cookies found - private Power BI reports will still show a login wall"
    )
    lines.append(
        " [ok] Tableau session captured"
        if covers("tableau.com", "online.tableau.com")
        else " [--] No Tableau cookies (fine if you only validate Tableau Public / already-signed-in Tableau Server)"
    )
    return lines


async def main() -> None:
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=False, channel="msedge")
        # Resume the previous session if one exists so re-auth is usually
        # just a click-through instead of a full credential + MFA round.
        storage_state = (
            str(settings.auth_state_path) if settings.auth_state_path.exists() else None
        )
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            storage_state=storage_state,
        )
        page = await context.new_page()
        await page.goto(POWERBI_URL)

        print("\n" + "=" * 64)
        print(" A browser window has opened.")
        print()
        print(" 1. Sign in to Power BI and open a report you can see.")
        print(" 2. Tableau Server / Tableau Cloud reports too? Open a NEW TAB")
        print("    in the SAME window, go to your Tableau site, and sign in")
        print("    there as well (skip for Tableau Public - no login needed).")
        print(" 3. Come back here and press Enter to save the session.")
        print(MFA_HELP)
        print("=" * 64)
        input("\n Press Enter once you are signed in and can see the report(s)... ")

        state = await context.storage_state(path=str(settings.auth_state_path))
        print(f"\n Saved authenticated session to '{settings.auth_state_path}'.")
        for line in _summarize_capture(state):
            print(line)
        print("\n Restart the MCP servers (reload VS Code window / restart Claude")
        print(" Code) so the Playwright server picks up the new session.")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
