"""Unit tests for the run-history log and its cumulative statistics."""

from src.models.history import ValidationRunRecord
from src.services.run_history import RunHistoryService


def _record(pass_rate: float, failed: int = 0, checks: dict | None = None) -> ValidationRunRecord:
    return ValidationRunRecord(
        tableau_url="https://tableau.example/view",
        powerbi_url="https://powerbi.example/report",
        total_visuals=5,
        passed=4,
        warnings=1,
        failed=failed,
        pass_rate_pct=pass_rate,
        checks=checks or {},
    )


def test_load_missing_file_returns_empty(tmp_path):
    service = RunHistoryService(tmp_path / "harness-log.json")
    assert service.load() == []
    assert service.stats().total_runs == 0


def test_append_persists_and_accumulates(tmp_path):
    service = RunHistoryService(tmp_path / "harness-log.json")

    stats = service.append(_record(100.0))
    assert stats.total_runs == 1

    stats = service.append(_record(80.0, failed=1))
    assert stats.total_runs == 2
    assert stats.average_pass_rate_pct == 90.0
    assert stats.fully_passed_runs == 1

    # A fresh service instance reads the same file back.
    reloaded = RunHistoryService(tmp_path / "harness-log.json").load()
    assert len(reloaded) == 2
    assert reloaded[0].pass_rate_pct == 100.0


def test_most_common_failed_check(tmp_path):
    service = RunHistoryService(tmp_path / "harness-log.json")
    service.append(_record(90.0, checks={"completeness": "PASS", "hover_proof": "FAIL"}))
    service.append(_record(95.0, checks={"completeness": "PASS", "hover_proof": "FAIL"}))
    stats = service.append(_record(99.0, checks={"scroll_proof": "FAIL"}))

    assert stats.most_common_failed_check == "hover_proof"


def test_harness_score():
    record = _record(90.0, checks={"a": "PASS", "b": "FAIL", "c": "PASS"})
    assert record.harness_score == "2/3"
    assert _record(90.0).harness_score == "n/a"
