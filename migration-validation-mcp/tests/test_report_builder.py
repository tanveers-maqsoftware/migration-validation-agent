"""Unit tests for Markdown report rendering."""

from pathlib import Path

from migration_validation.models import (
    ComparisonStatus,
    ValidationReport,
    ValueComparison,
    VisualComparison,
    VisualType,
)
from migration_validation.services.report_builder import MarkdownReportBuilder


def _sample_report() -> ValidationReport:
    return ValidationReport(
        tableau_url="https://public.tableau.com/views/Demo/Dashboard",
        powerbi_url="https://app.powerbi.com/groups/x/reports/y",
        comparisons=[
            VisualComparison(
                title="Sales by Region",
                page="Overview",
                visual_type=VisualType.BAR_CHART,
                values=[
                    ValueComparison(
                        label="Region A",
                        tableau_value="1.0M",
                        powerbi_value="1.0M",
                        status=ComparisonStatus.PASS,
                        variance_pct=0.0,
                    ),
                    ValueComparison(
                        label="Region B",
                        tableau_value="$1.25M",
                        powerbi_value="$1.21M",
                        status=ComparisonStatus.FAIL,
                        variance_pct=-3.2,
                        reason="Value mismatch",
                    ),
                ],
                tableau_screenshot="validation-screenshots/tableau_visual_1.png",
                powerbi_screenshot="validation-screenshots/pbi_visual_1.png",
            ),
        ],
    )


def test_build_contains_summary_and_sections():
    markdown = MarkdownReportBuilder(reports_dir=Path(".")).build(_sample_report())

    assert "# Validation Report" in markdown
    assert "**Total Visuals:** 1" in markdown
    assert "## Visual Inventory" in markdown
    assert "## Visual 1: Sales by Region" in markdown
    assert "❌ Fail" in markdown  # visual fails because one value failed
    assert "![Tableau](validation-screenshots/tableau_visual_1.png)" in markdown
    assert "| Region B | $1.25M | $1.21M | -3.2% | Value mismatch |" in markdown


def test_write_creates_timestamped_file(tmp_path):
    builder = MarkdownReportBuilder(reports_dir=tmp_path)
    path = builder.write(_sample_report())

    assert path.exists()
    assert path.name.startswith("Validation_Report_")
    assert path.suffix == ".md"
    assert "# Validation Report" in path.read_text(encoding="utf-8")


def test_summary_counts_and_pass_rate():
    report = _sample_report()
    summary = report.summary()
    assert summary.total_visuals == 1
    assert summary.failed == 1
    assert summary.pass_rate_pct == 0.0
