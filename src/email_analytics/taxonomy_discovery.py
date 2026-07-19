"""Build review artifacts to discover an email taxonomy from cleaned messages."""

import argparse
import json
import random
import re
from collections import Counter, defaultdict
from datetime import datetime
from email.utils import parsedate_to_datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PROCESSED_DATA_DIR = REPO_ROOT / "data" / "processed"
ANALYTICS_DATA_DIR = REPO_ROOT / "data" / "analytics" / "taxonomy_discovery"
STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "at",
    "be",
    "by",
    "for",
    "from",
    "hi",
    "i",
    "in",
    "is",
    "it",
    "me",
    "my",
    "of",
    "on",
    "or",
    "re",
    "regarding",
    "regards",
    "request",
    "thanks",
    "that",
    "the",
    "this",
    "to",
    "we",
    "with",
    "you",
    "your",
}


def parse_args():
    parser = argparse.ArgumentParser(
        description="Create taxonomy discovery artifacts from cleaned emails.",
    )
    parser.add_argument("--since", required=True, help="Inclusive month start YYYY-MM.")
    parser.add_argument("--through", required=True, help="Inclusive month end YYYY-MM.")
    parser.add_argument(
        "--sample-size",
        type=int,
        default=150,
        help="Number of messages to include in the review sample.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for repeatable sampling.",
    )
    return parser.parse_args()


def parse_month(value):
    return datetime.strptime(value, "%Y-%m")


def iter_processed_files():
    for path in PROCESSED_DATA_DIR.rglob("*.json"):
        yield path


def month_in_range(path, since_month, through_month):
    parts = path.relative_to(PROCESSED_DATA_DIR).parts
    if len(parts) < 3:
        return False
    try:
        file_month = datetime.strptime(f"{parts[0]}-{parts[1]}", "%Y-%m")
    except ValueError:
        return False
    return since_month <= file_month <= through_month


def load_records(since, through):
    since_month = parse_month(since)
    through_month = parse_month(through)
    if since_month > through_month:
        raise ValueError("--since must be earlier than or equal to --through")

    records = []
    for path in iter_processed_files():
        if not month_in_range(path, since_month, through_month):
            continue

        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue

        record["_path"] = path
        records.append(record)
    return records


