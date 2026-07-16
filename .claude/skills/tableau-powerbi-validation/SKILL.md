---
name: tableau-powerbi-validation
description: 'Validate Tableau to Power BI migration by comparing rendered visuals in the browser using Playwright. Use when: comparing dashboards across Tableau and Power BI, validating KPI cards, tables, charts, tooltips, legends, axis labels, and filters between platforms. Triggers: validate migration, compare reports, compare dashboards, Tableau vs Power BI, visual comparison, migration accuracy.'
argument-hint: 'Provide Tableau URL and Power BI URL to compare'
---

# Tableau ↔ Power BI Visual Validation Skill

## When to Use

- Validating that a Tableau dashboard was correctly migrated to Power BI
- Comparing what business users see on both platforms
- Checking KPI values, chart data points, table data, and tooltips match
- Generating a migration accuracy report

## Prerequisites

- Both report URLs must be accessible (public or user is authenticated)
- Browser tools must be available (Playwright-based)

## Authentication Gate (check after EVERY `browser_navigate`)

Private reports (Power BI `app.powerbi.com/groups/...`, Tableau Server/Cloud — i.e. anything not on Tableau Public / "Publish to web") sit behind a login wall. A saved session normally carries you past it (captured by `migration-validation-mcp/scripts/authenticate.py`, wired in automatically via `migration-validation-mcp/scripts/run_playwright_mcp.py`), but sessions expire. After navigating to either report URL, check the page URL and title BEFORE extracting anything.

**Signs you hit a login wall:** URL contains `login.microsoftonline.com`, page says "Sign in to your account" / "Approve sign in", Tableau URL redirects to a `/signin` page.

**What to do — in this order:**

1. **NEVER type credentials or passwords** into any field.
2. Wait 5 seconds and re-check — SSO redirects often resolve on their own.
3. **If an Authenticator number-match screen appears** ("Approve sign in", "Enter the number if prompted"): **immediately tell the user the number, prominently, before waiting** — e.g. *"MFA approval needed — open Microsoft Authenticator and enter **NN**. If no notification arrived, open the Authenticator app manually and pull down to refresh — the pending request appears there even when the push fails to deliver."* Then poll in ~15s intervals (`browser_wait_for`) for **at most 2 minutes total**. Never wait silently or unbounded.
4. **Still on the sign-in page after ~2 minutes** (or the request was denied/expired)? Stop validating this platform: record `Authentication required — <platform>` as one FAIL in the report, continue with the other platform, and end your summary telling the user to run `uv run python scripts/authenticate.py` from `migration-validation-mcp/`, restart the MCP servers, and re-run the validation.

> **NON-NEGOTIABLE: call `generate_validation_report` no matter what happened above.** Full success, partial extraction, or a total authentication failure on BOTH platforms — you must still call it before ending your turn. If a platform failed auth, its only comparison entry can be a single `VisualComparison` titled `"Authentication Status: <platform>"` with one FAIL value explaining the blocker (e.g. `"MFA approval not received within 2 minutes"`). Zero comparisons is still a valid report. **A run that ends without a report is a failed run, even if the reason was authentication, not extraction.**

## Procedure

### Step 0: Establish a Run ID (before any navigation)

Generate a `RUN_ID` once — `YYYYMMDD_HHMMSS` from the current time — and prefix **every** screenshot filename with it for the rest of this run. **Never reuse a static filename like `tableau-full.png` across runs**: a later run's screenshot silently overwrites an earlier run's file at that same path, corrupting the image links in that earlier run's already-generated report. The `RUN_ID` prefix is what makes each run's evidence immutable.

### Step 1: Receive Input

Collect from the user:
- **Tableau URL**: Full URL to the Tableau dashboard (e.g., `https://public.tableau.com/views/ReportName/Dashboard`)
- **Power BI URL**: Full URL to the Power BI report (e.g., `https://app.powerbi.com/groups/.../reports/...`)

### Step 2: Open Tableau Dashboard

