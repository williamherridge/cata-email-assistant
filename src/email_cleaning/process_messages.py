"""Process raw Gmail exports into cleaned email records."""

import argparse
import json
from datetime import datetime
from pathlib import Path

from src.email_cleaning.normalize import clean_email_body

REPO_ROOT = Path(__file__).resolve().parents[2]
RAW_DATA_DIR = REPO_ROOT / "data" / "raw"
PROCESSED_DATA_DIR = REPO_ROOT / "data" / "processed"
CLEANING_VERSION = "v1"


def parse_args():
    parser = argparse.ArgumentParser(description="Clean exported Gmail messages.")
    parser.add_argument(
        "--since",
        required=True,
        help="Inclusive month start in YYYY-MM format.",
    )
    parser.add_argument(
        "--through",
        required=True,
        help="Inclusive month end in YYYY-MM format.",
    )
    return parser.parse_args()


def parse_month(value):
    return datetime.strptime(value, "%Y-%m")


def iter_raw_message_files():
    for path in RAW_DATA_DIR.rglob("*.json"):
        if path.name == "thread_index.json":
            continue
        yield path


def month_in_range(path, since_month, through_month):
    parts = path.relative_to(RAW_DATA_DIR).parts
    if len(parts) < 3:
        return False
    year, month = parts[0], parts[1]
    try:
        file_month = datetime.strptime(f"{year}-{month}", "%Y-%m")
    except ValueError:
        return False
    return since_month <= file_month <= through_month


def build_clean_record(raw_record, source_path):
    body = raw_record.get("body", "")
    cleaned = clean_email_body(body)
    return {
        "id": raw_record.get("id", ""),
        "thread_id": raw_record.get("thread_id", ""),
        "date": raw_record.get("date", ""),
        "from": raw_record.get("from", ""),
        "to": raw_record.get("to", ""),
        "cc": raw_record.get("cc", ""),
        "subject": raw_record.get("subject", ""),
        "labels": raw_record.get("labels", []),
        "raw_body": body,
        "clean_body": cleaned["clean_body"],
        "language_hint": "",
        "has_quoted_text": cleaned["has_quoted_text"],
        "has_signature": cleaned["has_signature"],
        "cleaning_version": CLEANING_VERSION,
        "source_path": source_path,
    }


def write_clean_record(raw_path, record):
    relative = raw_path.relative_to(RAW_DATA_DIR)
    output_path = PROCESSED_DATA_DIR / relative
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(record, indent=2), encoding="utf-8")


def process_messages(since, through):
    since_month = parse_month(since)
    through_month = parse_month(through)
    if since_month > through_month:
        raise ValueError("--since must be earlier than or equal to --through")

    processed_count = 0
    skipped_count = 0

    for raw_path in iter_raw_message_files():
        if not month_in_range(raw_path, since_month, through_month):
            skipped_count += 1
            continue

        try:
            raw_record = json.loads(raw_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            skipped_count += 1
            continue

        record = build_clean_record(
            raw_record=raw_record,
            source_path=str(raw_path.relative_to(REPO_ROOT)),
        )
        write_clean_record(raw_path, record)
        processed_count += 1

    print(f"Processed messages: {processed_count}")
    print(f"Skipped messages: {skipped_count}")
    print(f"Output root: {PROCESSED_DATA_DIR}")


def main():
    args = parse_args()
    process_messages(since=args.since, through=args.through)


if __name__ == "__main__":
    main()

