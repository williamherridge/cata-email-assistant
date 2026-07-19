"""Normalization helpers for historical email bodies."""

import re

QUOTED_REPLY_PATTERNS = [
    re.compile(r"^\s*On .+wrote:\s*$", re.IGNORECASE),
    re.compile(r"^\s*From:\s+.+$", re.IGNORECASE),
    re.compile(r"^\s*Sent:\s+.+$", re.IGNORECASE),
    re.compile(r"^\s*To:\s+.+$", re.IGNORECASE),
    re.compile(r"^\s*Subject:\s+.+$", re.IGNORECASE),
]

SIGNATURE_PATTERNS = [
    re.compile(r"^\s*--\s*$"),
    re.compile(r"^\s*thanks[,!\s]*$", re.IGNORECASE),
    re.compile(r"^\s*thank you[,!\s]*$", re.IGNORECASE),
    re.compile(r"^\s*best[,!\s]*$", re.IGNORECASE),
    re.compile(r"^\s*regards[,!\s]*$", re.IGNORECASE),
]


def normalize_whitespace(text):
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in text.split("\n")]
    compact = "\n".join(lines)
    compact = re.sub(r"\n{3,}", "\n\n", compact)
    return compact.strip()


def split_signature(lines):
    for idx, line in enumerate(lines):
        if any(pattern.match(line) for pattern in SIGNATURE_PATTERNS):
            return lines[:idx], lines[idx:]
    return lines, []


def split_quoted_reply(lines):
    for idx, line in enumerate(lines):
        if line.lstrip().startswith(">"):
            return lines[:idx], lines[idx:]
        if any(pattern.match(line) for pattern in QUOTED_REPLY_PATTERNS):
            return lines[:idx], lines[idx:]
    return lines, []


def clean_email_body(body):
    normalized = normalize_whitespace(body or "")
    if not normalized:
        return {
            "clean_body": "",
            "has_quoted_text": False,
            "has_signature": False,
        }

    lines = normalized.split("\n")
    without_quote, quoted_lines = split_quoted_reply(lines)
    without_signature, signature_lines = split_signature(without_quote)

    clean_body = "\n".join(without_signature).strip()
    clean_body = re.sub(r"\n{3,}", "\n\n", clean_body)

    return {
        "clean_body": clean_body,
        "has_quoted_text": bool(quoted_lines),
        "has_signature": bool(signature_lines),
    }

