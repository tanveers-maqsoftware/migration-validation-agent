"""Deterministic value comparison between Tableau and Power BI renderings.

The LLM agent reads raw strings off the screen ("$1.2M", "45.3%", "1,234").
This module owns the rules for deciding whether two such strings *mean* the
same thing, so the judgement is consistent across runs instead of being
re-derived by the model every time:

* numbers      — banded on relative variance: <= ``numeric_pass_pct`` PASS,
                 <= ``numeric_warning_pct`` WARNING, above FAIL
* percentages  — pass if absolute difference <= ``percentage_tolerance_points``
* dates        — pass if they normalise to the same calendar date
* text         — case-insensitive, whitespace-collapsed equality
"""

import re
from datetime import datetime

from migration_validation.config.settings import settings
from migration_validation.models import (
    ComparisonStatus,
    DataPoint,
    ValueComparison,
    Visual,
    VisualComparison,
)

# "$1,234.5M" → sign / currency / digits / magnitude-suffix / percent
_NUMBER_PATTERN = re.compile(
    r"^\(?\s*(?P<sign>-)?\s*[$€£₹]?\s*(?P<digits>\d[\d,]*\.?\d*)\s*"
    r"(?P<suffix>[KMB])?\s*(?P<percent>%)?\s*\)?$",
    re.IGNORECASE,
)
_SUFFIX_MULTIPLIERS = {"K": 1e3, "M": 1e6, "B": 1e9}
_DATE_FORMATS = (
    "%Y-%m-%d", "%d-%m-%Y", "%m/%d/%Y", "%d/%m/%Y",
    "%b %d, %Y", "%d %b %Y", "%B %d, %Y", "%d %B %Y",
)


class ParsedNumber:
    """A numeric value recovered from rendered text."""

    def __init__(self, value: float, is_percentage: bool) -> None:
        self.value = value
        self.is_percentage = is_percentage


def parse_number(raw: str | float | int | None) -> ParsedNumber | None:
    """Parse a rendered value into a number, or None if it is not numeric.

    Handles currency symbols, thousands separators, K/M/B magnitude
    suffixes, percent signs, and accounting-style parentheses negatives.
    """
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return ParsedNumber(float(raw), is_percentage=False)

    text = raw.strip()
    match = _NUMBER_PATTERN.match(text)
    if not match or not match.group("digits"):
        return None

    value = float(match.group("digits").replace(",", ""))
    suffix = (match.group("suffix") or "").upper()
    value *= _SUFFIX_MULTIPLIERS.get(suffix, 1.0)
    if match.group("sign") or (text.startswith("(") and text.endswith(")")):
        value = -value
    return ParsedNumber(value, is_percentage=match.group("percent") is not None)


def parse_date(raw: str | float | int | None) -> datetime | None:
    """Parse a rendered date in any of the common report formats."""
    if not isinstance(raw, str):
        return None
    text = raw.strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def normalize_text(raw: str | float | int | None) -> str:
    """Case-insensitive, whitespace-collapsed form used for text equality."""
    return re.sub(r"\s+", " ", str(raw or "").strip()).casefold()


