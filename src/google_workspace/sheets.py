"""Google Sheets helpers for deterministic spreadsheet workflows."""

from __future__ import annotations

from dataclasses import dataclass
import re

from src.google_workspace.auth import get_google_service
from src.shared.config import Settings


TEAM_REGISTRATION_SHEET_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
]

BASE_RECIPIENT_HEADERS = [
    "Team Code",
    "Team Name",
    "Captain(s)",
    "Email Address",
    "Email Provided",
    "League",
    "Minimum Roster",
    "Max Roster",
    "Format",
    "Subject",
    "RosterDueDate",
    "SeasonStartDate",
    "EmailSent",
]

TEAM_REGISTRATION_RECIPIENT_HEADERS = [
    "Team Code",
    "Team Name",
    "Captain(s)",
    "Email Address",
    "Email Provided",
    "Captain USTA Number",
    "League",
    "Registration Type",
    "Facility",
    "Minimum Roster",
    "Max Roster",
    "Format",
    "Subject",
    "RosterDueDate",
    "SeasonStartDate",
    "EmailSent",
    "SourceMessageId",
    "IngestedAt",
]

TEAM_REGISTRATION_FORMULA_HEADERS = [
    "Minimum Roster",
    "Max Roster",
    "Format",
    "RosterDueDate",
    "SeasonStartDate",
]


@dataclass
class DuplicateRecipientRow:
    row_number: int
    row_data: dict[str, str]