def load_previous_sample_ids(since, through):
    previous_ids = set()
    slug = f"{since}_to_{through}"

    if not ANALYTICS_DATA_DIR.exists():
        return previous_ids

    for run_dir in ANALYTICS_DATA_DIR.iterdir():
        if not run_dir.is_dir() or not run_dir.name.startswith(f"{slug}_"):
            continue

        sample_path = run_dir / f"{slug}_sample.json"
        if not sample_path.exists():
            continue

        try:
            rows = json.loads(sample_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue

        for row in rows:
            sample_id = row.get("id")
            if sample_id:
                previous_ids.add(sample_id)

    return previous_ids


def parse_record_datetime(record):
    date_value = record.get("date", "")
    if not date_value:
        return datetime.max

    try:
        parsed = parsedate_to_datetime(date_value)
    except (TypeError, ValueError, IndexError):
        return datetime.max

    if parsed.tzinfo is not None:
        return parsed.astimezone().replace(tzinfo=None)
    return parsed


def build_thread_roots(records):
    roots_by_thread = {}

    for record in records:
        thread_id = record.get("thread_id") or record.get("id")
        current_best = roots_by_thread.get(thread_id)
        candidate_key = (parse_record_datetime(record), record.get("id", ""))

        if current_best is None:
            roots_by_thread[thread_id] = record
            continue

        best_key = (
            parse_record_datetime(current_best),
            current_best.get("id", ""),
        )
        if candidate_key < best_key:
            roots_by_thread[thread_id] = record

    return list(roots_by_thread.values())


def body_snippet(text, length=280):
    snippet = re.sub(r"\s+", " ", (text or "")).strip()
    if len(snippet) <= length:
        return snippet
    return snippet[: length - 3].rstrip() + "..."


def tokenize(text):
    return re.findall(r"[a-z0-9']+", (text or "").lower())


def extract_keywords(record, limit=6):
    subject_tokens = tokenize(record.get("subject", ""))
    body_tokens = tokenize(record.get("clean_body", ""))
    counts = Counter(
        token
        for token in subject_tokens + body_tokens
        if len(token) > 2 and token not in STOPWORDS and not token.isdigit()
    )
    return [token for token, _ in counts.most_common(limit)]


def classify_direction(record):
    labels = set(record.get("labels", []))
    if "SENT" in labels:
        return "sent"
    if "INBOX" in labels:
        return "inbound"
    return "other"


def group_key(record):
    keywords = extract_keywords(record, limit=3)
    if keywords:
        return " / ".join(keywords)
    subject = (record.get("subject") or "").strip().lower()
    if subject:
        return subject[:80]
    return "uncategorized"


def build_summary(records):
    direction_counts = Counter()
    label_counts = Counter()
    sender_domain_counts = Counter()
    subject_keyword_counts = Counter()
    groups = defaultdict(list)

    for record in records:
        direction_counts[classify_direction(record)] += 1

        for label in record.get("labels", []):
            label_counts[label] += 1

        from_value = record.get("from", "")
        domain_match = re.search(r"@([A-Za-z0-9.-]+\.[A-Za-z]{2,})", from_value)
        if domain_match:
            sender_domain_counts[domain_match.group(1).lower()] += 1

        for keyword in extract_keywords(record, limit=4):
            subject_keyword_counts[keyword] += 1

        groups[group_key(record)].append(record)

    candidate_groups = []
    for key, grouped_records in groups.items():
        candidate_groups.append(
            {
                "candidate_label": key,
                "message_count": len(grouped_records),
                "example_subjects": [
                    item.get("subject", "") for item in grouped_records[:3]
                ],
                "example_ids": [item.get("id", "") for item in grouped_records[:3]],
            }
        )

    candidate_groups.sort(
        key=lambda item: (-item["message_count"], item["candidate_label"]),
    )

    return {
        "record_count": len(records),
        "direction_counts": dict(direction_counts),
        "top_labels": label_counts.most_common(15),
        "top_sender_domains": sender_domain_counts.most_common(20),
        "top_keywords": subject_keyword_counts.most_common(40),
        "candidate_categories": candidate_groups[:60],
    }


def build_review_sample(records, sample_size, seed, since, through):
    rng = random.Random(seed)
    previous_sample_ids = load_previous_sample_ids(since, through)
    thread_roots = build_thread_roots(records)
    eligible_roots = [
        record for record in thread_roots if record.get("id") not in previous_sample_ids
    ]

    sample_count = min(sample_size, len(eligible_roots))
    sampled = rng.sample(eligible_roots, sample_count) if sample_count else []

    review_rows = []
    for record in sampled:
        review_rows.append(
            {
                "id": record.get("id", ""),
                "thread_id": record.get("thread_id", ""),
                "date": record.get("date", ""),
                "direction": classify_direction(record),
                "from": record.get("from", ""),
                "subject": record.get("subject", ""),
                "labels": record.get("labels", []),
                "keywords": extract_keywords(record),
                "snippet": body_snippet(record.get("clean_body", "")),
                "suggested_group": group_key(record),
                "review_notes": "",
                "approved_category": "",
                "approved_subcategory": "",
            }
        )
    return {
        "review_rows": review_rows,
        "prior_sampled_message_count": len(previous_sample_ids),
        "thread_root_count": len(thread_roots),
        "eligible_thread_root_count": len(eligible_roots),
    }


def write_outputs(summary, sample_result, since, through, sample_size, seed):
    ANALYTICS_DATA_DIR.mkdir(parents=True, exist_ok=True)

    slug = f"{since}_to_{through}"
    run_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = ANALYTICS_DATA_DIR / f"{slug}_{run_timestamp}"
    run_dir.mkdir(parents=True, exist_ok=True)

    summary_path = run_dir / f"{slug}_summary.json"
    sample_path = run_dir / f"{slug}_sample.json"
    manifest_path = run_dir / f"{slug}_manifest.json"

    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    sample_path.write_text(
        json.dumps(sample_result["review_rows"], indent=2),
        encoding="utf-8",
    )
    manifest_path.write_text(
        json.dumps(
            {
                "since": since,
                "through": through,
                "sample_size_requested": sample_size,
                "sample_size_written": len(sample_result["review_rows"]),
                "seed": seed,
                "sampling_strategy": "unsampled_thread_roots_only",
                "prior_sampled_message_count": sample_result["prior_sampled_message_count"],
                "thread_root_count": sample_result["thread_root_count"],
                "eligible_thread_root_count": sample_result["eligible_thread_root_count"],
                "run_timestamp": run_timestamp,
                "run_directory": str(run_dir.relative_to(REPO_ROOT)),
                "summary_path": str(summary_path.relative_to(REPO_ROOT)),
                "sample_path": str(sample_path.relative_to(REPO_ROOT)),
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    print(f"Summary written to: {summary_path}")
    print(f"Review sample written to: {sample_path}")
    print(f"Manifest written to: {manifest_path}")


def main():
    args = parse_args()
    records = load_records(args.since, args.through)
    summary = build_summary(records)
    sample_result = build_review_sample(
        records,
        args.sample_size,
        args.seed,
        args.since,
        args.through,
    )
    write_outputs(
        summary=summary,
        sample_result=sample_result,
        since=args.since,
        through=args.through,
        sample_size=args.sample_size,
        seed=args.seed,
    )


if __name__ == "__main__":
    main()
