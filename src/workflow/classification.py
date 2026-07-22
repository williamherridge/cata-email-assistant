"""Deterministic message classification helpers."""

from __future__ import annotations

from dataclasses import dataclass

from src.shared.models import Category, Message

MAKEUP_LINEUP_CATEGORY = "Make-up match line up"
TEAM_REGISTRATION_CATEGORY = "Team registration submission"
FACILITY_REQUEST_CATEGORY = "Facility Request"
INELIGIBLE_LEAGUE_PLAYER_FORM_CATEGORY = "Ineligible League Player Form"
UTW_SUBCATEGORY = "UT-W"
REPLY_PREFIXES = ("re:", "fw:", "fwd:")
MAKEUP_LINEUP_SUBJECT_PREFIX = "make-up match line up from"
UTW_FACILITY_REQUEST_SUBJECT_PREFIX = "ut-w league facility request from"
INELIGIBLE_LEAGUE_PLAYER_FORM_SUBJECT_PREFIX = "❗️ ineligible league player form"
MAKEUP_LINEUP_SENDERS = {
    "web@site.tennisaustin.org",
}
FORMRESPONSE_SENDERS = {
    "noreply@formresponse.com",
}
TEAM_REGISTRATION_SENDERS = {
    "no-reply@austintennis.org",
    "leaguecommittee@austintennis.org",
}
TEAM_REGISTRATION_SUBJECT_MARKERS = (
    "team registration from",
    "new spring team registration from",
    "new fall team registration from",
    "new winter team registration from",
    "new summer team registration from",
)
MAKEUP_LINEUP_REQUIRED_BODY_MARKERS = (
    "original match number",
    "captain's name",
    "opposing captain",
)
TEAM_REGISTRATION_REQUIRED_BODY_MARKERS = (
    "captain name",
    "captain usta number",
    "registration type",
    "team name",
)


@dataclass
class ClassificationResult:
    category_name: str
    subcategory_name: str | None
    reply_needed: bool | None
    informational_only: bool
    priority: str
    auto_ignore: bool
    reason_summary: str
    rule_code: str


def classify_message_deterministically(message: Message, body_text: str) -> ClassificationResult | None:
    result = classify_makeup_match_lineup(message, body_text)
    if result is not None:
        return result
    result = classify_team_registration_submission(message, body_text)
    if result is not None:
        return result
    result = classify_utw_facility_request(message, body_text)
    if result is not None:
        return result
    result = classify_ineligible_league_player_form(message, body_text)
    if result is not None:
        return result
    return None


def classify_makeup_match_lineup(message: Message, body_text: str) -> ClassificationResult | None:
    from_address = (message.from_address or "").strip().casefold()
    subject = (message.subject or "").strip()
    subject_lower = subject.casefold()

    if from_address not in MAKEUP_LINEUP_SENDERS:
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
        subcategory_name=None,
        reply_needed=False,
        informational_only=True,
        priority="low",
        auto_ignore=False,
        reason_summary=(
            "Matched the structured make-up match line-up form based on sender, subject prefix, "
            "and required body markers."
        ),
        rule_code="makeup_lineup_form_v1",
    )


def classify_team_registration_submission(message: Message, body_text: str) -> ClassificationResult | None:
    from_address = (message.from_address or "").strip().casefold()
    subject = (message.subject or "").strip()
    subject_lower = subject.casefold()

    if from_address not in TEAM_REGISTRATION_SENDERS:
        return None
    if subject_lower.startswith(REPLY_PREFIXES):
        return None
    if not any(marker in subject_lower for marker in TEAM_REGISTRATION_SUBJECT_MARKERS):
        return None

    normalized_body = body_text.casefold()
    if not all(marker in normalized_body for marker in TEAM_REGISTRATION_REQUIRED_BODY_MARKERS):
        return None
    if "league ntrp level of play" not in normalized_body and (
        "league" not in normalized_body or "ntrp level of play" not in normalized_body
    ):
        return None

    return ClassificationResult(
        category_name=TEAM_REGISTRATION_CATEGORY,
        subcategory_name=None,
        reply_needed=False,
        informational_only=False,
        priority="normal",
        auto_ignore=False,
        reason_summary=(
            "Matched the structured team registration form based on sender, subject marker, "
            "and required registration fields in the message body."
        ),
        rule_code="team_registration_form_v1",
    )


def classify_utw_facility_request(message: Message, body_text: str) -> ClassificationResult | None:
    del body_text
    from_address = (message.from_address or "").strip().casefold()
    subject = (message.subject or "").strip()
    subject_lower = subject.casefold()

    if from_address not in MAKEUP_LINEUP_SENDERS:
        return None
    if subject_lower.startswith(REPLY_PREFIXES):
        return None
    if not subject_lower.startswith(UTW_FACILITY_REQUEST_SUBJECT_PREFIX):
        return None

    return ClassificationResult(
        category_name=FACILITY_REQUEST_CATEGORY,
        subcategory_name=UTW_SUBCATEGORY,
        reply_needed=False,
        informational_only=True,
        priority="low",
        auto_ignore=True,
        reason_summary=(
            "Matched the UT-W facility request form based on sender and subject prefix, "
            "so the message can be categorized and auto-ignored during ingest."
        ),
        rule_code="utw_facility_request_form_v1",
    )


def classify_ineligible_league_player_form(message: Message, body_text: str) -> ClassificationResult | None:
    del body_text
    from_address = (message.from_address or "").strip().casefold()
    subject = (message.subject or "").strip()
    subject_lower = subject.casefold()

    if from_address not in FORMRESPONSE_SENDERS:
        return None
    if subject_lower.startswith(REPLY_PREFIXES):
        return None
    if not subject_lower.startswith(INELIGIBLE_LEAGUE_PLAYER_FORM_SUBJECT_PREFIX):
        return None

    return ClassificationResult(
        category_name=INELIGIBLE_LEAGUE_PLAYER_FORM_CATEGORY,
        subcategory_name=None,
        reply_needed=False,
        informational_only=True,
        priority="low",
        auto_ignore=True,
        reason_summary=(
            "Matched the ineligible league player form based on sender and subject prefix, "
            "so the message can be categorized and auto-ignored during ingest."
        ),
        rule_code="ineligible_league_player_form_v1",
    )


def category_default_result(category: Category) -> ClassificationResult:
    return ClassificationResult(
        category_name=category.name,
        subcategory_name=None,
        reply_needed=category.default_reply_needed,
        informational_only=bool(category.default_informational_only),
        priority=category.priority_hint or "normal",
        auto_ignore=False,
        reason_summary="Applied category-level defaults.",
        rule_code="category_defaults",
    )
