"""Top-level validation report model: one run, all visual comparisons."""

from datetime import datetime, timezone

from pydantic import BaseModel, Field

from migration_validation.models.comparison import ComparisonStatus, VisualComparison


class ReportSummary(BaseModel):
    """Roll-up counts shown at the top of the report."""

    total_visuals: int
    passed: int
    warnings: int
    failed: int
    pass_rate_pct: float


class ValidationReport(BaseModel):
    """Everything needed to render a validation report for one run."""

    tableau_url: str
    powerbi_url: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    comparisons: list[VisualComparison] = Field(default_factory=list)

    def summary(self) -> ReportSummary:
        counts = {status: 0 for status in ComparisonStatus}
        for comparison in self.comparisons:
            counts[comparison.status] += 1

        total = len(self.comparisons)
        passed = counts[ComparisonStatus.PASS]
        warnings = counts[ComparisonStatus.WARNING]
        return ReportSummary(
            total_visuals=total,
            passed=passed,
            warnings=warnings,
            failed=counts[ComparisonStatus.FAIL],
            # Warnings count as passing: they flag additional data, not wrong data.
            pass_rate_pct=round(100 * (passed + warnings) / total, 2) if total else 0.0,
        )
