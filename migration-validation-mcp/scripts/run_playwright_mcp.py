"""Launches the Playwright MCP server with the captured auth session attached.

Why this wrapper exists: Playwright errors out if the --storage-state file is
missing, so committing that flag directly in .mcp.json used to break fresh
clones (auth-state.json is personal and gitignored). This wrapper guarantees
the file exists -- writing an EMPTY session for unauthenticated (public-report)
use -- which makes the flag safe to keep in the shared configs. Anyone who runs
migration-validation-mcp/scripts/authenticate.py gets their private-report
session picked up automatically on the next MCP server start; everyone else
keeps working against public reports.

All paths passed to npx are relative to the repo root (set as cwd below) so
the command line stays free of user-specific paths and spaces.
"""

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
AUTH_STATE_RELATIVE = Path("migration-validation-mcp") / "auth-state.json"
AUTH_STATE_ABSOLUTE = REPO_ROOT / AUTH_STATE_RELATIVE

if not AUTH_STATE_ABSOLUTE.exists():
    AUTH_STATE_ABSOLUTE.write_text(
        json.dumps({"cookies": [], "origins": []}, indent=2) + "\n", encoding="utf-8"
    )

NPX_ARGS = [
    "npx",
    "@playwright/mcp@latest",
    "--browser=msedge",
    "--viewport-size=1920x1080",
    "--output-dir=migration-validation-mcp/validation-screenshots",
    f"--storage-state={AUTH_STATE_RELATIVE.as_posix()}",
]

# npx is npx.cmd on Windows; shell=True resolves it via PATH there. No-op
# difference on POSIX, where npx is found directly without a shell.
try:
    completed = subprocess.run(
        NPX_ARGS, cwd=REPO_ROOT, shell=(sys.platform == "win32")
    )
except OSError as error:
    print(f"Failed to launch Playwright MCP: {error}", file=sys.stderr)
    sys.exit(1)

sys.exit(completed.returncode)
