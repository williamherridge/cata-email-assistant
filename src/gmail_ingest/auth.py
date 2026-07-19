"""Gmail API authentication helpers."""

from pathlib import Path

from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

READONLY_SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = REPO_ROOT / "config"
ENV_PATH = CONFIG_DIR / ".env"
CREDENTIALS_PATH = CONFIG_DIR / "credentials.json"
TOKEN_PATH = CONFIG_DIR / "token.json"


def get_gmail_service(scopes=None, credentials_path=None, token_path=None):
    """Return an authenticated Gmail API service client."""
    load_dotenv(ENV_PATH)

    requested_scopes = scopes or READONLY_SCOPES
    credentials_path = Path(credentials_path or CREDENTIALS_PATH)
    token_path = Path(token_path or TOKEN_PATH)

    creds = None
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), requested_scopes)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                str(credentials_path),
                requested_scopes,
            )
            creds = flow.run_local_server(port=0)
        token_path.parent.mkdir(parents=True, exist_ok=True)
        token_path.write_text(creds.to_json(), encoding="utf-8")

    return build("gmail", "v1", credentials=creds)
