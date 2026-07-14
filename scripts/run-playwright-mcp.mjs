// Launches the Playwright MCP server with the captured auth session attached.
//
// Why this wrapper exists: Playwright errors out if the --storage-state file
// is missing, so committing that flag directly in .mcp.json used to break
// fresh clones (auth-state.json is personal and gitignored). This wrapper
// guarantees the file exists — writing an EMPTY session for unauthenticated
// (public-report) use — which makes the flag safe to keep in the shared
// configs. Anyone who runs migration-validation-mcp/scripts/authenticate.py
// gets their private-report session picked up automatically on the next
// MCP server start; everyone else keeps working against public reports.
//
// All paths passed to npx are relative to the repo root (set as cwd below)
// so the command line stays free of user-specific paths and spaces.

import { existsSync, writeFileSync } from "node:fs";
import { spawn } from "node:child_process";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const repoRoot = dirname(dirname(fileURLToPath(import.meta.url)));
const authStateRelative = join("migration-validation-mcp", "auth-state.json");
const authStateAbsolute = join(repoRoot, authStateRelative);

if (!existsSync(authStateAbsolute)) {
  writeFileSync(
    authStateAbsolute,
    JSON.stringify({ cookies: [], origins: [] }, null, 2) + "\n",
  );
}

const npxArgs = [
  "@playwright/mcp@latest",
  "--browser=msedge",
  "--viewport-size=1920x1080",
  "--output-dir=migration-validation-mcp/validation-screenshots",
  `--storage-state=${authStateRelative.replaceAll("\\", "/")}`,
];

// npx is npx.cmd on Windows, which spawn() can only run through cmd.exe.
const child =
  process.platform === "win32"
    ? spawn("cmd.exe", ["/c", "npx", ...npxArgs], {
        cwd: repoRoot,
        stdio: "inherit",
      })
    : spawn("npx", npxArgs, { cwd: repoRoot, stdio: "inherit" });

child.on("error", (err) => {
  console.error(`Failed to launch Playwright MCP: ${err.message}`);
  process.exit(1);
});
child.on("exit", (code) => process.exit(code ?? 0));
