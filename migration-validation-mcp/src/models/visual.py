"""Domain models for a single visual extracted from a report page.

A *visual* is anything a business user sees on a dashboard: a bar chart, a KPI
card, a table, a slicer. The LLM agent extracts these from the browser (via
Playwright MCP) and hands them to our comparison tools as instances of
:class:`Visual`.
"""

from enum import StrEnum

from pydantic import BaseModel, Field


class Platform(StrEnum):
    """Which BI platform a visual was extracted from."""

    TABLEAU = "tableau"
    POWERBI = "powerbi"


class VisualType(StrEnum):
    """Coarse visual taxonomy shared by both platforms.

    Only the distinctions that change how values are compared matter here;
    e.g. every bar/column/area variant compares the same way, so they all
    map to a small set of types. Use ``OTHER`` for anything unrecognised.
    """

    BAR_CHART = "bar_chart"
    LINE_CHART = "line_chart"
    AREA_CHART = "area_chart"
    COMBO_CHART = "combo_chart"
    PIE_CHART = "pie_chart"
    SCATTER_PLOT = "scatter_plot"
    MAP = "map"
    KPI_CARD = "kpi_card"
    TABLE = "table"
    MATRIX = "matrix"
    SLICER = "slicer"
    TEXT = "text"
    OTHER = "other"


class DataPoint(BaseModel):
    """One value read off a visual (a tooltip, a data label, a table cell).

    ``label`` is the category/axis position ("ProductKey 365", "Region A"),
    ``series`` disambiguates multi-series charts ("2024 Sales" line vs
    "2023 Sales" line), and ``value`` is the raw text exactly as rendered —
    parsing "$1.2M" into a number is the comparator's job, not the agent's.
    """

    label: str
    value: str | float | int | None = None
    series: str | None = None

    @property
    def key(self) -> str:
        """Case-insensitive identity used to match points across platforms."""
        series = (self.series or "").strip().casefold()
        return f"{series}::{self.label.strip().casefold()}"


class Visual(BaseModel):
    """Everything the agent extracted about one visual on one platform."""

    platform: Platform
    title: str
    page: str = Field(default="", description="Page/tab/bookmark the visual lives on")
    visual_type: VisualType = VisualType.OTHER
    axis_labels: list[str] = Field(default_factory=list)
    legend_items: list[str] = Field(default_factory=list)
    data_points: list[DataPoint] = Field(default_factory=list)
    screenshot: str | None = Field(
        default=None, description="Relative path to this visual's screenshot"
    )
