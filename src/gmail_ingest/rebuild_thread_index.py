"""Rebuild thread_index.json from existing exported message files."""

import json
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
RAW_DATA_DIR = REPO_ROOT / "data" / "raw"
THREAD_INDEX_PATH = RAW_DATA_DIR / "thread_index.json"


def iter_message_files():
    for path in RAW_DATA_DIR.rglob("*.json"):
        if path.name == "thread_index.json":
            continue
        yield path


def build_thread_index():
    thread_index = defaultdict(list)

    for message_file in iter_message_files():
        try:
            message = json.loads(message_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue

        thread_id = message.get("thread_id")
        message_id = message.get("id")
        if not thread_id or not message_id:
            continue

        thread_index[thread_id].append(
            {
                "message_id": message_id,
                "date": message.get("date", ""),
                "subject": message.get("subject", ""),
                "path": str(message_file.relative_to(REPO_ROOT)),
            }
        )

    # Deduplicate by message_id per thread.
    deduped = {}
    for thread_id, entries in thread_index.items():
        by_message_id = {entry["message_id"]: entry for entry in entries}
        deduped[thread_id] = list(by_message_id.values())
    return deduped


def main():
    RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
    thread_index = build_thread_index()
    THREAD_INDEX_PATH.write_text(json.dumps(thread_index, indent=2), encoding="utf-8")
    print(f"Rebuilt thread index with {len(thread_index)} threads.")
    print(f"Wrote: {THREAD_INDEX_PATH}")


if __name__ == "__main__":
    main()

