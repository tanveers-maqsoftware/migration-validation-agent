"""Domain MCP tools the validation agent calls after extracting visuals.

Browser automation is NOT here — the agent drives the browser through the
official Playwright MCP server (`npx @playwright/mcp`). These tools cover
what Playwright cannot: applying the migration-validation tolerance rules
and rendering the final report, deterministically.
"""

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from migration_validation.config.settings import settings
from migration_validation.models import ValidationReport, Visual, VisualComparison
from migration_validation.models.history import ValidationRunRecord
from migration_validation.services.comparator import ValueComparator
from migration_validation.services.report_builder import MarkdownReportBuilder
from migration_validation.services.run_history import RunHistoryService


# -- tool inputs (their JSON schemas are what the agent sees) ----------------

class EmptyInput(BaseModel):
    """No arguments."""


class ValuePair(BaseModel):
    label: str = Field(description="Category/label this value belongs to")
    tableau_value: str | float | int | None = Field(
        default=None, description="Value as rendered in Tableau, e.g. '$1.2M'"
    )
    powerbi_value: str | float | int | None = Field(
        default=None, description="Value as rendered in Power BI"
    )


class CompareValuesInput(BaseModel):
    pairs: list[ValuePair] = Field(description="Value pairs to compare")


class CompareVisualsInput(BaseModel):
    tableau_visual: Visual
    powerbi_visual: Visual


class GenerateReportInput(BaseModel):
    tableau_url: str
    powerbi_url: str
    comparisons: list[VisualComparison] = Field(
        description="Output of compare_visuals for every matched visual"
    )
    filename: str | None = Field(
        default=None, description="Report filename; defaults to a timestamped name"
    )


class RecordRunInput(ValidationRunRecord):
    """A completed run to append to the history log (same shape as the record)."""


# -- the toolbox --------------------------------------------------------------

class ValidationToolbox:
    """Owns the domain services and exposes them as MCP tool handlers."""

    def __init__(
        self,
        comparator: ValueComparator | None = None,
        report_builder: MarkdownReportBuilder | None = None,
        run_history: RunHistoryService | None = None,
    ) -> None:
        self._comparator = comparator or ValueComparator()
        self._report_builder = report_builder or MarkdownReportBuilder(
            settings.reports_dir
        )
        self._run_history = run_history or RunHistoryService(settings.history_path)

    async def health_check(self, _: EmptyInput) -> dict[str, Any]:
        return {
            "status": "healthy",
            "server": settings.app_name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def compare_values(self, args: CompareValuesInput) -> dict[str, Any]:
        results = [
            self._comparator.compare_value(
                pair.label, pair.tableau_value, pair.powerbi_value
            )
            for pair in args.pairs
        ]
        return {"results": [result.model_dump() for result in results]}

    async def compare_visuals(self, args: CompareVisualsInput) -> dict[str, Any]:
        comparison = self._comparator.compare_visual(
            args.tableau_visual, args.powerbi_visual
        )
        return comparison.model_dump()

    async def generate_validation_report(
        self, args: GenerateReportInput
    ) -> dict[str, Any]:
        report = ValidationReport(
            tableau_url=args.tableau_url,
            powerbi_url=args.powerbi_url,
            comparisons=args.comparisons,
        )
        path = self._report_builder.write(report, args.filename)
        return {
            "report_path": str(path),
            "summary": report.summary().model_dump(),
        }

    async def record_validation_run(self, args: RecordRunInput) -> dict[str, Any]:
        record = ValidationRunRecord.model_validate(args.model_dump())
        stats = self._run_history.append(record)
        return {
            "recorded": True,
            "harness_score": record.harness_score,
            "cumulative": stats.model_dump(),
        }

    async def get_validation_history(self, _: EmptyInput) -> dict[str, Any]:
        records = self._run_history.load()
        return {
            "runs": [record.model_dump(mode="json") for record in records],
            "cumulative": self._run_history.stats(records).model_dump(),
        }
