"""Shared Google API authentication helpers."""

from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build


class GoogleAuthorizationRequiredError(RuntimeError):
    """Raised when a Google API call requires an interactive re-authorization."""


REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = REPO_ROOT / "config"
ENV_PATH = CONFIG_DIR / ".env"
CREDENTIALS_PATH = CONFIG_DIR / "credentials.json"
TOKEN_PATH = CONFIG_DIR / "token.json"


def get_google_service(
    api_name: str,
    api_version: str,
    *,
    scopes: list[str],
    credentials_path: Path | str | None = None,
    token_path: Path | str | None = None,
    allow_interactive: bool = True,
):
    """Return an authenticated Google API service client."""
    creds = get_google_credentials(
        scopes=scopes,
        credentials_path=credentials_path,
        token_path=token_path,
        allow_interactive=allow_interactive,
    )
    return build(api_name, api_version, credentials=creds)


def get_google_credentials(
    *,
    scopes: list[str],
    credentials_path: Path | str | None = None,
    token_path: Path | str | None = None,
    allow_interactive: bool = True,
) -> Credentials:
    """Return authenticated Google API credentials for the requested scopes."""
    load_dotenv(ENV_PATH)

    requested_scopes = scopes
    credentials_path = Path(credentials_path or CREDENTIALS_PATH)
    token_path = Path(token_path or TOKEN_PATH)

    creds = None
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), requested_scopes)
        granted_scopes = set(creds.scopes or [])
        if not set(requested_scopes).issubset(granted_scopes):
            if not allow_interactive:
                raise GoogleAuthorizationRequiredError(
                    "Google authorization is missing one or more required scopes."
                )
            creds = None

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not allow_interactive:
                raise GoogleAuthorizationRequiredError(
                    "Google authorization must be refreshed interactively before this action can continue."
                )
            flow = InstalledAppFlow.from_client_secrets_file(
                str(credentials_path),
                requested_scopes,
            )
            creds = flow.run_local_server(port=0)
        token_path.parent.mkdir(parents=True, exist_ok=True)
        token_path.write_text(creds.to_json(), encoding="utf-8")

    return creds