class ValueComparator:
    """Applies the tolerance rules to values and whole visuals."""

    def __init__(
        self,
        numeric_pass_pct: float | None = None,
        numeric_warning_pct: float | None = None,
        percentage_tolerance_points: float | None = None,
    ) -> None:
        self.numeric_pass_pct = (
            settings.numeric_pass_pct if numeric_pass_pct is None else numeric_pass_pct
        )
        self.numeric_warning_pct = (
            settings.numeric_warning_pct
            if numeric_warning_pct is None
            else numeric_warning_pct
        )
        self.percentage_tolerance_points = (
            settings.percentage_tolerance_points
            if percentage_tolerance_points is None
            else percentage_tolerance_points
        )

    def compare_value(
        self,
        label: str,
        tableau_value: str | float | int | None,
        powerbi_value: str | float | int | None,
    ) -> ValueComparison:
        """Compare one rendered value across platforms."""
        result = self._judge(tableau_value, powerbi_value)
        return ValueComparison(
            label=label,
            tableau_value=tableau_value,
            powerbi_value=powerbi_value,
            status=result[0],
            variance_pct=result[1],
            reason=result[2],
        )

    def compare_visual(self, tableau: Visual, powerbi: Visual) -> VisualComparison:
        """Compare two matched visuals data-point by data-point.

        Power BI is the migration target, so its title/page/type name the
        comparison. Points present only in Tableau are failures (data was
        lost); points present only in Power BI are warnings (additional
        data, per the validation methodology).
        """
        tableau_points = {point.key: point for point in tableau.data_points}
        powerbi_points = {point.key: point for point in powerbi.data_points}

        values: list[ValueComparison] = []
        for key, tableau_point in tableau_points.items():
            powerbi_point = powerbi_points.get(key)
            if powerbi_point is None:
                values.append(
                    ValueComparison(
                        label=_display_label(tableau_point),
                        tableau_value=tableau_point.value,
                        status=ComparisonStatus.FAIL,
                        reason="Missing in Power BI",
                    )
                )
            else:
                values.append(
                    self.compare_value(
                        _display_label(tableau_point),
                        tableau_point.value,
                        powerbi_point.value,
                    )
                )

        for key, powerbi_point in powerbi_points.items():
            if key not in tableau_points:
                values.append(
                    ValueComparison(
                        label=_display_label(powerbi_point),
                        powerbi_value=powerbi_point.value,
                        status=ComparisonStatus.WARNING,
                        reason="Additional in Power BI",
                    )
                )

        return VisualComparison(
            title=powerbi.title,
            page=powerbi.page,
            visual_type=powerbi.visual_type,
            values=values,
            tableau_screenshot=tableau.screenshot,
            powerbi_screenshot=powerbi.screenshot,
        )

    # -- judgement ----------------------------------------------------------

    def _judge(
        self,
        tableau_value: str | float | int | None,
        powerbi_value: str | float | int | None,
    ) -> tuple[ComparisonStatus, float | None, str]:
        """Return (status, variance_pct, reason) for one pair of values."""
        if tableau_value is None or powerbi_value is None:
            side = "Tableau" if tableau_value is None else "Power BI"
            return ComparisonStatus.FAIL, None, f"Missing in {side}"

        tableau_num = parse_number(tableau_value)
        powerbi_num = parse_number(powerbi_value)
        if tableau_num is not None and powerbi_num is not None:
            return self._judge_numeric(tableau_num, powerbi_num)

        tableau_date = parse_date(tableau_value)
        powerbi_date = parse_date(powerbi_value)
        if tableau_date is not None and powerbi_date is not None:
            if tableau_date.date() == powerbi_date.date():
                return ComparisonStatus.PASS, 0.0, ""
            return ComparisonStatus.FAIL, None, "Date mismatch"

        if normalize_text(tableau_value) == normalize_text(powerbi_value):
            return ComparisonStatus.PASS, 0.0, ""
        return ComparisonStatus.FAIL, None, "Text mismatch"

    def _judge_numeric(
        self, tableau: ParsedNumber, powerbi: ParsedNumber
    ) -> tuple[ComparisonStatus, float | None, str]:
        difference = powerbi.value - tableau.value

        # Percentages compare on absolute points: 45% vs 46% is 1pt apart
        # regardless of how large the percentages themselves are.
        if tableau.is_percentage or powerbi.is_percentage:
            if abs(difference) <= self.percentage_tolerance_points:
                return ComparisonStatus.PASS, round(difference, 2), ""
            return ComparisonStatus.FAIL, round(difference, 2), "Percentage mismatch"

        if tableau.value == 0:
            if powerbi.value == 0:
                return ComparisonStatus.PASS, 0.0, ""
            return ComparisonStatus.FAIL, None, "Zero vs non-zero"

        variance_pct = 100 * difference / abs(tableau.value)
        rounded = round(variance_pct, 2)
        if abs(variance_pct) <= self.numeric_pass_pct:
            return ComparisonStatus.PASS, rounded, ""
        if abs(variance_pct) <= self.numeric_warning_pct:
            return ComparisonStatus.WARNING, rounded, "Within warning band"
        return ComparisonStatus.FAIL, rounded, "Value mismatch"


def _display_label(point: DataPoint) -> str:
    return f"{point.series} / {point.label}" if point.series else point.label
