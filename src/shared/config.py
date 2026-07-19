"""Application configuration for the lean pilot runtime."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATABASE_PATH = REPO_ROOT / "data" / "processed" / "app" / "cata_email_assistant.db"
DEFAULT_ARTIFACT_ROOT = REPO_ROOT / "data" / "processed" / "artifacts"
DEFAULT_TEMPLATES_DIR = REPO_ROOT / "src" / "admin_portal" / "templates"


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

    database_url: str = Field(
        default=f"sqlite:///{DEFAULT_DATABASE_PATH}",
        alias="DATABASE_URL",
    )
    artifact_root: Path = Field(default=DEFAULT_ARTIFACT_ROOT, alias="ARTIFACT_ROOT")
    templates_dir: Path = Field(default=DEFAULT_TEMPLATES_DIR, alias="TEMPLATES_DIR")

    default_gmail_address: str | None = Field(default=None, alias="DEFAULT_GMAIL_ADDRESS")
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
