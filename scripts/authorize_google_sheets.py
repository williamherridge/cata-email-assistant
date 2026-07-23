"""Run an interactive Google Sheets OAuth flow and persist a dedicated Sheets token."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.google_workspace.auth import get_google_credentials
from src.google_workspace.sheets import TEAM_REGISTRATION_SHEET_SCOPES
from src.shared.config import get_settings


def main() -> None:
    settings = get_settings()
    creds = get_google_credentials(
        scopes=TEAM_REGISTRATION_SHEET_SCOPES,
        credentials_path=settings.gmail_oauth_credentials_path,
        token_path=settings.google_sheets_oauth_token_path,
        allow_interactive=True,
    )
    print(f"Google Sheets authorization saved to {settings.google_sheets_oauth_token_path}")
    print(f"Granted scopes: {', '.join(creds.scopes or TEAM_REGISTRATION_SHEET_SCOPES)}")


if __name__ == "__main__":
    main()