1. Use `browser_navigate` to open the Tableau URL
2. Use `browser_wait_for` to wait for `.tab-dashboard, .tableauPlaceholder, #tableau_base_target` to be present
3. Wait additional 3-5 seconds for all visuals to render
4. **Detect multiple pages/tabs**:
   - Look for: `.tabWidget .tab`, `.tableau-tab`, `[role="tab"]`, `.storyPointCaption`
   - If tabs exist, iterate through EACH tab:
     a. Click tab → wait for load → screenshot → extract visuals
     b. Screenshot filenames: `{RUN_ID}_tableau-page-1.png`, `{RUN_ID}_tableau-page-2.png`, etc.
   - If no tabs, treat as single page
5. Use `browser_take_screenshot` — filename `{RUN_ID}_tableau-full.png` (default page)
6. Use `browser_snapshot` to read the accessibility tree

> **Pass ONLY the bare filename to `browser_take_screenshot`** (e.g. `{RUN_ID}_tableau-full.png`) — **never** prefix it with `validation-screenshots/`. The Playwright MCP server is already configured with `--output-dir=migration-validation-mcp/validation-screenshots`, so it places every file there automatically. Adding the folder name yourself makes Playwright save relative to the *repo root* instead, scattering screenshots outside the correct folder.
> **`validation-screenshots/` is screenshots ONLY.** Other tools (`browser_console_messages`, `browser_snapshot`, `browser_network_request`) also accept an optional `filename` that writes into the same `--output-dir` — **never pass `filename` to those tools.** Always let their output return inline in the response instead.
> **Track which page each visual belongs to for accurate cross-platform matching.**

### Step 3: Extract Tableau Visuals

For each visual container found:

**Identify visual type** using DOM patterns:
```javascript
// Cards: .tab-textRegion with single large number
// Tables: .tabGlassPaneContainer table, .tab-tableCell
// Charts: svg with .mark, .tab-mark-group
// Filters: .tab-filter, .tabQuickFilter
```

**Extract data** using `browser_evaluate`:
```javascript
// Get all visual titles
Array.from(document.querySelectorAll('.tab-textRegion')).map(el => el.innerText)

// Get table data
Array.from(document.querySelectorAll('table tr')).map(row => 
  Array.from(row.querySelectorAll('td, th')).map(cell => cell.innerText)
)

// Get axis labels
Array.from(document.querySelectorAll('.tick text')).map(el => el.textContent)

// Get legend entries
Array.from(document.querySelectorAll('.legendItem text, .tabLegendEntry')).map(el => el.textContent)
```

**Extract tooltips** by hovering (MANDATORY for pie/donut charts and canvas-rendered visuals):

> **CRITICAL**: Tableau renders charts on `<canvas>` elements. Standard DOM hover via `browser_hover` does NOT work on canvas pixels. You MUST use PointerEvent/MouseEvent dispatching on the canvas element at calculated coordinates.

**For Pie/Donut Charts (canvas-rendered):**
```javascript
async () => {
  const iframe = document.querySelector('iframe');
  const iframeDoc = iframe.contentDocument || iframe.contentWindow.document;
  
  // Locate the pie chart zone
  const zones = Array.from(iframeDoc.querySelectorAll('.tab-zone.tab-widget.tabZone-viz'));
  const pieZone = zones.find(z => z.innerText.startsWith('YOUR_SHEET_NAME'));
  const canvas = pieZone.querySelectorAll('canvas')[2]; // topmost canvas layer
  
  // Calculate center of pie
  const rect = canvas.getBoundingClientRect();
  const cx = rect.x + rect.width / 2;
  const cy = rect.y + rect.height / 2;
  
  const results = [];
  const knownEntries = [];
  
  // Sweep at multiple radii (35, 50, 65) with fine angles (every 3-5°)
  // Smaller slices require smaller radius and finer angle increments
  for (const radius of [35, 50, 65]) {
    for (let angle = 0; angle < 360; angle += 5) {
      const rad = angle * Math.PI / 180;
      const x = cx + radius * Math.cos(rad);
      const y = cy + radius * Math.sin(rad);
      
      canvas.dispatchEvent(new PointerEvent('pointermove', { bubbles: true, clientX: x, clientY: y, pointerId: 1 }));
      canvas.dispatchEvent(new MouseEvent('mousemove', { bubbles: true, clientX: x, clientY: y }));
      
      await new Promise(r => setTimeout(r, 300));
      
      const tooltip = iframeDoc.querySelector('.tab-tooltip, [class*="tooltip"]');
      if (tooltip && tooltip.offsetHeight > 0) {
        const text = tooltip.innerText.trim();
        if (text && !knownEntries.includes(text)) {
          knownEntries.push(text);
          results.push({ angle, radius, tooltip: text });
        }
      }
    }
  }
  return results;
}
```

