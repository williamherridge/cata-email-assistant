# Google OAuth Setup For Gmail Ingestion

This guide creates the `config/credentials.json` file used by the exporter.

## 1. Create Or Select A Google Cloud Project

1. Open Google Cloud Console: `https://console.cloud.google.com/`
2. Create a new project or select an existing one.

## 2. Enable Gmail API

1. Go to `APIs & Services` -> `Library`.
2. Search for `Gmail API`.
3. Click `Enable`.

## 3. Configure OAuth Consent Screen

1. Go to `APIs & Services` -> `OAuth consent screen`.
2. Choose `External` (or `Internal` for Workspace-only org usage).
3. Fill required app fields:
   - App name
   - User support email
   - Developer contact email
4. Save and continue through scopes/test users.
5. Add your Google account under `Test users` if app is in testing mode.

## 4. Create OAuth Client Credentials

1. Go to `APIs & Services` -> `Credentials`.
2. Click `Create Credentials` -> `OAuth client ID`.
3. Application type: `Desktop app`.
4. Name it (example: `cata-email-assistant-local`).
5. Click `Create`.
6. Download the JSON file.

## 5. Place Credentials In This Repo

1. Rename downloaded file to `credentials.json` (optional but recommended).
2. Move it to:
   - `config/credentials.json`

Expected path from the repository root:

- `config/credentials.json`

## 6. Run First Gmail Auth Flow

From repo root:

```bash
source .venv/bin/activate
python -m src.gmail_ingest.export_messages --after 2024-06-01 --before 2026-06-01
```

On first run:

1. Browser opens for Google sign-in/consent.
2. After success, token is saved to:
   - `config/token.json`

Future runs reuse `config/token.json` automatically.

## 7. Run First Google Sheets Auth Flow

From repo root:

```bash
source .venv/bin/activate
python scripts/authorize_google_sheets.py
```

On first run:

1. Browser opens for Google sign-in/consent.
2. After success, a dedicated Sheets token is saved to:
   - `config/sheets_token.json`

This token is intentionally separate from the Gmail token so re-authorizing Gmail does not remove Sheets access.

## Troubleshooting

- `FileNotFoundError` for credentials:
  - Confirm `config/credentials.json` exists and is valid JSON.
- `access_denied` or app not verified:
  - Ensure your Google account is listed as a test user.
- Gmail scope/permission issues:
  - Delete `config/token.json` and re-run the Gmail auth flow to force new consent.
- Sheets scope/permission issues:
  - Delete `config/sheets_token.json` and re-run `python scripts/authorize_google_sheets.py`.
