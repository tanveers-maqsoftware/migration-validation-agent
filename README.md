# Migration Validation Agent

Validates **Tableau → Power BI** dashboard migrations by comparing what is
*visibly rendered in the browser* on both platforms. You give an LLM agent two
report URLs; it drives a real browser over both reports, extracts every visual,
compares the values, and writes a Markdown validation report.

## Where does a validation run start?

There is no Python `main()` that takes the URLs. The starting point is a
**chat message to the agent**:

1. Open this repository in VS Code (Copilot custom agent) or Claude Code.
   Both MCP servers below are registered automatically via
   [.vscode/mcp.json](.vscode/mcp.json) / [.mcp.json](.mcp.json).
2. Invoke the validation agent/skill and paste the two URLs:
   - VS Code: the custom agent in [.github/agents/tableau-powerbi-validation.agent.md](.github/agents/tableau-powerbi-validation.agent.md)
   - Claude Code: the skill in [.claude/skills/tableau-powerbi-validation/SKILL.md](.claude/skills/tableau-powerbi-validation/SKILL.md)
3. The agent works autonomously: navigate → extract visuals → compare →
   report. Outputs land in `validation-screenshots/` and `validation-reports/`.

## The three moving parts

| Part | Role | Where |
|------|------|-------|
| **Agent playbook** (markdown) | The methodology: how to find visuals, hover for tooltips, scroll tables, match visuals across platforms | `.github/agents/`, `.claude/skills/` |
| **Playwright MCP** (official, `npx @playwright/mcp`) | The browser "hands": `browser_navigate`, `browser_snapshot`, `browser_hover`, `browser_click`, `browser_evaluate`, `browser_take_screenshot`, … | registered in `.mcp.json` — no code in this repo |
| **migration-validation MCP** (Python) | Deterministic domain tools: `compare_values`, `compare_visuals`, `generate_validation_report`, `health_check` | [migration-validation-mcp/](migration-validation-mcp/) |

The LLM agent orchestrates: it reads the playbook and calls tools from both
MCP servers one step at a time. Browser automation is deliberately **not**
implemented in this repo — the official Playwright MCP server does it better.

## Repository layout

```
├── .mcp.json                  # MCP servers for Claude Code
├── .vscode/mcp.json           # MCP servers for VS Code
├── .github/agents/            # VS Code custom agent playbook
├── .claude/skills/            # Claude Code skill (same methodology)
├── Plans/                     # planning documents
└── migration-validation-mcp/  # Python MCP server (domain tools) — see its README
```

## Prerequisites

- Node.js (for `npx @playwright/mcp`)
- [uv](https://docs.astral.sh/uv/) + Python 3.12 (for the domain server)
- For private reports: run `uv run python scripts/authenticate.py` inside
  `migration-validation-mcp/` once to capture a login session, then add
  `--storage-state=migration-validation-mcp/auth-state.json` to the
  playwright server args in `.mcp.json`.
