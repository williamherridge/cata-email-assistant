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


def test_find_sorted_open_league_insert_row_inserts_before_first_later_open_league():
    headers = sheets.TEAM_REGISTRATION_RECIPIENT_HEADERS
    rows = [
        ["", "Team A", "Captain A", "", "a@example.com", "", "Mens Weekend - 3.5 - FALL 18+ League", "", "", "", "", "", "", "", "", "", "", ""],
        ["", "Team B", "Captain B", "", "b@example.com", "", "Mens Weekend - 3.5 - FALL 18+ League", "", "", "", "", "", "", "", "", "Yes", "", ""],
        ["", "Team C", "Captain C", "", "c@example.com", "", "Womens WeekEND - 3.0 - FALL 18+ League", "", "", "", "", "", "", "", "", "", "", ""],
    ]

    insert_row = sheets.TeamRegistrationRecipientListClient._find_sorted_open_league_insert_row(
        headers=headers,
        rows=rows,
        league_value="Team Tennis Junior - Orange Ball",
    )

    assert insert_row == 4


def test_find_sorted_open_league_insert_row_returns_row_after_last_equal_open_league():
    headers = sheets.TEAM_REGISTRATION_RECIPIENT_HEADERS
    rows = [
        ["", "Team A", "Captain A", "", "a@example.com", "", "Mens Weekend - 3.5 - FALL 18+ League", "", "", "", "", "", "", "", "", "", "", ""],
        ["", "Team B", "Captain B", "", "b@example.com", "", "Mens Weekend - 3.5 - FALL 18+ League", "", "", "", "", "", "", "", "", "", "", ""],
        ["", "Team C", "Captain C", "", "c@example.com", "", "Womens WeekEND - 3.0 - FALL 18+ League", "", "", "", "", "", "", "", "", "", "", ""],
    ]

    insert_row = sheets.TeamRegistrationRecipientListClient._find_sorted_open_league_insert_row(
        headers=headers,
        rows=rows,
        league_value="Mens Weekend - 3.5 - FALL 18+ League",
    )

    assert insert_row == 4


def test_find_sorted_open_league_insert_row_returns_none_when_matching_league_is_already_processed():
    headers = sheets.TEAM_REGISTRATION_RECIPIENT_HEADERS
    rows = [
        ["8096179001", "Team A", "Captain A", "", "a@example.com", "", "Mens Weekend - 3.5 - FALL 18+ League", "", "", "", "", "", "", "", "", "", "", ""],
        ["8096179002", "Team B", "Captain B", "", "b@example.com", "", "Mens Weekend - 3.5 - FALL 18+ League", "", "", "", "", "", "", "", "", "", "", ""],
        ["", "Team C", "Captain C", "", "c@example.com", "", "Womens WeekEND - 3.0 - FALL 18+ League", "", "", "", "", "", "", "", "", "", "", ""],
    ]

    insert_row = sheets.TeamRegistrationRecipientListClient._find_sorted_open_league_insert_row(
        headers=headers,
        rows=rows,
        league_value="Mens Weekend - 3.5 - FALL 18+ League",
    )

    assert insert_row is None


def test_find_sorted_open_league_insert_row_returns_none_without_open_rows():
    headers = sheets.TEAM_REGISTRATION_RECIPIENT_HEADERS
    rows = [
        ["", "Team A", "Captain A", "", "a@example.com", "", "Mens Weekend - 3.5 - FALL 18+ League", "", "", "", "", "", "", "", "", "Yes", "", ""],
        ["", "Team B", "Captain B", "", "b@example.com", "", "Womens WeekEND - 3.0 - FALL 18+ League", "", "", "", "", "", "", "", "", "Yes", "", ""],
    ]

    insert_row = sheets.TeamRegistrationRecipientListClient._find_sorted_open_league_insert_row(
        headers=headers,
        rows=rows,
        league_value="Mens Weekend - 3.5 - FALL 18+ League",
    )

    assert insert_row is None