**For Bar Charts / other SVG-based visuals:**
1. Find all data point elements (bars, circles, paths)
2. For each point, dispatch PointerEvent at element center coordinates
3. Wait 300-600ms for tooltip to render
4. Read `.tab-tooltip` or `.tabTooltipContainer` content
5. Parse into key/value pairs

### Step 3b: Handle Scrollable Visuals in Tableau (MANDATORY)

> **CRITICAL**: Tables and highlight tables in Tableau use virtualized scrolling (`.tab-tvScrollY`). Only ~20-30 rows are visible at a time. You MUST scroll through the entire container to extract ALL data.

```javascript
async () => {
  const iframe = document.querySelector('iframe');
  const iframeDoc = iframe.contentDocument || iframe.contentWindow.document;
  
  const zones = Array.from(iframeDoc.querySelectorAll('.tab-zone.tab-widget.tabZone-viz'));
  const targetZone = zones.find(z => z.innerText.includes('YOUR_IDENTIFIER'));
  const scrollEl = targetZone.querySelector('.tab-tvScrollY');
  
  const allData = new Set();
  let scrollPos = 0;
  const step = 200; // scroll in 200px increments
  const maxScroll = scrollEl.scrollHeight;
  
  while (scrollPos <= maxScroll) {
    scrollEl.scrollTop = scrollPos;
    await new Promise(r => setTimeout(r, 200));
    
    // Extract currently rendered row headers
    const headers = Array.from(targetZone.querySelectorAll('.tab-vizHeader'));
    headers.forEach(h => {
      const text = h.innerText.trim();
      if (text) allData.add(text);
    });
    
    scrollPos += step;
  }
  
  return Array.from(allData).sort();
}
```

**Key indicators that scrolling is needed:**
- `scrollHeight` >> `clientHeight` on `.tab-tvScrollY` element
- Visual shows partial data with scrollbar
- Aria labels mention more data points than visible

> **Before scrolling, apply the Large-Table Policy (Step 5c):** estimate the row count from `scrollHeight / rowHeight` — if it exceeds ~300 rows, do NOT full-scroll; validate grand totals first and fall back to first/middle/last band sampling.

### Step 4: Open Power BI Report

1. Use `browser_navigate` to open the Power BI URL
2. Use `browser_wait_for` to wait for `visual-container, .visualContainerHost` to be present
3. Wait additional 3-5 seconds for all visuals to render
4. Use `browser_take_screenshot` — filename `{RUN_ID}_powerbi-full.png` (bare filename only — see the note in Step 2, same rule applies here)
5. Use `browser_snapshot` to read the accessibility tree

### Step 5: Extract Power BI Visuals

For each visual container found:

**Identify visual type** using DOM patterns:
```javascript
// Cards: visual-container[visual-type="card"], .card
// Tables: visual-container[visual-type="tableEx"], .tableEx
// Matrix: visual-container[visual-type="pivotTable"]
// Bar Chart: visual-container[visual-type="clusteredBarChart"]
// Line Chart: visual-container[visual-type="lineChart"]
// Pie Chart: visual-container[visual-type="donutChart"]
// Filters: .slicer-container
```

