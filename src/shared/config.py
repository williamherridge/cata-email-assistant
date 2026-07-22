"""Application configuration for the lean pilot runtime."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATABASE_PATH = REPO_ROOT / "data" / "processed" / "app" / "cata_email_assistant.db"
DEFAULT_ARTIFACT_ROOT = REPO_ROOT / "data" / "processed" / "artifacts"
DEFAULT_TEMPLATES_DIR = REPO_ROOT / "src" / "admin_portal" / "templates"
DEFAULT_TAXONOMY_CATALOG_PATH = REPO_ROOT / "data" / "analytics" / "taxonomy_catalog.json"


class Settings(BaseSettings):
    """Environment-backed settings."""

    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / "config" / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = Field(default="development", alias="APP_ENV")
    app_host: str = Field(default="127.0.0.1", alias="APP_HOST")
    app_port: int = Field(default=8000, alias="APP_PORT")
    app_debug: bool = Field(default=True, alias="APP_DEBUG")
    secret_key: str = Field(default="dev-secret-key", alias="APP_SECRET_KEY")
    display_timezone: str | None = Field(default=None, alias="APP_DISPLAY_TIMEZONE")

    database_url: str = Field(
        default=f"sqlite:///{DEFAULT_DATABASE_PATH}",
        alias="DATABASE_URL",
    )
    artifact_root: Path = Field(default=DEFAULT_ARTIFACT_ROOT, alias="ARTIFACT_ROOT")
    templates_dir: Path = Field(default=DEFAULT_TEMPLATES_DIR, alias="TEMPLATES_DIR")
    taxonomy_catalog_path: Path = Field(
        default=DEFAULT_TAXONOMY_CATALOG_PATH,
        alias="TAXONOMY_CATALOG_PATH",
    )

    default_gmail_address: str | None = Field(default=None, alias="DEFAULT_GMAIL_ADDRESS")
    default_gmail_aliases: list[str] = Field(default_factory=list, alias="DEFAULT_GMAIL_ALIASES")
    default_gmail_display_name: str = Field(default="CATA Inbox", alias="DEFAULT_GMAIL_DISPLAY_NAME")
    gmail_oauth_credentials_path: Path = Field(
        default=REPO_ROOT / "config" / "credentials.json",
        alias="GOOGLE_OAUTH_CREDENTIALS_PATH",
    )
    gmail_oauth_token_path: Path = Field(
        default=REPO_ROOT / "config" / "token.json",
        alias="GOOGLE_OAUTH_TOKEN_PATH",
    )
    gmail_initial_sync_days: int = Field(default=30, alias="GMAIL_INITIAL_SYNC_DAYS")
    gmail_initial_sync_max_results: int = Field(default=50, alias="GMAIL_INITIAL_SYNC_MAX_RESULTS")
    gmail_test_send_override: str | None = Field(
        default="william@theherridges.com",
        alias="GMAIL_TEST_SEND_OVERRIDE",
    )
    gmail_poll_day_start_hour: int = Field(default=7, alias="GMAIL_POLL_DAY_START_HOUR")
    gmail_poll_day_end_hour: int = Field(default=19, alias="GMAIL_POLL_DAY_END_HOUR")
    gmail_poll_day_interval_minutes: int = Field(default=15, alias="GMAIL_POLL_DAY_INTERVAL_MINUTES")
    gmail_poll_offhours_interval_minutes: int = Field(default=120, alias="GMAIL_POLL_OFFHOURS_INTERVAL_MINUTES")

    @field_validator("default_gmail_aliases", mode="before")
    @classmethod
    def parse_default_gmail_aliases(cls, value):
        if value is None or value == "":
            return []
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        if isinstance(value, (list, tuple, set)):
            return [str(item).strip() for item in value if str(item).strip()]
        return []

    @field_validator(
        "gmail_poll_day_start_hour",
        "gmail_poll_day_end_hour",
        mode="after",
    )
    @classmethod
    def validate_poll_hours(cls, value: int) -> int:
        if value < 0 or value > 23:
            raise ValueError("Polling schedule hours must be between 0 and 23.")
        return value

    @field_validator(
        "gmail_poll_day_interval_minutes",
        "gmail_poll_offhours_interval_minutes",
        mode="after",
    )
    @classmethod
    def validate_poll_intervals(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("Polling intervals must be greater than zero.")
        return value

    @property
    def resolved_database_url(self) -> str:
        """Return a filesystem-safe SQLite URL rooted at the repository when relative."""
        prefix = "sqlite:///"
        if not self.database_url.startswith(prefix):
            return self.database_url

        raw_path = self.database_url.removeprefix(prefix)
        path = Path(raw_path)
        if not path.is_absolute():
            path = REPO_ROOT / path
        return f"{prefix}{path}"

    @property
    def resolved_artifact_root(self) -> Path:
        """Return an absolute artifact root."""
        path = Path(self.artifact_root)
        if not path.is_absolute():
            path = REPO_ROOT / path
        return path


@lru_cache
def get_settings() -> Settings:
    """Return cached settings."""
    return Settings()
