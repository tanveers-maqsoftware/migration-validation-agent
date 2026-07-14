from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "Migration Validation MCP"

    # Tableau configuration
    TABLEAU_SERVER: str = ""
    TABLEAU_PAT_NAME: str = ""
    TABLEAU_PAT_SECRET: str = ""
    TABLEAU_URL: str = ""  # URL of the Tableau report to validate

    # Power BI configuration
    POWERBI_TENANT_ID: str = ""
    POWERBI_CLIENT_ID: str = ""
    POWERBI_CLIENT_SECRET: str = ""
    POWERBI_URL: str = ""  # URL of the Power BI report to validate

    # Playwright configuration
    PLAYWRIGHT_HEADLESS: bool = True
    PLAYWRIGHT_MCP_URL: str = ""  # URL for Playwright MCP server connection (optional)
    AUTH_STATE_PATH: str = "auth-state.json"  # Saved Playwright session (cookies + localStorage) for signed-in reports

    # Output directories
    SCREENSHOTS_DIR: str = "validation-screenshots"
    REPORTS_DIR: str = "validation-reports"

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )


settings = Settings()