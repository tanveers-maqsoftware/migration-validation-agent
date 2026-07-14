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

    # Saved Playwright session (cookies + localStorage) captured by
    # scripts/authenticate.py and passed to Playwright MCP via --storage-state
    # so private reports open without a login wall.
    auth_state_path: Path = Path("auth-state.json")

    # Comparison tolerances (see src/services/comparator.py).
    numeric_tolerance_pct: float = 1.0
    percentage_tolerance_points: float = 1.0

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
