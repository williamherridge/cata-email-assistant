from pathlib import Path

from src.google_workspace import sheets


class DummySettings:
    gmail_oauth_credentials_path = Path("config/credentials.json")
    gmail_oauth_token_path = Path("config/token.json")
    google_sheets_oauth_token_path = Path("config/sheets_token.json")
    team_registration_spreadsheet_id = "sheet-123"
    team_registration_sheet_name = "RecipientList"


def test_team_registration_sheets_client_uses_dedicated_sheets_token(monkeypatch):
    captured: dict[str, object] = {}

    def fake_get_google_service(api_name, api_version, *, scopes, credentials_path, token_path, allow_interactive):
        captured.update(
            {
                "api_name": api_name,
                "api_version": api_version,
                "scopes": scopes,
                "credentials_path": credentials_path,
                "token_path": token_path,
                "allow_interactive": allow_interactive,
            }
        )
        return object()

    monkeypatch.setattr(sheets, "get_google_service", fake_get_google_service)

    client = sheets.TeamRegistrationRecipientListClient(DummySettings())
    _ = client.service

    assert captured["api_name"] == "sheets"
    assert captured["api_version"] == "v4"
    assert captured["credentials_path"] == DummySettings.gmail_oauth_credentials_path
    assert captured["token_path"] == DummySettings.google_sheets_oauth_token_path
    assert captured["allow_interactive"] is False


def test_build_formula_copy_requests_uses_named_headers_and_groups_ranges():
    requests = sheets.TeamRegistrationRecipientListClient._build_formula_copy_requests(
        headers=sheets.TEAM_REGISTRATION_RECIPIENT_HEADERS,
        sheet_id=42,
        source_row=10,
        destination_row=11,
    )

    assert len(requests) == 2

    first = requests[0]["copyPaste"]
    assert first["source"] == {
        "sheetId": 42,
        "startRowIndex": 9,
        "endRowIndex": 10,
        "startColumnIndex": 9,
        "endColumnIndex": 12,
    }
    assert first["destination"] == {
        "sheetId": 42,
        "startRowIndex": 10,
        "endRowIndex": 11,
        "startColumnIndex": 9,
        "endColumnIndex": 12,
    }
    assert first["pasteType"] == "PASTE_FORMULA"

    second = requests[1]["copyPaste"]
    assert second["source"] == {
        "sheetId": 42,
        "startRowIndex": 9,
        "endRowIndex": 10,
        "startColumnIndex": 13,
        "endColumnIndex": 15,
    }
    assert second["destination"] == {
        "sheetId": 42,
        "startRowIndex": 10,
        "endRowIndex": 11,
        "startColumnIndex": 13,
        "endColumnIndex": 15,
    }
