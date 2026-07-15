"""Unit tests for the value/visual comparison rules."""

import pytest

from migration_validation.models import ComparisonStatus, DataPoint, Platform, Visual, VisualType
from migration_validation.services.comparator import ValueComparator, parse_number


@pytest.fixture
def comparator() -> ValueComparator:
    return ValueComparator(
        numeric_pass_pct=0.0,
        numeric_warning_pct=0.5,
        percentage_tolerance_points=1.0,
    )


class TestParseNumber:
    def test_plain_number(self):
        assert parse_number("1234").value == 1234

    def test_thousands_separators_and_currency(self):
        assert parse_number("$1,234.50").value == 1234.5

    def test_magnitude_suffixes(self):
        assert parse_number("2.27M").value == 2_270_000
        assert parse_number("1.5K").value == 1500
        assert parse_number("3B").value == 3_000_000_000

    def test_percentage_flag(self):
        parsed = parse_number("45.3%")
        assert parsed.value == 45.3
        assert parsed.is_percentage

    def test_accounting_negative(self):
        assert parse_number("($500)").value == -500

    def test_non_numeric_returns_none(self):
        assert parse_number("Region A") is None
        assert parse_number(None) is None


class TestCompareValue:
    def test_equal_numbers_pass(self, comparator):
        result = comparator.compare_value("Sales", "2.27M", "2,270,000")
        assert result.status == ComparisonStatus.PASS
        assert result.variance_pct == 0.0

    def test_small_variance_lands_in_warning_band(self, comparator):
        # 145.6M vs 145.7M is ~0.07% — inside the 0.5% warning band
        result = comparator.compare_value("Revenue", "145.6M", "145.7M")
        assert result.status == ComparisonStatus.WARNING
        assert result.variance_pct == 0.07
        assert result.reason == "Within warning band"

    def test_numbers_beyond_warning_band_fail(self, comparator):
        result = comparator.compare_value("Sales", "$1.25M", "$1.21M")
        assert result.status == ComparisonStatus.FAIL
        assert result.variance_pct == -3.2

    def test_pass_band_is_configurable(self):
        lenient = ValueComparator(
            numeric_pass_pct=1.0, numeric_warning_pct=2.0, percentage_tolerance_points=1.0
        )
        result = lenient.compare_value("Revenue", "145.6M", "145.7M")
        assert result.status == ComparisonStatus.PASS

    def test_percentages_compare_on_points(self, comparator):
        assert (
            comparator.compare_value("Share", "45.3%", "46.0%").status
            == ComparisonStatus.PASS
        )
        assert (
            comparator.compare_value("Share", "45%", "47%").status
            == ComparisonStatus.FAIL
        )

    def test_text_is_case_insensitive(self, comparator):
        result = comparator.compare_value("Region", "REGION  a", "region A")
        assert result.status == ComparisonStatus.PASS

    def test_dates_normalize_across_formats(self, comparator):
        result = comparator.compare_value("Date", "2024-01-15", "Jan 15, 2024")
        assert result.status == ComparisonStatus.PASS

    def test_missing_side_fails(self, comparator):
        result = comparator.compare_value("Sales", "1.2M", None)
        assert result.status == ComparisonStatus.FAIL
        assert "Power BI" in result.reason

    def test_zero_vs_nonzero_fails(self, comparator):
        result = comparator.compare_value("Qty", "0", "5")
        assert result.status == ComparisonStatus.FAIL


class TestCompareVisual:
    def _visual(self, platform: Platform, points: dict[str, str]) -> Visual:
        return Visual(
            platform=platform,
            title="Sales by Region",
            visual_type=VisualType.BAR_CHART,
            data_points=[DataPoint(label=k, value=v) for k, v in points.items()],
        )

    def test_matching_visuals_pass(self, comparator):
        tableau = self._visual(Platform.TABLEAU, {"A": "1.0M", "B": "2.0M"})
        powerbi = self._visual(Platform.POWERBI, {"A": "1,000,000", "B": "2,000,000"})
        comparison = comparator.compare_visual(tableau, powerbi)
        assert comparison.status == ComparisonStatus.PASS
        assert len(comparison.values) == 2

    def test_point_missing_in_powerbi_fails(self, comparator):
        tableau = self._visual(Platform.TABLEAU, {"A": "1.0M", "B": "2.0M"})
        powerbi = self._visual(Platform.POWERBI, {"A": "1.0M"})
        comparison = comparator.compare_visual(tableau, powerbi)
        assert comparison.status == ComparisonStatus.FAIL

    def test_additional_point_in_powerbi_warns(self, comparator):
        tableau = self._visual(Platform.TABLEAU, {"A": "1.0M"})
        powerbi = self._visual(Platform.POWERBI, {"A": "1.0M", "C": "9.0M"})
        comparison = comparator.compare_visual(tableau, powerbi)
        assert comparison.status == ComparisonStatus.WARNING

    def test_labels_match_case_insensitively(self, comparator):
        tableau = self._visual(Platform.TABLEAU, {"region a": "1.0M"})
        powerbi = self._visual(Platform.POWERBI, {"Region A": "1.0M"})
        comparison = comparator.compare_visual(tableau, powerbi)
        assert comparison.status == ComparisonStatus.PASS
