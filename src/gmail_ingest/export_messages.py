"""Export Gmail messages for a date range."""

import argparse
import base64
import json
from collections import defaultdict
from datetime import datetime
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from pathlib import Path

from src.gmail_ingest.auth import get_gmail_service

REPO_ROOT = Path(__file__).resolve().parents[2]
RAW_DATA_DIR = REPO_ROOT / "data" / "raw"


class _HTMLTextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self._chunks = []

    def handle_data(self, data):
        self._chunks.append(data)

    def get_text(self):
        return " ".join(chunk.strip() for chunk in self._chunks if chunk.strip())


def parse_args():
    parser = argparse.ArgumentParser(description="Export Gmail messages to JSON.")
    parser.add_argument("--after", required=True, help="Start date (YYYY-MM-DD).")
    parser.add_argument("--before", required=True, help="End date (YYYY-MM-DD).")
    return parser.parse_args()


def format_query_date(date_str):
    return datetime.strptime(date_str, "%Y-%m-%d").strftime("%Y/%m/%d")


def build_query(after_date, before_date):
    return f"after:{format_query_date(after_date)} before:{format_query_date(before_date)}"


def decode_body(data):
    if not data:
        return ""
    padding = "=" * (-len(data) % 4)
    decoded = base64.urlsafe_b64decode(data + padding)
    return decoded.decode("utf-8", errors="replace")


def find_part(payload, mime_type):
    if payload.get("mimeType") == mime_type and payload.get("body", {}).get("data"):
        return payload["body"]["data"]

    for part in payload.get("parts", []):
        result = find_part(part, mime_type)
        if result:
            return result
    return None


def extract_body(payload):
    plain_data = find_part(payload, "text/plain")
    if plain_data:
        return decode_body(plain_data)

    html_data = find_part(payload, "text/html")
    if html_data:
        html = decode_body(html_data)
        parser = _HTMLTextExtractor()
        parser.feed(html)
        return parser.get_text().strip()

    direct_data = payload.get("body", {}).get("data")
    if direct_data:
        return decode_body(direct_data)

    return ""


def headers_to_dict(headers):
    return {header["name"].lower(): header["value"] for header in headers}


def get_message_timestamp(message):
    internal_date_ms = message.get("internalDate")
    if internal_date_ms:
        timestamp = datetime.fromtimestamp(int(internal_date_ms) / 1000)
        return timestamp

    headers = headers_to_dict(message.get("payload", {}).get("headers", []))
    date_header = headers.get("date")
    if date_header:
        try:
            return parsedate_to_datetime(date_header)
        except (TypeError, ValueError):
            pass
    return datetime.utcnow()


def serialize_message(message):
    payload = message.get("payload", {})
    headers = headers_to_dict(payload.get("headers", []))

    return {
        "id": message.get("id"),
        "thread_id": message.get("threadId"),
        "subject": headers.get("subject", ""),
        "from": headers.get("from", ""),
        "to": headers.get("to", ""),
        "cc": headers.get("cc", ""),
        "date": headers.get("date", ""),
        "labels": message.get("labelIds", []),
        "body": extract_body(payload),
    }


def save_message(message_json, timestamp):
    output_dir = RAW_DATA_DIR / timestamp.strftime("%Y") / timestamp.strftime("%m")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{message_json['id']}.json"
    output_path.write_text(json.dumps(message_json, indent=2), encoding="utf-8")
    return output_path


def load_existing_thread_index():
    thread_index_path = RAW_DATA_DIR / "thread_index.json"
    if not thread_index_path.exists():
        return {}

    try:
        return json.loads(thread_index_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def merge_thread_entries(existing_entries, new_entries):
    by_message_id = {entry["message_id"]: entry for entry in existing_entries}
    for entry in new_entries:
        by_message_id[entry["message_id"]] = entry
    return list(by_message_id.values())


def export_messages(after_date, before_date):
    service = get_gmail_service()
    query = build_query(after_date, before_date)

    new_thread_entries = defaultdict(list)
    page_token = None
    total = 0

    while True:
        response = (
            service.users()
            .messages()
            .list(
                userId="me",
                q=query,
                maxResults=500,
                pageToken=page_token,
            )
            .execute()
        )

        messages = response.get("messages", [])
        for item in messages:
            full_message = (
                service.users()
                .messages()
                .get(userId="me", id=item["id"], format="full")
                .execute()
            )

            message_json = serialize_message(full_message)
            timestamp = get_message_timestamp(full_message)
            output_path = save_message(message_json, timestamp)

            new_thread_entries[message_json["thread_id"]].append(
                {
                    "message_id": message_json["id"],
                    "date": message_json["date"],
                    "subject": message_json["subject"],
                    "path": str(output_path.relative_to(REPO_ROOT)),
                }
            )
            total += 1

        page_token = response.get("nextPageToken")
        if not page_token:
            break

    RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
    existing_index = load_existing_thread_index()
    merged_index = {}

    all_thread_ids = set(existing_index.keys()) | set(new_thread_entries.keys())
    for thread_id in all_thread_ids:
        existing_entries = existing_index.get(thread_id, [])
        new_entries = new_thread_entries.get(thread_id, [])
        merged_index[thread_id] = merge_thread_entries(existing_entries, new_entries)

    thread_index_path = RAW_DATA_DIR / "thread_index.json"
    thread_index_path.write_text(
        json.dumps(merged_index, indent=2),
        encoding="utf-8",
    )

    print(f"Export complete. Messages exported: {total}")
    print(f"Thread index written to: {thread_index_path}")


def main():
    args = parse_args()
    export_messages(after_date=args.after, before_date=args.before)


if __name__ == "__main__":
    main()
