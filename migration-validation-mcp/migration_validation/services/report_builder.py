"""Renders a ValidationReport to the Markdown format defined by the playbook.

Keeping the rendering here (instead of letting the LLM compose the file)
guarantees every run produces the same structure: summary header, visual
inventory, one section per visual with screenshots and value table, and a
final summary table.
"""

from datetime import datetime
from pathlib import Path

from migration_validation.models import ComparisonStatus, ValidationReport, VisualComparison

_STATUS_BADGES = {
    ComparisonStatus.PASS: "✅ Pass",
    ComparisonStatus.WARNING: "⚠️ Warning",
    ComparisonStatus.FAIL: "❌ Fail",
}


class MarkdownReportBuilder:
    """Builds and writes ``Validation_Report_<timestamp>.md`` files."""

    def __init__(self, reports_dir: Path) -> None:
        self.reports_dir = reports_dir

    def write(self, report: ValidationReport, filename: str | None = None) -> Path:
        """Render the report and write it into ``reports_dir``."""
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"Validation_Report_{timestamp}.md"

        path = self.reports_dir / filename
        path.write_text(self.build(report), encoding="utf-8")
        return path

    def build(self, report: ValidationReport) -> str:
        summary = report.summary()
        lines = [
            "# Validation Report",
            "",
            f"**Date:** {report.generated_at:%Y-%m-%d %H:%M} UTC  ",
            f"**Tableau:** {report.tableau_url}  ",
            f"**Power BI:** {report.powerbi_url}  ",
            f"**Total Visuals:** {summary.total_visuals} | "
            f"**Passed:** {summary.passed} | "
            f"**Warnings:** {summary.warnings} | "
            f"**Failed:** {summary.failed} | "
            f"**Accuracy:** {summary.pass_rate_pct}%",
            "",
            "---",
            "",
            "## Visual Inventory",
            "",
            "| # | Visual | Page | Type | Status |",
            "|---|--------|------|------|--------|",
        ]
        for index, comparison in enumerate(report.comparisons, start=1):
            lines.append(
                f"| {index} | {comparison.title} | {comparison.page} "
                f"| {comparison.visual_type} | {_STATUS_BADGES[comparison.status]} |"
            )

        for index, comparison in enumerate(report.comparisons, start=1):
            lines += ["", "---", ""] + self._visual_section(index, comparison)

        return "\n".join(lines) + "\n"

    def _visual_section(self, index: int, comparison: VisualComparison) -> list[str]:
        lines = [
            f"## Visual {index}: {comparison.title}",
            "",
            f"**Type:** {comparison.visual_type} | "
            f"**Page:** {comparison.page or '—'} | "
            f"**Status:** {_STATUS_BADGES[comparison.status]}",
            "",
        ]

        if comparison.tableau_screenshot or comparison.powerbi_screenshot:
            tableau_img = _image_cell(comparison.tableau_screenshot, "Tableau")
            powerbi_img = _image_cell(comparison.powerbi_screenshot, "Power BI")
            lines += [
                "| Tableau | Power BI |",
                "|---------|----------|",
                f"| {tableau_img} | {powerbi_img} |",
                "",
            ]

        if comparison.values:
            lines += [
                "| Category | Tableau | Power BI | Variance % | Reason |",
                "|----------|---------|----------|------------|--------|",
            ]
            for value in comparison.values:
                variance = "—" if value.variance_pct is None else f"{value.variance_pct}%"
                lines.append(
                    f"| {value.label} | {_cell(value.tableau_value)} "
                    f"| {_cell(value.powerbi_value)} | {variance} "
                    f"| {value.reason or '—'} |"
                )

        for note in comparison.notes:
            lines += ["", f"> {note}"]
        return lines


def _cell(value: str | float | int | None) -> str:
    return "—" if value is None else str(value)


def _image_cell(path: str | None, alt: str) -> str:
    return f"![{alt}]({path})" if path else "—"