**Extract data** using `browser_evaluate`:
```javascript
// Get visual titles
Array.from(document.querySelectorAll('.visualTitle span')).map(el => el.innerText)

// Get card values
Array.from(document.querySelectorAll('.card .value, .cardValue')).map(el => el.innerText)

// Get table data
Array.from(document.querySelectorAll('.tablixCell')).map(cell => cell.innerText)

// Get axis labels
Array.from(document.querySelectorAll('.axisLabel text, .xAxisLabel, .yAxisLabel')).map(el => el.textContent)

// Get legend entries
Array.from(document.querySelectorAll('.legendItem .legendText')).map(el => el.textContent)
```

**Extract tooltips** by hovering (MANDATORY for pie/donut charts):

> **CRITICAL**: Standard `browser_hover` does NOT trigger Power BI tooltips on SVG chart elements. You MUST use PointerEvent dispatching directly on the SVG path/rect elements.

**For Pie/Donut Charts:**
```javascript
async () => {
  const visuals = Array.from(document.querySelectorAll('visual-container'));
  const pieVisual = visuals.find(v => v.innerText.includes('YOUR_MEASURE'));
  const paths = Array.from(pieVisual.querySelectorAll('svg path'));
  const slices = paths.filter(p => {
    const d = p.getAttribute('d');
    return d && d.includes('A') && d.length > 50; // Arc paths = pie slices
  });
  
  const results = [];
  
  for (let i = 0; i < slices.length; i++) {
    const slice = slices[i];
    const box = slice.getBoundingClientRect();
    const x = box.x + box.width / 2;
    const y = box.y + box.height / 2;
    
    // Reset tooltip by moving away
    document.dispatchEvent(new MouseEvent('mousemove', { bubbles: true, clientX: 0, clientY: 0 }));
    await new Promise(r => setTimeout(r, 300));
    
    // Dispatch full pointer event sequence (required for Power BI)
    slice.dispatchEvent(new PointerEvent('pointerenter', { bubbles: true, clientX: x, clientY: y, pointerId: 1 }));
    slice.dispatchEvent(new PointerEvent('pointerover', { bubbles: true, clientX: x, clientY: y, pointerId: 1 }));
    slice.dispatchEvent(new PointerEvent('pointermove', { bubbles: true, clientX: x, clientY: y, pointerId: 1 }));
    slice.dispatchEvent(new MouseEvent('mouseenter', { bubbles: false, clientX: x, clientY: y }));
    slice.dispatchEvent(new MouseEvent('mouseover', { bubbles: true, clientX: x, clientY: y }));
    slice.dispatchEvent(new MouseEvent('mousemove', { bubbles: true, clientX: x, clientY: y }));
    
    await new Promise(r => setTimeout(r, 800));
    
    // Read tooltip from Power BI's tooltip container
    const tooltipContainer = document.querySelector('.tooltip-container.enhancedTooltips');
    if (tooltipContainer && tooltipContainer.offsetHeight > 0) {
      const rows = Array.from(tooltipContainer.querySelectorAll('.tooltip-row'));
      const data = {};
      rows.forEach(row => {
        const title = row.querySelector('.tooltip-title-cell');
        const value = row.querySelector('.tooltip-value-cell');
        if (title && value) data[title.innerText.trim()] = value.innerText.trim();
      });
      results.push({ slice: i, data });
    }
  }
  return results;
}
```

**For Bar Charts:** Same pattern but target `rect` elements with significant height/width.

### Step 5b: Handle Scrollable Visuals in Power BI (MANDATORY)

> **CRITICAL**: Power BI tables/matrices use virtualized rendering via `.mid-viewport` with `overflow: auto`. Only ~20 rows are DOM-rendered at a time. You MUST scroll to extract ALL data.