class FakeAppendInsertSheetsService:
    def __init__(self):
        self.append_calls: list[dict] = []
        self.update_calls: list[dict] = []
        self.batch_update_calls: list[dict] = []

    def spreadsheets(self):
        return self

    def values(self):
        return self

    def append(self, **kwargs):
        self.append_calls.append(kwargs)
        return _ExecutableResponse({"updates": {"updatedRange": "RecipientList!A10:R10"}})

    def update(self, **kwargs):
        self.update_calls.append(kwargs)
        return _ExecutableResponse({})

    def batchUpdate(self, **kwargs):
        self.batch_update_calls.append(kwargs)
        return _ExecutableResponse({})


class _ExecutableResponse:
    def __init__(self, payload):
        self.payload = payload

    def execute(self):
        return self.payload


def test_append_team_registration_row_inserts_into_sorted_open_league_block(monkeypatch):
    client = sheets.TeamRegistrationRecipientListClient(DummySettings())
    fake_service = FakeAppendInsertSheetsService()
    copied_rows: list[int] = []

    client._service = fake_service
    monkeypatch.setattr(client, "ensure_recipient_sheet_schema", lambda: None)
    monkeypatch.setattr(
        client,
        "_read_rows",
        lambda: (
            sheets.TEAM_REGISTRATION_RECIPIENT_HEADERS,
            [
                ["", "Team A", "Captain A", "", "a@example.com", "", "Mens Weekend - 3.5 - FALL 18+ League", "", "", "", "", "", "", "", "", "", "", ""],
                ["", "Team B", "Captain B", "", "b@example.com", "", "Womens WeekEND - 3.0 - FALL 18+ League", "", "", "", "", "", "", "", "", "", "", ""],
            ],
        ),
    )
    monkeypatch.setattr(client, "_get_sheet_id", lambda: 42)
    monkeypatch.setattr(client, "_copy_formula_columns_to_row", lambda row_number: copied_rows.append(row_number))

    inserted_row = client.append_team_registration_row(
        {
            "Team Name": "New Team",
            "Captain(s)": "New Captain",
            "League": "Team Tennis Junior - Orange Ball",
        }
    )

    assert inserted_row == 3
    assert fake_service.append_calls == []
    assert len(fake_service.batch_update_calls) == 1
    request = fake_service.batch_update_calls[0]["body"]["requests"][0]["insertDimension"]
    assert request["range"] == {
        "sheetId": 42,
        "dimension": "ROWS",
        "startIndex": 2,
        "endIndex": 3,
    }
    assert request["inheritFromBefore"] is True
    assert fake_service.update_calls[0]["range"] == "RecipientList!A3:R3"
    assert fake_service.update_calls[0]["body"]["values"][0][1] == "New Team"
    assert copied_rows == [3]


def test_append_team_registration_row_appends_when_matching_league_is_already_processed(monkeypatch):
    client = sheets.TeamRegistrationRecipientListClient(DummySettings())
    fake_service = FakeAppendInsertSheetsService()
    copied_rows: list[int] = []

    client._service = fake_service
    monkeypatch.setattr(client, "ensure_recipient_sheet_schema", lambda: None)
    monkeypatch.setattr(
        client,
        "_read_rows",
        lambda: (
            sheets.TEAM_REGISTRATION_RECIPIENT_HEADERS,
            [
                ["8096179001", "Team A", "Captain A", "", "a@example.com", "", "Mens Weekend - 3.5 - FALL 18+ League", "", "", "", "", "", "", "", "", "", "", ""],
                ["8096179002", "Team B", "Captain B", "", "b@example.com", "", "Mens Weekend - 3.5 - FALL 18+ League", "", "", "", "", "", "", "", "", "", "", ""],
            ],
        ),
    )
    monkeypatch.setattr(client, "_copy_formula_columns_to_row", lambda row_number: copied_rows.append(row_number))

    appended_row = client.append_team_registration_row(
        {
            "Team Name": "New Team",
            "Captain(s)": "New Captain",
            "League": "Mens Weekend - 3.5 - FALL 18+ League",
        }
    )

    assert appended_row == 10
    assert len(fake_service.append_calls) == 1
    assert fake_service.update_calls == []
    assert fake_service.batch_update_calls == []
    assert copied_rows == [10]
