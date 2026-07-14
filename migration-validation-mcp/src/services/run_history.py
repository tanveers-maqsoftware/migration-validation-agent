"""Append-only run history persisted to a JSON file.

Replaces the playbook's old approach of having the agent append JSON via
terminal commands — that re-derived file-handling logic every run and
corrupted the log when quoting went wrong. Here the file format is owned by
one class and validated by Pydantic on every read.
"""

import json
from collections import Counter
from pathlib import Path

from src.models.history import RunHistoryStats, ValidationRunRecord


class RunHistoryService:
    """Reads and appends ``ValidationRunRecord`` entries in a JSON array file."""

    def __init__(self, history_path: Path) -> None:
        self.history_path = history_path

    def load(self) -> list[ValidationRunRecord]:
        """All recorded runs, oldest first. A missing file means no runs yet."""
        if not self.history_path.exists():
            return []
        raw = json.loads(self.history_path.read_text(encoding="utf-8"))
        return [ValidationRunRecord.model_validate(entry) for entry in raw]

    def append(self, record: ValidationRunRecord) -> RunHistoryStats:
        """Persist one run and return the updated cumulative statistics."""
        records = self.load() + [record]
        self.history_path.parent.mkdir(parents=True, exist_ok=True)
        self.history_path.write_text(
            json.dumps(
                [entry.model_dump(mode="json") for entry in records], indent=2
            ),
            encoding="utf-8",
        )
        return self.stats(records)

    def stats(self, records: list[ValidationRunRecord] | None = None) -> RunHistoryStats:
        records = self.load() if records is None else records
        if not records:
            return RunHistoryStats(
                total_runs=0, average_pass_rate_pct=0.0, fully_passed_runs=0
            )

        failed_checks = Counter(
            check
            for record in records
            for check, outcome in record.checks.items()
            if outcome.upper() != "PASS"
        )
        return RunHistoryStats(
            total_runs=len(records),
            average_pass_rate_pct=round(
                sum(record.pass_rate_pct for record in records) / len(records), 2
            ),
            fully_passed_runs=sum(
                1 for record in records if record.failed == 0 and record.total_visuals
            ),
            most_common_failed_check=(
                failed_checks.most_common(1)[0][0] if failed_checks else None
            ),
        )