```javascript
async () => {
  const visuals = Array.from(document.querySelectorAll('visual-container'));
  const tableVisual = visuals.find(v => v.innerText.includes('YOUR_COLUMN'));
  
  // Find the virtualized scroll container
  const allDivs = Array.from(tableVisual.querySelectorAll('div'));
  const scrollEl = allDivs.find(d => {
    const style = window.getComputedStyle(d);
    return (style.overflowY === 'auto' || style.overflowY === 'scroll') && d.clientHeight > 30;
  });
  
  if (!scrollEl) return { error: 'No scrollable container found' };
  
  const allData = new Map(); // key → value pairs
  let scrollPos = 0;
  const step = 300;
  const maxScroll = scrollEl.scrollHeight;
  
  while (scrollPos <= maxScroll) {
    scrollEl.scrollTop = scrollPos;
    await new Promise(r => setTimeout(r, 200));
    
    // Parse visible rows (Power BI renders pairs: label, value)
    const text = tableVisual.innerText;
    const lines = text.split('\n').filter(l => 
      l.trim() && !['Scroll up','Scroll down','Scroll left','Scroll right',
                    'Row Selection','Select Row','Total'].includes(l.trim())
    );
    // Skip header row, parse data pairs
    // ... extract based on column structure
    
    scrollPos += step;
  }
  
  return Object.fromEntries(allData);
}
```

**Key indicators that scrolling is needed in Power BI:**
- `.mid-viewport` element with `scrollHeight` >> `clientHeight`
- Table visual shows "Total" row at bottom but only partial data above
- Scroll buttons visible in accessibility tree ("Scroll up", "Scroll down")

### Step 5c: Large-Table Policy (BOTH platforms — overrides full-scroll when tables are huge)

Full-scroll extraction (Steps 3b/5b) is only for tables that fit the budget. **Estimate the row count first**, before scrolling: `estimatedRows ≈ scrollEl.scrollHeight / averageRenderedRowHeight` (measure row height from the currently rendered rows).

**Rule L1 — Size gate.** If `estimatedRows ≤ 300`, do the full scroll extraction as written in 3b/5b. If larger — a table can hold millions of rows; NEVER attempt to scroll it end-to-end — switch to aggregate + sample validation below.

**Rule L2 — Totals first.** Look for rendered aggregates and validate those as the primary check:
- Power BI: the table's **Total** row / matrix subtotals + grand totals.
- Tableau: grand total row/column if the sheet has them enabled.
- Compare every available total via `compare_values` (label `"<Column> · Grand Total"`). A total that matches is strong evidence the full column migrated correctly, even without row-level reads.
- If one platform shows totals and the other doesn't, still validate the sum: on the totals-less platform derive nothing — instead record a note that the total exists on only one side (cosmetic) and rely on Rule L3 for data validation.

**Rule L3 — Threshold sampling (always, and mandatory when there are no totals).** Extract three deterministic bands: **first 25 rows** (scrollTop 0), **25 rows at the midpoint** (scrollTop = scrollHeight/2), **last 25 rows** (scrollTop = max). Compare rows across platforms **by row key** (the dimension value, e.g. city name), never by position — sort order may differ between platforms. If sort order differs, say so in a note; if the same keys can't be found on both platforms within the sampled bands, extract the Power BI keys' values on Tableau via targeted scroll/tooltip lookup rather than comparing mismatched positions.

**Rule L4 — Row-count check.** Compare row counts when cheaply determinable: exact count if fully extracted, otherwise the `estimatedRows` from both platforms (must agree within 1%; label `"Row count (estimated)"` and mark the estimate in the reason).

**Rule L5 — Disclose coverage.** The `VisualComparison` notes MUST state what was validated: e.g. `"Totals validated + 75 of ~1.2M rows sampled (first/middle/last bands)"`, and the run's `record_validation_run` call MUST list the sampling in `incomplete_items`. Never present a sampled table as fully verified.

### Step 6: Match Visuals

Match visuals between the two reports:

1. **Exact Match**: Normalize titles (lowercase, trim, remove extra spaces) and compare
2. **Fuzzy Match**: Use character-level similarity > 80% threshold
3. **Type + Content Match**: Same visual type with overlapping value patterns

Record unmatched visuals separately.

### Step 7: Compare Values

