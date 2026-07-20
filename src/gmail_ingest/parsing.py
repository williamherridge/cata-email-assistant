"""Helpers for Gmail payload parsing."""

from __future__ import annotations

import base64
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html import escape
from html.parser import HTMLParser


class _HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._chunks: list[str] = []
        self._skip_depth = 0

    _BLOCK_TAGS = {
        "address",
        "article",
        "aside",
        "blockquote",
        "caption",
        "div",
        "dl",
        "dt",
        "dd",
        "fieldset",
        "figcaption",
        "figure",
        "footer",
        "form",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "header",
        "hr",
        "li",
        "main",
        "nav",
        "ol",
        "p",
        "pre",
        "section",
        "table",
        "tbody",
        "td",
        "tfoot",
        "th",
        "thead",
        "tr",
        "ul",
    }
    _SKIP_CONTENT_TAGS = {"head", "script", "style", "title"}

    def _append_break(self, minimum_breaks: int = 1) -> None:
        if not self._chunks:
            self._chunks.append("\n" * minimum_breaks)
            return
        trailing_breaks = len(self._chunks[-1]) - len(self._chunks[-1].rstrip("\n"))
        if trailing_breaks >= minimum_breaks:
            return
        self._chunks.append("\n" * (minimum_breaks - trailing_breaks))

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self._SKIP_CONTENT_TAGS:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        if tag == "br":
            self._append_break()
            return
        if tag in self._BLOCK_TAGS:
            self._append_break(2 if tag in {"p", "div", "table", "tr"} else 1)

    def handle_endtag(self, tag: str) -> None:
        if tag in self._SKIP_CONTENT_TAGS and self._skip_depth:
            self._skip_depth -= 1
            return
        if self._skip_depth:
            return
        if tag in self._BLOCK_TAGS:
            self._append_break(2 if tag in {"p", "div", "table", "tr"} else 1)

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        normalized = data.replace("\xa0", " ")
        if not normalized.strip():
            return
        normalized = re.sub(r"[ \t\r\f\v]+", " ", normalized)
        self._chunks.append(normalized)

    def get_text(self) -> str:
        text = "".join(self._chunks)
        lines = [re.sub(r" {2,}", " ", line).strip() for line in text.splitlines()]
        collapsed: list[str] = []
        previous_blank = True
        for line in lines:
            if not line:
                if not previous_blank:
                    collapsed.append("")
                previous_blank = True
                continue
            collapsed.append(line)
            previous_blank = False
        return "\n".join(collapsed).strip()


class _SafeHTMLRenderer(HTMLParser):
    _ALLOWED_TAGS = {
        "a",
        "b",
        "blockquote",
        "br",
        "code",
        "div",
        "em",
        "hr",
        "i",
        "li",
        "ol",
        "p",
        "pre",
        "span",
        "strong",
        "table",
        "tbody",
        "td",
        "th",
        "thead",
        "tr",
        "u",
        "ul",
    }
    _DROP_CONTENT_TAGS = {"head", "script", "style", "title"}
    _VOID_TAGS = {"br", "hr"}

    def __init__(self) -> None:
        super().__init__()
        self._output: list[str] = []
        self._drop_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self._DROP_CONTENT_TAGS:
            self._drop_depth += 1
            return
        if self._drop_depth or tag not in self._ALLOWED_TAGS:
            return
        rendered_attrs: list[str] = []
        if tag == "a":
            href = next((value for key, value in attrs if key == "href" and value), None)
            if href and href.startswith(("http://", "https://", "mailto:")):
                rendered_attrs.append(f'href="{escape(href, quote=True)}"')
                rendered_attrs.append('target="_blank"')
                rendered_attrs.append('rel="noopener noreferrer nofollow"')
        elif tag in {"td", "th"}:
            for key in ("colspan", "rowspan"):
                value = next((candidate for attr, candidate in attrs if attr == key and candidate), None)
                if value and value.isdigit():
                    rendered_attrs.append(f'{key}="{escape(value, quote=True)}"')
        attr_suffix = f" {' '.join(rendered_attrs)}" if rendered_attrs else ""
        if tag in self._VOID_TAGS:
            self._output.append(f"<{tag}{attr_suffix}>")
            return
        self._output.append(f"<{tag}{attr_suffix}>")

    def handle_endtag(self, tag: str) -> None:
        if tag in self._DROP_CONTENT_TAGS and self._drop_depth:
            self._drop_depth -= 1
            return
        if self._drop_depth or tag not in self._ALLOWED_TAGS or tag in self._VOID_TAGS:
            return
        self._output.append(f"</{tag}>")

    def handle_data(self, data: str) -> None:
        if self._drop_depth:
            return
        self._output.append(escape(data))

    def get_html(self) -> str:
        return "".join(self._output).strip()


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

    html_text = extract_body_html(payload)
    if html_text:
        parser = _HTMLTextExtractor()
        parser.feed(html_text)
        return parser.get_text().strip()

    direct_data = payload.get("body", {}).get("data")
    if direct_data:
        return decode_body(direct_data)

    return ""


def extract_body_html(payload: dict) -> str:
    html_data = find_part(payload, "text/html")
    if html_data:
        return decode_body(html_data)

    if payload.get("mimeType") == "text/html":
        direct_data = payload.get("body", {}).get("data")
        if direct_data:
            return decode_body(direct_data)
    return ""


def sanitize_email_html(html: str) -> str:
    if not html.strip():
        return ""
    parser = _SafeHTMLRenderer()
    parser.feed(html)
    return parser.get_html()


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