class TeamRegistrationRecipientListClient:
    """Manage the RecipientList worksheet for team-registration automation."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.spreadsheet_id = (settings.team_registration_spreadsheet_id or "").strip()
        self.sheet_name = settings.team_registration_sheet_name
        self._service = None
        self._sheet_id = None

    @property
    def service(self):
        if self._service is None:
            self._service = get_google_service(
                "sheets",
                "v4",
                scopes=TEAM_REGISTRATION_SHEET_SCOPES,
                credentials_path=self.settings.gmail_oauth_credentials_path,
                token_path=self.settings.google_sheets_oauth_token_path,
                allow_interactive=False,
            )
        return self._service

    def append_team_registration_row(self, row: dict[str, str]) -> int:
        self.ensure_recipient_sheet_schema()
        values = [[row.get(header, "") for header in TEAM_REGISTRATION_RECIPIENT_HEADERS]]
        response = (
            self.service.spreadsheets()
            .values()
            .append(
                spreadsheetId=self.spreadsheet_id,
                range=f"{self.sheet_name}!A:{self._column_letter(len(TEAM_REGISTRATION_RECIPIENT_HEADERS))}",
                valueInputOption="USER_ENTERED",
                insertDataOption="INSERT_ROWS",
                body={"values": values},
            )
            .execute()
        )
        updated_range = (
            response.get("updates", {}).get("updatedRange")
            or response.get("tableRange")
            or ""
        )
        appended_row_number = self._parse_row_number(updated_range)
        self._copy_formula_columns_to_row(appended_row_number)
        return appended_row_number

    def find_duplicate_row(self, *, team_name: str, captain_name: str, league_value: str) -> DuplicateRecipientRow | None:
        headers, rows = self._read_rows()
        target_key = self._duplicate_key(team_name, captain_name, league_value)
        for index, row in enumerate(rows, start=2):
            row_map = {headers[i]: row[i] if i < len(row) else "" for i in range(len(headers))}
            existing_key = self._duplicate_key(
                row_map.get("Team Name", ""),
                row_map.get("Captain(s)", ""),
                row_map.get("League", ""),
            )
            if existing_key == target_key:
                return DuplicateRecipientRow(row_number=index, row_data=row_map)
        return None

    def ensure_recipient_sheet_schema(self) -> None:
        current_headers = self._read_headers()
        if current_headers == TEAM_REGISTRATION_RECIPIENT_HEADERS:
            return

        working_headers = current_headers.copy()
        requests: list[dict] = []

        for index, expected_header in enumerate(TEAM_REGISTRATION_RECIPIENT_HEADERS):
            if index < len(working_headers) and working_headers[index] == expected_header:
                continue
            if expected_header in working_headers[index + 1 :]:
                raise ValueError(
                    "RecipientList headers are in an unexpected order and cannot be auto-adjusted safely."
                )
            requests.append(
                {
                    "insertDimension": {
                        "range": {
                            "sheetId": self._get_sheet_id(),
                            "dimension": "COLUMNS",
                            "startIndex": index,
                            "endIndex": index + 1,
                        },
                        "inheritFromBefore": index > 0,
                    }
                }
            )
            working_headers.insert(index, expected_header)

        if working_headers[: len(TEAM_REGISTRATION_RECIPIENT_HEADERS)] != TEAM_REGISTRATION_RECIPIENT_HEADERS:
            raise ValueError("RecipientList headers do not match a recognized safe layout.")

        if requests:
            self.service.spreadsheets().batchUpdate(
                spreadsheetId=self.spreadsheet_id,
                body={"requests": requests},
            ).execute()

        (
            self.service.spreadsheets()
            .values()
            .update(
                spreadsheetId=self.spreadsheet_id,
                range=f"{self.sheet_name}!1:1",
                valueInputOption="RAW",
                body={"values": [TEAM_REGISTRATION_RECIPIENT_HEADERS]},
            )
            .execute()
        )

    def _read_rows(self) -> tuple[list[str], list[list[str]]]:
        self.ensure_recipient_sheet_schema()
        headers = self._read_headers()
        response = (
            self.service.spreadsheets()
            .values()
            .get(
                spreadsheetId=self.spreadsheet_id,
                range=f"{self.sheet_name}!A2:{self._column_letter(len(TEAM_REGISTRATION_RECIPIENT_HEADERS))}",
            )
            .execute()
        )
        rows = response.get("values", [])
        return headers, rows

    def _read_headers(self) -> list[str]:
        response = (
            self.service.spreadsheets()
            .values()
            .get(spreadsheetId=self.spreadsheet_id, range=f"{self.sheet_name}!1:1")
            .execute()
        )
        values = response.get("values", [])
        headers = [header.strip() for header in (values[0] if values else [])]
        while headers and not headers[-1]:
            headers.pop()
        return headers

    def _get_sheet_id(self) -> int:
        if self._sheet_id is not None:
            return self._sheet_id
        spreadsheet = (
            self.service.spreadsheets()
            .get(spreadsheetId=self.spreadsheet_id, fields="sheets.properties")
            .execute()
        )
        for sheet in spreadsheet.get("sheets", []):
            properties = sheet.get("properties", {})
            if properties.get("title") == self.sheet_name:
                self._sheet_id = int(properties["sheetId"])
                return self._sheet_id
        raise ValueError(f"Worksheet '{self.sheet_name}' was not found in the configured spreadsheet.")

    def _copy_formula_columns_to_row(self, destination_row: int) -> None:
        if destination_row <= 2:
            return

        source_row = destination_row - 1
        requests = self._build_formula_copy_requests(
            headers=self._read_headers(),
            sheet_id=self._get_sheet_id(),
            source_row=source_row,
            destination_row=destination_row,
        )
        if not requests:
            return
        self.service.spreadsheets().batchUpdate(
            spreadsheetId=self.spreadsheet_id,
            body={"requests": requests},
        ).execute()

    @classmethod
    def _build_formula_copy_requests(
        cls,
        *,
        headers: list[str],
        sheet_id: int,
        source_row: int,
        destination_row: int,
    ) -> list[dict]:
        indices = [headers.index(header) for header in TEAM_REGISTRATION_FORMULA_HEADERS if header in headers]
        if not indices:
            return []

        indices.sort()
        ranges: list[tuple[int, int]] = []
        start = indices[0]
        end = indices[0]
        for index in indices[1:]:
            if index == end + 1:
                end = index
                continue
            ranges.append((start, end))
            start = end = index
        ranges.append((start, end))

        requests: list[dict] = []
        for start_index, end_index in ranges:
            requests.append(
                {
                    "copyPaste": {
                        "source": {
                            "sheetId": sheet_id,
                            "startRowIndex": source_row - 1,
                            "endRowIndex": source_row,
                            "startColumnIndex": start_index,
                            "endColumnIndex": end_index + 1,
                        },
                        "destination": {
                            "sheetId": sheet_id,
                            "startRowIndex": destination_row - 1,
                            "endRowIndex": destination_row,
                            "startColumnIndex": start_index,
                            "endColumnIndex": end_index + 1,
                        },
                        "pasteType": "PASTE_FORMULA",
                        "pasteOrientation": "NORMAL",
                    }
                }
            )
        return requests

    @staticmethod
    def _duplicate_key(team_name: str, captain_name: str, league_value: str) -> tuple[str, str, str]:
        return (
            TeamRegistrationRecipientListClient._normalize_cell(team_name),
            TeamRegistrationRecipientListClient._normalize_cell(captain_name),
            TeamRegistrationRecipientListClient._normalize_cell(league_value),
        )

    @staticmethod
    def _normalize_cell(value: str) -> str:
        return re.sub(r"\s+", " ", (value or "").strip()).casefold()

    @staticmethod
    def _column_letter(index: int) -> str:
        result = ""
        current = index
        while current > 0:
            current, remainder = divmod(current - 1, 26)
            result = chr(65 + remainder) + result
        return result or "A"

    @staticmethod
    def _parse_row_number(range_value: str) -> int:
        match = re.search(r"![A-Z]+(\d+):[A-Z]+(\d+)$", range_value)
        if not match:
            raise ValueError("Could not determine the appended row number from the Google Sheets response.")
        return int(match.group(1))
