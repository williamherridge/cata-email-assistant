"""Deterministic message classification helpers."""

from __future__ import annotations

from dataclasses import dataclass

from src.shared.models import Category, Message

MAKEUP_LINEUP_CATEGORY = "Make-up match line up"
REPLY_PREFIXES = ("re:", "fw:", "fwd:")
MAKEUP_LINEUP_SUBJECT_PREFIX = "make-up match line up from"
MAKEUP_LINEUP_REQUIRED_BODY_MARKERS = (
    "original match number",
    "captain's name",
    "opposing captain",
)


@dataclass
class ClassificationResult:
    category_name: str
    reply_needed: bool | None
    informational_only: bool
    priority: str
    reason_summary: str
    rule_code: str


def classify_message_deterministically(message: Message, body_text: str) -> ClassificationResult | None:
    result = classify_makeup_match_lineup(message, body_text)
    if result is not None:
        return result
    return None


def classify_makeup_match_lineup(message: Message, body_text: str) -> ClassificationResult | None:
    from_address = (message.from_address or "").strip().casefold()
    subject = (message.subject or "").strip()
    subject_lower = subject.casefold()

    if from_address != "no-reply@austintennis.org":
        return None
    if subject_lower.startswith(REPLY_PREFIXES):
        return None
    if not subject_lower.startswith(MAKEUP_LINEUP_SUBJECT_PREFIX):
        return None

    normalized_body = body_text.casefold()
    if not all(marker in normalized_body for marker in MAKEUP_LINEUP_REQUIRED_BODY_MARKERS):
        return None

    return ClassificationResult(
        category_name=MAKEUP_LINEUP_CATEGORY,
        reply_needed=False,
        informational_only=True,
        priority="low",
        reason_summary=(
            "Matched the structured make-up match line-up form based on sender, subject prefix, "
            "and required body markers."
        ),
        rule_code="makeup_lineup_form_v1",
    )


def category_default_result(category: Category) -> ClassificationResult:
    return ClassificationResult(
        category_name=category.name,
        reply_needed=category.default_reply_needed,
        informational_only=bool(category.default_informational_only),
        priority=category.priority_hint or "normal",
        reason_summary="Applied category-level defaults.",
        rule_code="category_defaults",
    )
