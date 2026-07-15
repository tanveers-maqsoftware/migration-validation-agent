# Migration Validation Agent

Validates **Tableau → Power BI** dashboard migrations by comparing what is
*visibly rendered in the browser* on both platforms. You give an LLM agent two
report URLs; it drives a real browser over both reports, extracts every visual,
compares the values, and writes a Markdown validation report.

No Python `main()` takes the URLs — the starting point is a **chat message to
an AI agent**, which then drives everything else autonomously.

---

## Quick Start (new machine, first time)

### 1. Prerequisites — must already be on your machine

Nothing below is project-specific; if you already do dev work on this
machine, you probably have all of it.

| Requirement | Why | Check it |
|---|---|---|
| **Node.js** | Runs `npx @playwright/mcp` (the browser automation server) | `node --version` |
| **[uv](https://docs.astral.sh/uv/)** | Manages the Python server's venv + dependencies | `uv --version` |
| **Microsoft Edge** | The agent drives Edge specifically (`--browser=msedge`) | Installed by default on Windows |
| **VS Code + GitHub Copilot Chat**, *or* **Claude Code** | The chat host that runs the agent and talks to the MCP servers | Either works — see step 3 |

Python 3.12 itself does **not** need to be pre-installed — `uv` will download
a matching interpreter automatically if none is found.

### 2. Clone and open

```powershell
git clone <this-repo-url>
cd migration-validation-agent
code .
```

That's it — no `npm install`, no `pip install`, no build step. The two MCP
servers this project needs are declared in [.mcp.json](.mcp.json) (Claude
Code) / [.vscode/mcp.json](.vscode/mcp.json) (VS Code) and install themselves
automatically the first time they're launched:

- `npx @playwright/mcp@latest` downloads and caches itself on first run.
- `uv run migration-validation-mcp` creates the venv and installs Python
  dependencies from `uv.lock` automatically.

### 3. Open a chat and approve the MCP servers

- **Claude Code**: open a new chat in this workspace.
- **VS Code Copilot Chat**: open the Chat panel, pick the
  **tableau-powerbi-validation** custom agent from the agent dropdown.

The first time either host tries to launch the two MCP servers, it shows a
**trust/approval prompt** ("Allow this server to run?") — click **Allow** for
both `playwright` and `migration-validation`. This only happens once per
workspace.

### 4. Run a validation

Paste both report URLs in one message:

```
Validate this migration.
Tableau: <your Tableau Public / Server URL>
Power BI: <your Power BI report URL>
```

The agent takes over completely from here — no further input needed. It
navigates both reports, extracts every visual, matches them across
platforms, compares values, and writes:

- `migration-validation-mcp/validation-reports/Validation_Report_<timestamp>.md`
- `migration-validation-mcp/validation-screenshots/*.png`
- an entry appended to `migration-validation-mcp/harness-log.json`

Open the `.md` report in VS Code's preview to see it with screenshots inline.

### 5. Try it risk-free with public reports first

Public reports need **zero setup** — no sign-in, no extra config. Good first
test:

- Tableau Public: any dashboard under `public.tableau.com/views/...` or
  `public.tableau.com/app/profile/.../viz/...`
- Power BI "Publish to web": a link like `app.powerbi.com/view?r=...`

If you paste two *unrelated* public reports just to test the pipeline,
expect most visuals to come back "Unmatched" — that's correct behavior, not
a bug. It's validating the pipeline, not migration accuracy.

---

## Private reports (auth setup — one command, per person)

Private Power BI (`app.powerbi.com/groups/...`) or Tableau Server/Cloud
reports sit behind your org's sign-in. Capturing a session is a **one-time,
per-machine, per-person** step:

1. ```powershell
   cd migration-validation-mcp
   uv run python scripts/authenticate.py
   ```
   A real Edge window opens. Sign in with your own account (approve the MFA
   prompt on your phone — the script prints what to do if the Authenticator
   notification doesn't arrive), open a report you can see, and — if your
   Tableau reports are on Tableau Server/Cloud rather than Tableau Public —
   also open your Tableau site in a second tab and sign in there. Then return
   to the terminal and press Enter. This saves `auth-state.json` (gitignored —
   it holds your session cookies and must never be committed or shared).

2. **Restart the MCP servers** (reload the VS Code window / restart Claude
   Code). That's it — no config editing. The shared configs launch Playwright
   through [migration-validation-mcp/scripts/run_playwright_mcp.py](migration-validation-mcp/scripts/run_playwright_mcp.py),
   which passes `--storage-state=migration-validation-mcp/auth-state.json`
   automatically. On machines that never ran `authenticate.py`, the wrapper
   writes an *empty* placeholder session, so fresh clones keep working for
   public reports (no more `ENOENT ... auth-state.json` startup crash).

Auth sessions are per-person by design: even if `auth-state.json` were
shared, it would carry *your* identity and permissions, not a teammate's.
Everyone who needs private reports runs their own `authenticate.py`.

**Why do this instead of letting the agent sign in mid-run?** Without a saved
session, the agent hits the login wall during validation and has to drive MFA
interactively — sending an Authenticator push and waiting on your approval,
which stalls the run (and fails outright when the notification doesn't
arrive). With the session captured up front, runs stay fully autonomous. If a
run does hit a login wall (expired session), the agent playbook now surfaces
the MFA number immediately, waits at most 2 minutes, then marks that platform
"Authentication required" and tells you to re-run `authenticate.py`.

---

## Testing the tools directly (optional)

A full agent run takes several minutes. To sanity-check just the Python
server's tools (`compare_values`, `compare_visuals`, `generate_validation_report`,
`record_validation_run`, `get_validation_history`) in seconds, use the
[MCP Inspector](https://github.com/modelcontextprotocol/inspector):

```powershell
cd migration-validation-mcp
npx @modelcontextprotocol/inspector uv run migration-validation-mcp
```

Opens a browser UI at `localhost:6274` — click **Connect**, then **List
Tools**, then try a tool with sample input. For nested-object inputs
(`compare_visuals`), click **Switch to JSON** on each object field and paste
a JSON blob rather than fighting the generated form.

To test the browser side (Playwright MCP) the same way:

```powershell
npx @modelcontextprotocol/inspector npx @playwright/mcp@latest --browser=msedge
```

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `ENOENT ... auth-state.json` at startup | Playwright MCP was launched directly with `--storage-state` instead of through the wrapper | Make sure the `playwright` server in `.mcp.json`/`.vscode/mcp.json` runs `uv run python migration-validation-mcp/scripts/run_playwright_mcp.py` — the wrapper creates a placeholder session file when none exists |
| Screenshots don't render in the `.md` report | Playwright MCP and the Python server were launched with different working directories, so relative image paths don't resolve | Confirm `--output-dir=migration-validation-mcp/validation-screenshots` in `migration-validation-mcp/scripts/run_playwright_mcp.py` (already fixed in this repo) |
| VS Code Copilot Chat: *"No utility model is configured for 'copilot-utility-small' while the selected main agent model is BYOK"* | Your main chat model is a custom/BYOK provider (e.g. an internal org gateway); Copilot Chat also needs a small "utility model" mapped for internal tasks, and none is set | Configure a utility model via Command Palette → "GitHub Copilot: Manage Models", or ask whoever administers your org's BYOK provider. Unrelated to this repo — Claude Code doesn't need this at all |
| MCP Inspector: `-32602 Invalid request parameters` on a nested-object tool (e.g. `compare_visuals`) | A client-side form-assembly quirk in the Inspector UI for deeply nested JSON, not a server bug | Click **Switch to JSON** on the *entire* field again to force a resync, or use **Copy Input** to see exactly what was about to be sent |
| Power BI or Tableau report shows a sign-in page mid-run | No session captured yet, or the captured session expired | Run `migration-validation-mcp/scripts/authenticate.py` again (see above), then restart the MCP servers |
| Agent stalls on "Approve sign in" / Authenticator number prompt during a run | Same as above — the agent fell through to interactive MFA | Approve within 2 minutes if you can (no push? open Authenticator manually and pull to refresh); otherwise let the run finish, then run `migration-validation-mcp/scripts/authenticate.py` and re-run the validation |
| Most visuals report "Unmatched" | The two report URLs aren't actually a migrated pair (different content) | Expected — use a real before/after pair for a meaningful accuracy result |

---

## The three moving parts

| Part | Role | Where |
|------|------|-------|
| **Agent playbook** (markdown) | The methodology: how to find visuals, hover for tooltips, scroll tables, match visuals across platforms, validate filters and drill-throughs | `.github/agents/`, `.claude/skills/` |
| **Playwright MCP** (official, `npx @playwright/mcp`) | The browser "hands": `browser_navigate`, `browser_snapshot`, `browser_hover`, `browser_click`, `browser_evaluate`, `browser_take_screenshot`, … | registered in `.mcp.json` — no code in this repo |
| **migration-validation MCP** (Python) | Deterministic domain tools: `compare_values`, `compare_visuals`, `generate_validation_report`, `record_validation_run`, `get_validation_history`, `health_check` | [migration-validation-mcp/](migration-validation-mcp/) |

The LLM agent orchestrates: it reads the playbook and calls tools from both
MCP servers one step at a time. Browser automation is deliberately **not**
implemented in this repo — the official Playwright MCP server does it better.

See [HLD.md](HLD.md) for the full runtime flow, comparison rules, and design decisions.

## Repository layout

```
├── .mcp.json                  # MCP servers for Claude Code
├── .vscode/mcp.json           # MCP servers for VS Code
├── .github/agents/            # VS Code custom agent playbook
├── .github/workflows/         # CI — tests + lint on every push/PR
├── .claude/skills/            # Claude Code skill (same methodology)
├── HLD.md                     # high-level design: architecture, runtime flow, comparison rules
└── migration-validation-mcp/  # Python MCP server (domain tools) — see its README
                                #   scripts/ — authenticate.py + run_playwright_mcp.py
```