**Preferred:** call the `compare_values` or `compare_visuals` tools from the **migration-validation** MCP server with the raw rendered strings — they apply the rules below deterministically and return pass/warning/fail with variance %. Only apply the rules manually if those tools are unavailable.

For each matched pair, the comparison rules are:

| Data Type | Rule |
|-----------|------|
| Numbers | 0% variance = Pass, ≤0.5% = Warning, >0.5% = Fail (bands configurable via `.env`) |
| Percentages | `abs(a - b) <= 1.0` percentage point |
| Text/Labels | Case-insensitive exact match |
| Dates | Normalize format then compare |
| Currency | Strip symbols, compare numeric portion |
| Counts | Exact integer match |

**Value normalization**:
- Remove currency symbols ($, €, £)
- Convert suffixes: K=1000, M=1000000, B=1000000000
- Remove thousands separators
- Trim whitespace

### Step 7b: Filter Validation (when filters/slicers exist on either platform)

**Rule F0 — Inventory & match (always do this, even if you skip applying filters).**
Enumerate filters on both platforms and match them by normalized field name:
- Tableau: `.tabQuickFilter` zones, `.tab-filter`, parameter controls — note each filter's field name and widget type (dropdown / single-select / multi-select / slider / date range).
- Power BI: `.slicer-container` visuals on the canvas **and** the Filters pane entries (`[data-testid*="filter"]`, pane cards).
- A filter present on one platform but not the other = one **FAIL** value (`"Filter <Field>: missing on <platform>"`). Filters pane empty + no slicers on both = record filter validation as **N/A** with a note.

**Rule F1 — Selection budget (deterministic, so runs are reproducible).**
Validate at most **5 matched filters**, in the order they appear top-to-bottom / left-to-right in the Tableau report. For each filter test the **first 2 non-default values** in Tableau's displayed order (1 value if the filter is single-value). Never test combinations of two filters — one filter at a time, always from a clean baseline.

**Rule F2 — Baseline before anything.**
Before applying any value of a filter, record the **baseline**: the 1–3 most prominent affected values (priority: KPI cards → chart total/largest data point → first table row + row count). The same labels must be re-read after applying and after resetting.

**Rule F3 — Apply identically on both platforms.**
- Tableau: open the quick-filter widget, `browser_click` the value; for multi-select, uncheck "(All)" first so exactly one value is active.
- Power BI: `browser_click` the slicer item; if the filter only exists in the Filters pane, expand the card and check the value's checkbox. For multi-select slicers, ensure exactly the same single value is selected (Ctrl-click semantics differ — verify the selection state, not the click).
- Wait for re-render on **both** platforms before reading anything: Tableau — wait until the `.tab-loading` / glass-pane indicator disappears plus 2s; Power BI — wait until visual spinners (`.circle`, `[class*="spinner"]`) disappear plus 2s.

**Rule F4 — Verify the filter actually applied before comparing.**
Confirm at least one of: (a) the widget shows the value selected (checkbox state / slicer highlight / filter chip), AND (b) at least one baseline value changed from Rule F2 — a filter that changes nothing is suspicious unless the value covers all data. If application cannot be confirmed on a platform, record that value as **FAIL** with reason `"Filter did not apply on <platform>"` — do NOT compare unverified numbers.

**Rule F5 — Compare the filtered values.**
Re-read the same 1–3 labels from Rule F2 on both platforms and send to `compare_values` with labels `"<Field>=<Value> · <Measure>"` (e.g. `"Year=2011 · Total Sales"`). Standard tolerance bands decide pass/warning/fail.

**Rule F6 — Reset and verify the reset.**
Clear the filter on both platforms (Tableau: filter menu "Clear"/select All; Power BI: slicer eraser icon / uncheck). Re-read the baseline labels — they must match Rule F2's values exactly. If the baseline does not return, **reload the report page** (`browser_navigate` again) before testing the next filter; never let one filter's residue contaminate the next check.

