"""Domain models describing the outcome of comparing Tableau vs Power BI.

The severity ladder is deliberate:

* ``PASS``    — values agree within tolerance.
* ``WARNING`` — nothing is wrong, but a human should glance at it
                (e.g. Power BI shows *additional* rows Tableau never had).
* ``FAIL``    — a rendered value disagrees beyond tolerance, or data that
                exists in Tableau is missing from Power BI.
"""

from enum import StrEnum

from pydantic import BaseModel, Field, computed_field

from src.models.visual import VisualType


class ComparisonStatus(StrEnum):
    PASS = "pass"
    WARNING = "warning"
    FAIL = "fail"


class ValueComparison(BaseModel):
    """One label's value compared across both platforms."""

    label: str
    tableau_value: str | float | int | None = None
    powerbi_value: str | float | int | None = None
    status: ComparisonStatus
    variance_pct: float | None = Field(
        default=None,
        description="Relative variance in percent when both values are numeric",
    )
    reason: str = Field(default="", description="Short phrase, e.g. 'Rounding'")


class VisualComparison(BaseModel):
    """A matched pair of visuals and all of their value-level comparisons."""

    title: str
    page: str = ""
    visual_type: VisualType = VisualType.OTHER
    values: list[ValueComparison] = Field(default_factory=list)
    tableau_screenshot: str | None = None
    powerbi_screenshot: str | None = None
    notes: list[str] = Field(default_factory=list)

    @computed_field  # serialized so the LLM agent sees the verdict directly
    @property
    def status(self) -> ComparisonStatus:
        """Worst value-level status wins: any FAIL fails the visual."""
        statuses = {value.status for value in self.values}
        if ComparisonStatus.FAIL in statuses:
            return ComparisonStatus.FAIL
        if ComparisonStatus.WARNING in statuses:
            return ComparisonStatus.WARNING
        return ComparisonStatus.PASS
