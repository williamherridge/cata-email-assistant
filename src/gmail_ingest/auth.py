"""Gmail API authentication helpers."""

from src.google_workspace.auth import get_google_service

DEFAULT_GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
]


def get_gmail_service(scopes=None, credentials_path=None, token_path=None):
    """Return an authenticated Gmail API service client."""
    return get_google_service(
        "gmail",
        "v1",
        scopes=scopes or DEFAULT_GMAIL_SCOPES,
        credentials_path=credentials_path,
        token_path=token_path,
        allow_interactive=True,
    )
