# migration-validation-mcp

Python MCP server providing the **domain tools** for Tableau → Power BI
migration validation. Browser automation lives in the official
[Playwright MCP](https://github.com/microsoft/playwright-mcp) server — this
server only owns what Playwright cannot: the validation rules.

## Tools

| Tool | Purpose |
|------|---------|
| `compare_values` | Compare rendered value pairs with tolerance rules (numbers ≤1%, percentages ≤1pt, text case-insensitive, dates normalized) |
| `compare_visuals` | Compare two matched visuals data-point by data-point |
| `generate_validation_report` | Render all comparisons into a Markdown report in `validation-reports/` |
| `health_check` | Server liveness probe |

## Layout

```
├── main.py                    # entry point → src/server.py
├── scripts/authenticate.py    # one-time login capture → auth-state.json
├── src/
│   ├── server.py              # MCP protocol wiring (list_tools / call_tool)
│   ├── config/                # settings (env/.env driven) + logging
│   ├── models/                # Pydantic domain models
│   │   ├── visual.py          #   Visual, DataPoint, Platform, VisualType
│   │   ├── comparison.py      #   ValueComparison, VisualComparison, status
│   │   └── report.py          #   ValidationReport, ReportSummary
│   ├── services/              # business logic (no MCP, no I/O with agent)
│   │   ├── comparator.py      #   ValueComparator — the tolerance rules
│   │   └── report_builder.py  #   MarkdownReportBuilder
│   └── tools/                 # MCP tool layer
│       ├── registry.py        #   ToolSpec — schema derived from Pydantic
│       └── validation_tools.py#   ValidationToolbox — tool handlers
└── tests/                     # pytest unit tests for the services
```

Layering rule: `server.py → tools → services → models`. Tool JSON schemas
are generated from the Pydantic input models, so schema, validation, and
handler signatures cannot drift apart.

## Develop

```bash
uv sync                 # install deps
uv run pytest           # run unit tests
uv run migration-validation-mcp   # start the server (stdio) manually
```

Configuration is environment-driven — copy `.env.example` to `.env` to
override tolerances or output directories.
