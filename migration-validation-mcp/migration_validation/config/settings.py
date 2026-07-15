"""Application settings, overridable via environment variables or ``.env``.

Example: setting ``NUMERIC_TOLERANCE_PCT=0.5`` in ``.env`` tightens the
numeric comparison tolerance without touching code.
"""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Migration Validation MCP"

    # Where MarkdownReportBuilder writes validation reports.
    reports_dir: Path = Path("validation-reports")

    # Where Playwright MCP's --output-dir points. Screenshots are the only
    # thing that belongs here, but other browser_* tools (console_messages,
    # snapshot, network_request) also honor --output-dir if the agent passes
    # them a filename — ScreenshotDirCleaner sweeps anything non-image out to
    # debug_artifacts_dir so this folder stays screenshots-only.
    screenshots_dir: Path = Path("validation-screenshots")
    debug_artifacts_dir: Path = Path("playwright-debug")

    # Saved Playwright session (cookies + localStorage) captured by
    # scripts/authenticate.py and passed to Playwright MCP via --storage-state
    # so private reports open without a login wall.
    auth_state_path: Path = Path("auth-state.json")

    # Comparison bands for numeric values (see migration_validation/services/comparator.py):
    # variance <= pass band → PASS; <= warning band → WARNING; above → FAIL.
    # Defaults follow the validation methodology: 0% = pass, <0.5% = warning.
    numeric_pass_pct: float = 0.0
    numeric_warning_pct: float = 0.5
    percentage_tolerance_points: float = 1.0

    # Where record_validation_run appends its per-run harness records.
    history_path: Path = Path("harness-log.json")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
