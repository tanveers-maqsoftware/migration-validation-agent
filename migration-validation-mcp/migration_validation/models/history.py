"""Models for tracking validation runs over time (regression history).

Every completed run appends a :class:`ValidationRunRecord` to
``harness-log.json``; :class:`RunHistoryStats` is the cumulative roll-up shown
at the end of each run and the seed for an executive dashboard later.
"""

from datetime import datetime, timezone

from pydantic import BaseModel, Field


class ValidationRunRecord(BaseModel):
    """One completed validation run, including its self-harness outcome."""

    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    tableau_url: str
    powerbi_url: str
    total_visuals: int = 0
    passed: int = 0
    warnings: int = 0
    failed: int = 0
    pass_rate_pct: float = 0.0
    # Self-harness outcome: check name → "PASS" | "FAIL", e.g.
    # {"completeness": "PASS", "hover_proof": "FAIL"}
    checks: dict[str, str] = Field(default_factory=dict)
    duration: str = Field(default="", description="Human-readable run duration")
    incomplete_items: list[str] = Field(default_factory=list)
    report_path: str = ""

    @property
    def harness_score(self) -> str:
        passed = sum(1 for outcome in self.checks.values() if outcome.upper() == "PASS")
        return f"{passed}/{len(self.checks)}" if self.checks else "n/a"


class RunHistoryStats(BaseModel):
    """Cumulative statistics across all recorded runs."""

    total_runs: int
    average_pass_rate_pct: float
    fully_passed_runs: int
    most_common_failed_check: str | None = None
