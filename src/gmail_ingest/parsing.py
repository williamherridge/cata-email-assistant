"""Helpers for Gmail payload parsing."""

from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser


class _HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._chunks: list[str] = []

    def handle_data(self, data: str) -> None:
        self._chunks.append(data)

    def get_text(self) -> str:
        return " ".join(chunk.strip() for chunk in self._chunks if chunk.strip())


@dataclass
class ParsedParticipant:
    display_name: str | None
    email_address: str


def decode_body(data: str | None) -> str:
    if not data:
        return ""
    padding = "=" * (-len(data) % 4)
    decoded = base64.urlsafe_b64decode(data + padding)
    return decoded.decode("utf-8", errors="replace")


def find_part(payload: dict, mime_type: str) -> str | None:
    if payload.get("mimeType") == mime_type and payload.get("body", {}).get("data"):
        return payload["body"]["data"]

    for part in payload.get("parts", []):
        result = find_part(part, mime_type)
        if result:
            return result
    return None


def extract_body_text(payload: dict) -> str:
    plain_data = find_part(payload, "text/plain")
    if plain_data:
        return decode_body(plain_data)

    html_data = find_part(payload, "text/html")
    if html_data:
        parser = _HTMLTextExtractor()
        parser.feed(decode_body(html_data))
        return parser.get_text().strip()

    direct_data = payload.get("body", {}).get("data")
    if direct_data:
        return decode_body(direct_data)

    return ""


def headers_to_dict(headers: list[dict]) -> dict[str, str]:
    return {header["name"].lower(): header["value"] for header in headers}


def parse_datetime_header(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError, IndexError):
        return None
    if parsed.tzinfo is not None:
        return parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def parse_internal_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromtimestamp(int(value) / 1000, tz=timezone.utc).replace(tzinfo=None)
    except (TypeError, ValueError):
        return None


def parse_email_address(raw_value: str | None) -> ParsedParticipant | None:
    if not raw_value:
        return None
    value = raw_value.strip()
    if not value:
        return None
    if "<" in value and value.endswith(">"):
        display_name, email_part = value.rsplit("<", 1)
        return ParsedParticipant(
            display_name=display_name.strip().strip('"') or None,
            email_address=email_part[:-1].strip(),
        )
    return ParsedParticipant(display_name=None, email_address=value)


def parse_address_list(raw_value: str | None) -> list[ParsedParticipant]:
    if not raw_value:
        return []
    participants: list[ParsedParticipant] = []
    for segment in raw_value.split(","):
        participant = parse_email_address(segment)
        if participant:
            participants.append(participant)
    return participants


def collect_attachment_metadata(payload: dict) -> list[dict]:
    attachments: list[dict] = []

    def walk(part: dict) -> None:
        body = part.get("body", {})
        attachment_id = body.get("attachmentId")
        filename = part.get("filename")
        if attachment_id or filename:
            attachments.append(
                {
                    "gmail_attachment_id": attachment_id,
                    "filename": filename or None,
                    "mime_type": part.get("mimeType"),
                    "size_bytes": body.get("size"),
                    "is_inline": bool(part.get("headers") and any(h.get("name", "").lower() == "content-id" for h in part["headers"])),
                }
            )
        for child in part.get("parts", []):
            walk(child)

    walk(payload)
    return attachments
