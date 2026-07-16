# Technical Approach Document (TAD)
## AI-Driven Tableau → Power BI Migration Validation

| | |
|---|---|
| **Project** | Migration Validation Agent |
| **Program scope** | ~150–200 Tableau reports migrated to Power BI |
| **Version** | 1.0 |
| **Date** | 2026-07-16 |
| **Status** | Working draft — capability tags: ✅ Implemented · 🔶 Partial · 🔷 Roadmap |

---

## 1. Purpose

Migration sign-off today depends on humans eyeballing two reports side by
side. That does not scale to 200 reports, and it misses exactly the defects
that matter (a dropped dimension member, a calculated field that silently
didn't migrate). This solution automates rendered-report validation so that
**the only manual input is the two report URLs**:

> *"Validate migration. Tableau Url: `<report url>` and Power BI Url: `<report url>`"*

Everything after that prompt — authentication, discovery, extraction,
comparison, reporting, email delivery, and run history — is automated.

## 2. Solution Architecture

```
User prompt (2 URLs)
        │
        ▼
┌─────────────────────────────────────────────┐
│  AI Orchestrator (Claude Code agent +       │
│  tableau-powerbi-validation skill playbook) │
└──────┬──────────────────────────┬───────────┘
       │                          │
       ▼                          ▼
┌──────────────────┐   ┌──────────────────────────────┐
│ Playwright MCP   │   │ migration-validation MCP     │
│ (browser: eyes & │   │ (ours: deterministic brain)  │
│  hands)          │   │  • compare_values            │
│  • navigate      │   │  • compare_visuals           │
│  • screenshot    │   │  • generate_validation_report│
│  • evaluate DOM  │   │  • send_report_email         │
│  • click/scroll  │   │  • record_validation_run     │
│                  │   │  • get_validation_history    │
└──────────────────┘   └──────────────────────────────┘
       │                          │
       ▼                          ▼
  auth-state.json          validation-reports/ · email
  validation-screenshots/  harness-log.json
```

**Design principle — the agent reads, the rules engine judges.** The LLM does
the fuzzy platform-specific work (finding visuals, triggering tooltips,
scrolling virtualized tables). Every pass/fail verdict is produced by the
deterministic comparator in our MCP server, so two runs on the same data give
identical verdicts. The functional agents in the target architecture
(Metadata Extraction, Screenshot Validation, Filter Validation, Data
Extraction, Variance Analysis, UAT Report Generation) exist today as **phases
of one orchestrated playbook**; they can be split into parallel subagents as
the program scales (§8).

## 3. Authentication Approach ✅

Authentication is resolved **up front for both platforms, before any
validation work begins**, then checked continuously:

1. **Session bootstrap (one-time / on expiry).** `scripts/authenticate.py`
   opens a headed browser; the user signs in to Power BI (and Tableau
   Server/Cloud for private reports) once, completing MFA interactively. The
   resulting cookies + localStorage are saved to **`auth-state.json`**.
2. **Session reuse (every run).** The Playwright MCP server is launched with
   `--storage-state=auth-state.json` (wired by `scripts/run_playwright_mcp.py`),
   so both reports normally open with no login wall. Public Tableau URLs need
   no auth at all.
3. **Auth gate — checked after *every* navigation.** Before extracting
   anything, the agent verifies the page is the report and not
   `login.microsoftonline.com` / a Tableau `/signin` redirect.
4. **Expired session handling.** If a login wall appears: never type
   credentials; if an MFA number-match challenge appears, surface the number
   to the user immediately and poll for at most 2 minutes. If auth still
   fails, that platform is recorded as an explicit FAIL, the other platform
   is still validated, and the final summary tells the user to re-run
   `authenticate.py`. **A report is generated no matter what** — an
   auth-failed run is a reported run, not a silent abort.
5. **Sequential vs parallel.** Today one browser session validates the two
   reports sequentially (Tableau fully extracted, then Power BI) — simplest
   and most reliable with a shared session state. Parallel extraction via two
   browser contexts (and, at program scale, parallel report *pairs* via
   multiple agent workers) is a 🔷 roadmap optimization; the upfront-auth
   design already supports it since both sessions come from the same
   `auth-state.json`.

## 4. End-to-End Validation Flow

**Status at a glance:**

| Step | Status |
|---|---|
| 1. Report Discovery | ✅ Done (DOM-based; API enrichment 🔷 roadmap) |
| 2. Screenshot & Layout Validation | ✅ Done |
| 3. Automated Filter Validation (F0–F7) | ✅ Done |
| 4. UI Data Extraction | ✅ Done (incl. large-table sampling policy) |
| 5. Variance Engine | ✅ Done |
| 6. Drill-through Validation | ✅ Done |
| 7. Export Validation (row-level data diff) | 🔷 Roadmap — opt-in, needs platform API access |
| 8. AI Root Cause Analysis | 🔶 Partial — causes in report notes; structured taxonomy 🔷 roadmap |
| 9. Report Generation, Email & History | ✅ Done |

### Step 1 — Report Discovery ✅ (DOM-based) / 🔷 (API-based)

Input:
```json
{ "tableauUrl": "...", "powerBiUrl": "..." }
```
The agent inventories both reports from the rendered DOM: pages/tabs
(Tableau tab widgets & story points; Power BI page navigation), every visual
container with its type (KPI card, bar/line/pie chart, table, matrix, map),
filters/slicers (Tableau quick filters; Power BI slicers + Filters pane), and
drill paths. Output feeds every later step:

```json
{ "pages": 1, "visuals": 5, "filters": 0, "kpis": 0 }
```

🔷 Roadmap: enrich discovery with the **Tableau Metadata/REST API** and
**Power BI REST/Scanner API** so the inventory includes fields, measures, and
datasource lineage — enabling "expected vs found" visual checks before the
browser even opens.

### Step 2 — Screenshot & Layout Validation ✅

Full-page screenshots of both reports are captured with a per-run `RUN_ID`
prefix (immutable evidence, no cross-run overwrites) and read by the agent's
vision capability. Checked: visual existence on both sides, chart type parity,
titles, axis labels, legends, gross formatting, and **missing/extra visuals**
(reported as unmatched — a finding, never a silent skip). Layout deltas are
recorded as notes; data verdicts come from Steps 4–5, not pixels.

### Step 3 — Automated Filter Validation ✅ (rules F0–F7)

Filters are validated under **definitive rules** (skill Step 7b) so every run
behaves identically:

| Rule | Content |
|---|---|
| **F0 Inventory & match** | Enumerate filters on both platforms, match by normalized field name; filter missing on one side = FAIL; none on both = N/A recorded |
| **F1 Selection budget** | Max 5 filters, first 2 non-default values each, Tableau display order, one filter at a time, never combinations |
| **F2 Baseline** | Record 1–3 prominent values (KPIs → chart total → first table row) *before* applying anything |
| **F3 Identical application** | Platform-specific click mechanics; wait for both re-renders (loading indicators gone + 2 s) |
| **F4 Verify application** | Selection state must show + a baseline value must move; unverified filter = FAIL "did not apply", never a bogus comparison |
| **F5 Compare** | Re-read the same labels on both platforms → `compare_values` with labels like `"Year=2011 · Total Sales"` |
| **F6 Verified reset** | Clear both filters, confirm baseline returns; if not, reload the page before the next filter |
| **F7 Full recording** | One `VisualComparison` per filter ("Filter check: <Field>"), tested and skipped values stated explicitly |

### Step 4 — UI Data Extraction ✅ (the hard part)

All visible values are read exactly as a business user sees them:

- **KPI cards** — direct DOM text.
- **Tables/matrices** — both platforms virtualize (~25 rows in the DOM at a
  time); the agent scrolls the internal containers stepwise and accumulates
  **all** rows, subtotals, and grand totals (demo: 270/270 city rows).
- **Large-table policy (tables can hold millions of rows).** The row count is
  estimated *before* scrolling (`scrollHeight / rowHeight`). Up to ~300 rows
  → full extraction. Above that, full scrolling is never attempted; instead:
  **(1) totals first** — rendered grand totals/subtotals are compared as the
  primary aggregate check; **(2) threshold sampling** — deterministic
  first/middle/last bands of 25 rows each, matched across platforms **by row
  key** (never by position, so sort-order differences can't fake a mismatch);
  **(3) row-count comparison** (estimated counts must agree within 1%); and
  **(4) explicit coverage disclosure** — the report states "totals + 75 of
  ~1.2M rows sampled", and the run history records it under
  `incomplete_items`. A sampled table is never presented as fully verified.
- **Tableau charts** — rendered on `<canvas>`, invisible to scraping: the
  agent dispatches synthetic pointer events at computed coordinates (radial
  multi-radius sweeps for pies) and reads each tooltip.
- **Power BI charts** — values from SVG aria-labels; tooltips triggered with
  the full pointer-event sequence Power BI requires.

🔷 Roadmap fallbacks: platform data APIs (Tableau VizQL data / Power BI
`executeQueries`) for headless value extraction, and OCR as a last resort for
custom visuals that expose nothing programmatic.

### Step 5 — Variance Engine ✅

Every extracted pair is judged by our MCP server (`compare_values` /
`compare_visuals`), never by the model:

```
1. One side missing?   Tableau-only = FAIL "Missing in Power BI" (data lost)
                       Power BI-only = WARNING "Additional in Power BI"
2. Both numeric?       variance = (PBI − Tableau) / |Tableau| × 100
                       0% PASS · ≤0.5% WARNING · >0.5% FAIL
                       (percentages: ≤1.0 point = PASS)
3. Both dates?         same calendar date = PASS
4. Else text           case-insensitive, whitespace-collapsed equality
```

Parsing handles `$/€/£/₹`, thousands separators, K/M/B suffixes
(`2.27M` ↔ `2,268,666.46`), accounting negatives. Bands are configurable per
engagement via `.env` (`NUMERIC_PASS_PCT`, `NUMERIC_WARNING_PCT`,
`PERCENTAGE_TOLERANCE_POINTS`).

Example output:

| KPI | Tableau | Power BI | Variance | Verdict |
|---|---|---|---|---|
| ProductKey 361 | 2,268,666 | 2,268,666.46 | 0.00% | ⚠️ Warning (rounding) |
| ProductKey 359 | 2,594,257 | — | — | ❌ FAIL Missing in Power BI |

### Step 6 — Drill-through Validation ✅

For one representative drillable visual: capture the parent value, drill one
level down on both platforms, compare child values (labels like
`"East → New York · Sales"`), **verify children sum to the parent**, drill
back up. Drill path missing on one platform = FAIL; no drill paths = N/A
recorded.

### Step 7 — Export Validation 🔷 Roadmap

Deeper-than-UI validation by exporting the underlying data from both
platforms (Tableau REST/CSV export; Power BI `executeQueries` / XMLA) and
diffing with pandas: row counts, distinct counts, totals, and **missing
records at row level**. This catches defects below UI granularity (e.g. two
wrong rows that offset in an aggregate). Planned as an opt-in step because it
requires API access/permissions that pure-UI validation does not.

### Step 8 — AI Root Cause Analysis 🔶 Partial

Today the agent already reasons across findings and writes probable causes
into report notes — e.g. in the demo run, ProductKey 359 missing from **two**
independent visuals was diagnosed as *"a dataset-level issue (row filter or
partial data load), not a visual-level one."*

🔷 Roadmap: a structured RCA step with a cause taxonomy (filter mismatch, DAX
translation, LOD-expression conversion, inactive relationship, null handling,
join duplication), evidence-based confidence, and — once Step 7 exists —
row-level evidence:

```
Revenue mismatch: 1.1%
Probable cause: Customer table relationship inactive in Power BI model
Confidence: 82%
```

### Step 9 — Report Generation, Email & History ✅

Called **always**, even after total auth failure:

1. `generate_validation_report` → timestamped Markdown in
   `validation-reports/`: summary header (accuracy %), visual inventory,
   per-visual sections with side-by-side screenshots and per-value verdict
   tables, notes. Also sweeps non-screenshot files out of
   `validation-screenshots/` (screenshots-only guarantee).
2. `send_report_email` → **emails the finished report** (summary line +
   full report body + `.md` attachment) to the recipients configured in
   `.env` (`SMTP_HOST`, `EMAIL_FROM`, `EMAIL_TO`; works with M365, Gmail app
   passwords, or any relay). Unconfigured email degrades gracefully — the
   run reports "email not configured" instead of failing.
3. `record_validation_run` → appends the run to `harness-log.json` (§6).

🔷 Roadmap: program-level **Validation Dashboard** (Power BI) fed from
`harness-log.json` + per-report JSON summaries — executive summary of the
whole 150–200-report program (reports validated, pages/visuals compared,
pass/warning/fail distribution).

## 5. Logging & Artifacts (where everything is stored)

| Artifact | Location | Written by |
|---|---|---|
| Validation reports (per run) | `migration-validation-mcp/validation-reports/Validation_Report_<ts>.md` | `generate_validation_report` |
| Screenshots (immutable, RUN_ID-prefixed) | `migration-validation-mcp/validation-screenshots/` | Playwright MCP |
| Run history + self-check outcomes | `migration-validation-mcp/harness-log.json` | `record_validation_run` |
| Debug artifacts (console logs, DOM snapshots swept out of the screenshots dir) | `migration-validation-mcp/playwright-debug/` | ScreenshotDirCleaner |
| MCP server operational log | stderr of the server process (`logging_config`) | server |
| Saved auth session | `migration-validation-mcp/auth-state.json` | `scripts/authenticate.py` |

So yes — every validation is durably logged twice: the human-readable report
and the machine-readable history record, plus the screenshot evidence both
link to.

## 6. Harness Engineering — learning from our own mistakes

The tool assumes **the validator itself can be wrong**, and instruments for it:

- **Per-run self-checks.** Every `record_validation_run` carries a `checks`
  map — auth, Tableau extraction, Power BI extraction, filter validation,
  drill-through, screenshots-dir hygiene — each PASS/FAIL/N/A. The history
  service aggregates these and reports the **most common failed check** across
  runs, pointing at the weakest part of the harness, not just of the reports.
- **Incomplete-work honesty.** Runs record `incomplete_items` (e.g. "city
  values compared on a 36-of-270 sample") so coverage limits are explicit,
  never implied.
- **Mistake → playbook hardening loop.** When a run exposes a validator bug,
  the fix lands in the skill/server so the mistake becomes impossible to
  repeat. Real examples from this repo's history: screenshot filenames being
  written outside the screenshots folder (fixed + an automated sweep added so
  the folder *stays* clean), and static screenshot names silently overwriting
  earlier runs' evidence (fixed by mandatory RUN_ID prefixes).
- **Cumulative statistics.** `get_validation_history` exposes run count,
  average pass rate, and fully-passed-run count — trend data that shows
  whether both the migrations *and* the validator are improving.

## 7. Technology Stack

| Layer | Current ✅ | Roadmap 🔷 |
|---|---|---|
| UI automation | Playwright (official Playwright MCP) | — |
| AI orchestration | Claude (Claude Code agent + skill playbook), incl. vision for layout checks | Multi-agent parallelization; Azure OpenAI/GPT interchangeable at the orchestrator layer if required |
| Comparison engine | Python 3 / Pydantic MCP server (deterministic comparator) | pandas for row-level export diffs |
| Power BI integration | Rendered-UI (SVG/DOM) | REST API, XMLA endpoint, semantic-model APIs |
| Tableau integration | Rendered-UI (canvas tooltips/DOM) | Metadata API, REST API |
| Reporting | Markdown reports + JSON summaries + SMTP email | Power BI Validation Dashboard over harness-log |
| Evidence | RUN_ID-prefixed screenshots | — |

## 8. Scaling to 150–200 Reports 🔷

The unit of work (one URL pair → one report) is already fully automated; the
program layer adds:

1. **Manifest-driven batching** — CSV/Excel of (report name, Tableau URL,
   Power BI URL, owner); a driver walks it with resumability (re-runs skip
   passed reports; failures triage into *fix-the-report / fix-the-tool /
   retry-auth* buckets).
2. **Chunked sessions** — batches of 15–25 reports per freshly-authenticated
   session to stay inside auth-state lifetime; re-auth checkpoints between
   chunks.
3. **Parallel workers** — multiple agent instances over disjoint manifest
   slices once sequential throughput becomes the bottleneck.
4. **Program rollup** — the Validation Dashboard (§4 Step 9) as the single
   pane of glass for stakeholders.

## 9. Risks & Limitations

| Risk | Mitigation |
|---|---|
| MFA/session expiry mid-batch | Upfront auth, auth gate on every navigation, bounded MFA wait, chunked batches, explicit auth-FAIL reporting |
| Custom visuals with non-standard DOM | "Extraction Failed" status (never guessed values); OCR/API fallbacks on roadmap |
| Very large tables | Full row-inventory + sampled values with sample size disclosed; row-level export diff on roadmap |
| Dynamic/animated visuals | Render waits + re-reads; inconsistent reads reported as warnings |
| Canvas hit-testing is pixel-based | Coordinates computed from live bounding boxes each run; multi-radius sweeps for small pie slices |
| Email/SMTP unavailable | Graceful degradation — report on disk is the source of truth |

## Appendix A — Custom MCP tool reference

| Tool | Purpose | Key input → output |
|---|---|---|
| `health_check` | Server liveness | — → status |
| `compare_values` | Judge ad-hoc value pairs (filters, drills) | `[{label, tableau_value, powerbi_value}]` → per-pair verdicts |
| `compare_visuals` | Judge one matched visual pair point-by-point | two `Visual`s → `VisualComparison` |
| `generate_validation_report` | Render the Markdown report (always called) | URLs + comparisons → path + summary counts |
| `send_report_email` | Email the finished report | `report_path`, `summary_line` → `sent` + recipients |
| `record_validation_run` | Append run + self-checks to history | run record → cumulative stats |
| `get_validation_history` | Read full history | — → runs + stats |