**Rule F7 — Record everything.**
One `VisualComparison` titled `"Filter check: <Field>"` per filter, containing one value row per (value × measure) tested, plus FAIL rows from F0/F4. Add a note stating which values were tested and which were skipped by the budget (F1) so coverage is explicit in the report.

### Step 7c: Drill-through Validation (when drill paths exist)

For one representative drillable visual: capture the parent value, drill one level down on both platforms, compare child values via `compare_values` (labels like `"East → New York · Sales"`), verify children sum to the parent, drill back up. Include as `VisualComparison` titled `"Drill-through: <visual> → <level>"`. A drill path missing on one platform = one FAIL value.

### Step 8: Generate Report

**Preferred:** call `generate_validation_report` (migration-validation MCP server) with both URLs and the list of visual comparisons — it writes a timestamped Markdown report into `validation-reports/` and returns the path plus summary.

After the report is written, call `record_validation_run` with the summary counts so the run lands in `harness-log.json`; it returns cumulative statistics across all runs (also available anytime via `get_validation_history`).

### Step 8b: Email the Report

After `generate_validation_report` succeeds, call `send_report_email` (migration-validation MCP server) with:
- `report_path` — exactly as returned by `generate_validation_report`
- `summary_line` — one line with the verdict and headline finding, e.g. `"2/5 visuals pass (40%) — ProductKey 359 missing in Power BI"`

The tool emails the report (inline body + `.md` attachment) to the recipients configured in `.env` (`SMTP_HOST`, `EMAIL_FROM`, `EMAIL_TO`, optional `SMTP_USERNAME`/`SMTP_PASSWORD`).

- If it returns `sent: false` (email not configured), do **not** treat this as a validation failure — mention in your final summary that the report was generated but email delivery is not configured, and how to enable it.
- If it returns an `error` (SMTP failure), retry once; if it still fails, report the error in your summary. The validation run itself is still complete — the report on disk is the source of truth.

The report contains:
- Dashboard name
- Total visuals checked
- Pass/Fail counts
- Per-visual details for failures
- Overall accuracy percentage
- JSON summary for programmatic consumption

## Output Format

### Human-Readable Report

```
══════════════════════════════════════════════
  DASHBOARD VALIDATION REPORT
══════════════════════════════════════════════
Dashboard: [Name]
Date: [Current Date]

SUMMARY: [Passed]/[Total] visuals match (Accuracy: [X]%)

FAILURES:
❌ [Visual] - [Reason] (Tableau: [val], Power BI: [val])

PASSED:
✅ [Visual] ([Type])
══════════════════════════════════════════════
```

### JSON Output

```json
{
  "dashboard": "Name",
  "timestamp": "ISO date",
  "tableauUrl": "...",
  "powerBiUrl": "...",
  "visualsChecked": 12,
  "passed": 11,
  "failed": 1,
  "notMatched": 0,
  "accuracy": 91.7,
  "results": [
    {
      "visual": "Revenue Trend",
      "visualType": "Line Chart",
      "status": "Fail",
      "reason": "April revenue mismatch",
      "tableauValue": "1.25M",
      "powerBiValue": "1.21M",
      "difference": "3.2%"
    }
  ],
  "unmatchedTableau": [],
  "unmatchedPowerBI": []
}
```

## Error Handling

| Scenario | Action |
|----------|--------|
| URL fails to load | Report error, continue with other URL |
| Authentication required | Follow the **Authentication Gate** section (surface MFA number, bounded wait, then fail that platform and continue with the other) |
| Visual extraction fails | Mark as "Extraction Failed" in results |
| Tooltip doesn't appear | Skip tooltip, compare visible values only |
| Page timeout | Retry once, then report timeout |
| No visuals found | Report empty dashboard, check URL correctness |

## Limitations

- Dynamic/animated visuals may produce inconsistent reads
- Embedded reports with iframe restrictions may block access
- Custom visuals may not follow standard DOM patterns
- Very small pie slices (< 2% of total) may require multiple radii and fine angle sweeps to detect
- Tableau canvas hit-testing is pixel-based; exact coordinates may shift with viewport/zoom changes
