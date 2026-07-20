"""Poll and ingest workflow for the lean pilot portal."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import parse_qs

from sqlalchemy import desc, select
from sqlalchemy.orm import Session, selectinload

from src.gmail_ingest.client import GmailClient
from src.gmail_ingest.parsing import (
    collect_attachment_metadata,
    extract_body_text,
    headers_to_dict,
    parse_address_list,
    parse_datetime_header,
    parse_email_address,
    parse_internal_date,
)
from src.shared.config import Settings
from src.workflow.classification import classify_message_deterministically
from src.workflow.taxonomy import sync_taxonomy_catalog
from src.shared.models import (
    AuditEvent,
    Category,
    Mailbox,
    Message,
    MessageArtifact,
    MessageAttachment,
    MessageHeader,
    MessageParticipant,
    MessageThread,
    PollRun,
    Subcategory,
    WorkItem,
)


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


@dataclass
class PollOutcome:
    poll_run_id: int
    messages_discovered: int
    messages_persisted: int


def ensure_runtime_directories(settings: Settings) -> None:
    Path(settings.resolved_artifact_root).mkdir(parents=True, exist_ok=True)
    if settings.resolved_database_url.startswith("sqlite:///"):
        sqlite_path = Path(settings.resolved_database_url.removeprefix("sqlite:///"))
        sqlite_path.parent.mkdir(parents=True, exist_ok=True)


def ensure_default_mailbox(session: Session, settings: Settings) -> Mailbox | None:
    mailbox_address = settings.default_gmail_address
    display_name = settings.default_gmail_display_name

    if not mailbox_address:
        try:
            profile = GmailClient(settings).get_profile()
        except Exception:
            return None
        mailbox_address = profile.get("emailAddress")
        display_name = display_name or mailbox_address

    if not mailbox_address:
        return None

    mailbox = session.scalar(
        select(Mailbox).where(Mailbox.gmail_address == mailbox_address)
    )
    if mailbox:
        return mailbox

    mailbox = Mailbox(
        gmail_address=mailbox_address,
        display_name=display_name,
        is_active=True,
    )
    session.add(mailbox)
    session.commit()
    session.refresh(mailbox)
    return mailbox


def list_mailboxes(session: Session) -> list[Mailbox]:
    return list(session.scalars(select(Mailbox).order_by(Mailbox.gmail_address)))


def list_queue_messages(session: Session) -> list[Message]:
    statement = (
        select(Message)
        .where(Message.status == "new")
        .options(
            selectinload(Message.mailbox),
            selectinload(Message.thread),
            selectinload(Message.participants),
            selectinload(Message.attachments),
        )
        .order_by(desc(Message.received_at), desc(Message.id))
    )
    messages = list(session.scalars(statement))
    return [message for message in messages if not is_sent_message(message)]


def get_message_detail(session: Session, message_id: int) -> Message | None:
    statement = (
        select(Message)
        .where(Message.id == message_id)
        .options(
            selectinload(Message.mailbox),
            selectinload(Message.thread),
            selectinload(Message.participants),
            selectinload(Message.attachments),
            selectinload(Message.headers),
            selectinload(Message.artifacts),
            selectinload(Message.audit_events),
            selectinload(Message.assigned_category),
            selectinload(Message.assigned_subcategory),
            selectinload(Message.topics),
        )
    )
    return session.scalar(statement)


def mark_message_opened(session: Session, message: Message) -> None:
    message.opened_in_portal_at = utcnow()
    session.commit()


def update_message_review(
    session: Session,
    message_id: int,
    *,
    priority: str,
    informational_only: bool,
    reply_needed: bool | None,
    assigned_category_id: int | None,
    assigned_subcategory_id: int | None,
) -> Message:
    message = session.get(Message, message_id)
    if message is None:
        raise ValueError(f"Message {message_id} was not found.")

    changes: dict[str, dict[str, object | None]] = {}
    normalized_priority = normalize_priority(priority)
    category = session.get(Category, assigned_category_id) if assigned_category_id else None
    if assigned_category_id and (category is None or not category.is_active):
        raise ValueError("The selected category is not active.")

    subcategory = session.get(Subcategory, assigned_subcategory_id) if assigned_subcategory_id else None
    if assigned_subcategory_id and (
        subcategory is None or not subcategory.is_active or subcategory.category_id != assigned_category_id
    ):
        raise ValueError("The selected subcategory does not belong to the selected category.")

    updates = {
        "priority": normalized_priority,
        "informational_only": informational_only,
        "reply_needed": reply_needed,
        "assigned_category_id": assigned_category_id,
        "assigned_subcategory_id": assigned_subcategory_id,
    }
    for field_name, new_value in updates.items():
        old_value = getattr(message, field_name)
        if old_value != new_value:
            changes[field_name] = {"old": old_value, "new": new_value}
            setattr(message, field_name, new_value)

    if changes:
        session.add(
            AuditEvent(
                mailbox_id=message.mailbox_id,
                message_id=message.id,
                event_type="message_review_updated",
                actor_type="admin_portal",
                summary="Administrator updated message review fields.",
                detail_json=json.dumps(changes, sort_keys=True),
            )
        )

    session.commit()
    return get_message_detail(session, message_id) or message


def transition_message_status(session: Session, message_id: int, status: str) -> Message:
    if status not in {"new", "ignored"}:
        raise ValueError(f"Unsupported message status transition target: {status}")

    message = session.get(Message, message_id)
    if message is None:
        raise ValueError(f"Message {message_id} was not found.")

    old_status = message.status
    if old_status != status:
        message.status = status
        if status == "ignored":
            message.ignored_at = utcnow()
            summary = "Administrator marked the message ignored."
            event_type = "message_ignored"
        else:
            message.ignored_at = None
            summary = "Administrator returned the message to the active queue."
            event_type = "message_reopened"

        session.add(
            AuditEvent(
                mailbox_id=message.mailbox_id,
                message_id=message.id,
                event_type=event_type,
                actor_type="admin_portal",
                summary=summary,
                detail_json=json.dumps({"old_status": old_status, "new_status": status}, sort_keys=True),
            )
        )

    session.commit()
    return get_message_detail(session, message_id) or message


def get_recent_poll_runs(session: Session, limit: int = 10) -> list[PollRun]:
    statement = select(PollRun).options(selectinload(PollRun.mailbox)).order_by(desc(PollRun.started_at)).limit(limit)
    return list(session.scalars(statement))


def poll_mailbox(session: Session, settings: Settings, mailbox_id: int, trigger_source: str = "portal") -> PollOutcome:
    ensure_runtime_directories(settings)
    if hasattr(settings, "taxonomy_catalog_path"):
        sync_taxonomy_catalog(session, settings.taxonomy_catalog_path)

    mailbox = session.get(Mailbox, mailbox_id)
    if mailbox is None:
        raise ValueError(f"Mailbox {mailbox_id} was not found.")

    poll_run = PollRun(
        mailbox_id=mailbox.id,
        trigger_source=trigger_source,
        status="running",
        history_id_start=mailbox.last_successful_history_id,
        started_at=utcnow(),
    )
    session.add(poll_run)
    session.flush()

    client = GmailClient(settings)

    try:
        profile = client.get_profile()
        mailbox.gmail_profile_id = profile.get("emailAddress")

        discovery = client.discover_message_ids(mailbox.last_successful_history_id)
        poll_run.history_id_end = discovery.history_id
        poll_run.messages_discovered = len(discovery.message_ids)

        ingest_items: list[WorkItem] = []
        for gmail_message_id in discovery.message_ids:
            work_item = WorkItem(
                work_type="ingest_message",
                status="pending",
                mailbox_id=mailbox.id,
                poll_run_id=poll_run.id,
                payload_json=json.dumps({"gmail_message_id": gmail_message_id}),
                scheduled_for=utcnow(),
            )
            session.add(work_item)
            ingest_items.append(work_item)

        poll_run.messages_enqueued = len(ingest_items)
        session.flush()

        persisted_count = 0
        for work_item in ingest_items:
            analyze_item = ingest_message_work_item(session, settings, client, mailbox, poll_run, work_item)
            analyze_message_work_item(session, analyze_item)
            persisted_count += 1

        mailbox.last_successful_history_id = discovery.history_id or mailbox.last_successful_history_id
        mailbox.last_polled_at = utcnow()
        poll_run.status = "completed"
        poll_run.completed_at = utcnow()

        session.add(
            AuditEvent(
                mailbox_id=mailbox.id,
                event_type="poll_completed",
                summary=f"Mailbox poll completed with {poll_run.messages_discovered} discovered message(s).",
                detail_json=json.dumps(
                    {
                        "poll_run_id": poll_run.id,
                        "messages_discovered": poll_run.messages_discovered,
                        "messages_enqueued": poll_run.messages_enqueued,
                    }
                ),
            )
        )

        session.commit()
        return PollOutcome(
            poll_run_id=poll_run.id,
            messages_discovered=poll_run.messages_discovered,
            messages_persisted=persisted_count,
        )
    except Exception as exc:
        poll_run.status = "failed"
        poll_run.completed_at = utcnow()
        poll_run.error_summary = str(exc)
        session.add(
            AuditEvent(
                mailbox_id=mailbox.id,
                event_type="poll_failed",
                summary="Mailbox poll failed.",
                detail_json=json.dumps({"error": str(exc), "poll_run_id": poll_run.id}),
            )
        )
        session.commit()
        raise


def ingest_message_work_item(
    session: Session,
    settings: Settings,
    client: GmailClient,
    mailbox: Mailbox,
    poll_run: PollRun,
    work_item: WorkItem,
) -> WorkItem:
    payload = json.loads(work_item.payload_json or "{}")
    gmail_message_id = payload["gmail_message_id"]

    work_item.status = "running"
    work_item.attempt_count += 1
    work_item.started_at = utcnow()
    session.flush()

    message_payload = client.get_message(gmail_message_id)
    message = upsert_message_from_gmail(session, settings, mailbox, message_payload)

    work_item.message_id = message.id
    work_item.status = "completed"
    work_item.completed_at = utcnow()
    work_item.error_summary = None

    analyze_item = WorkItem(
        work_type="analyze_message",
        status="pending",
        mailbox_id=mailbox.id,
        message_id=message.id,
        poll_run_id=poll_run.id,
        payload_json=json.dumps({"message_id": message.id}),
        scheduled_for=utcnow(),
    )
    session.add(analyze_item)
    session.add(
        AuditEvent(
            mailbox_id=mailbox.id,
            message_id=message.id,
            event_type="message_ingested",
            summary=f"Ingested Gmail message {message.gmail_message_id}.",
            detail_json=json.dumps({"poll_run_id": poll_run.id}),
        )
    )
    session.flush()
    return analyze_item


def analyze_message_work_item(session: Session, work_item: WorkItem) -> None:
    if work_item.work_type != "analyze_message":
        raise ValueError(f"Unsupported analysis work item type: {work_item.work_type}")

    message = session.get(Message, work_item.message_id)
    if message is None:
        raise ValueError(f"Message {work_item.message_id} was not found for analysis.")

    work_item.status = "running"
    work_item.attempt_count += 1
    work_item.started_at = utcnow()
    session.flush()

    result = None
    if message.assigned_category_id is None:
        result = apply_deterministic_classification(session, message)

    work_item.status = "completed"
    work_item.completed_at = utcnow()
    work_item.error_summary = None

    if result is None:
        session.add(
            AuditEvent(
                mailbox_id=message.mailbox_id,
                message_id=message.id,
                event_type="message_analysis_completed",
                summary="Deterministic analysis completed without an automatic category assignment.",
            )
        )

    session.flush()


def apply_deterministic_classification(session: Session, message: Message) -> Category | None:
    body_text = read_body_artifact(message)
    result = classify_message_deterministically(message, body_text)
    if result is None:
        return None

    category = session.scalar(
        select(Category).where(Category.name == result.category_name, Category.is_active.is_(True))
    )
    if category is None:
        return None

    message.assigned_category_id = category.id
    if message.reply_needed is None:
        message.reply_needed = result.reply_needed
    message.informational_only = result.informational_only
    message.priority = normalize_priority(result.priority)

    session.add(
        AuditEvent(
            mailbox_id=message.mailbox_id,
            message_id=message.id,
            event_type="message_auto_classified",
            summary=f"Deterministic rules assigned category '{category.name}'.",
            detail_json=json.dumps(
                {
                    "category_name": category.name,
                    "rule_code": result.rule_code,
                    "reason_summary": result.reason_summary,
                    "reply_needed": result.reply_needed,
                    "informational_only": result.informational_only,
                    "priority": normalize_priority(result.priority),
                },
                sort_keys=True,
            ),
        )
    )
    return category


def upsert_message_from_gmail(session: Session, settings: Settings, mailbox: Mailbox, raw_message: dict) -> Message:
    payload = raw_message.get("payload", {})
    headers = headers_to_dict(payload.get("headers", []))
    internal_date = parse_internal_date(raw_message.get("internalDate"))
    received_at = parse_datetime_header(headers.get("date")) or internal_date
    subject = headers.get("subject")

    thread = session.scalar(
        select(MessageThread).where(
            MessageThread.mailbox_id == mailbox.id,
            MessageThread.gmail_thread_id == raw_message.get("threadId"),
        )
    )
    if thread is None:
        thread = MessageThread(
            mailbox_id=mailbox.id,
            gmail_thread_id=raw_message["threadId"],
            subject_canonical=subject,
        )
        session.add(thread)
        session.flush()

    message = session.scalar(
        select(Message).where(
            Message.mailbox_id == mailbox.id,
            Message.gmail_message_id == raw_message["id"],
        )
    )
    if message is None:
        message = Message(
            mailbox_id=mailbox.id,
            gmail_message_id=raw_message["id"],
            status="new",
            draft_state="not_started",
            priority="normal",
            informational_only=False,
        )
        session.add(message)
        session.flush()

    from_participant = parse_email_address(headers.get("from"))
    message.thread_id = thread.id
    message.gmail_history_id = raw_message.get("historyId")
    message.rfc_message_id = headers.get("message-id")
    message.gmail_internal_date = internal_date
    message.from_display = from_participant.display_name if from_participant else None
    message.from_address = from_participant.email_address if from_participant else None
    message.subject = subject
    message.snippet = raw_message.get("snippet")
    message.received_at = received_at
    message.has_attachments = bool(collect_attachment_metadata(payload))
    message.updated_at = utcnow()

    sync_message_children(message, payload)
    sync_message_artifacts(message, settings, raw_message, extract_body_text(payload))

    thread.subject_canonical = thread.subject_canonical or subject
    if received_at and (
        thread.latest_message_received_at is None or received_at >= thread.latest_message_received_at
    ):
        thread.latest_message_received_at = received_at
        thread.latest_message_id = message.id
    thread.updated_at = utcnow()

    session.flush()
    return message


def sync_message_children(message: Message, payload: dict) -> None:
    headers = headers_to_dict(payload.get("headers", []))

    message.participants.clear()
    for participant_type in ("to", "cc", "bcc"):
        for index, participant in enumerate(parse_address_list(headers.get(participant_type))):
            message.participants.append(
                MessageParticipant(
                    participant_type=participant_type,
                    display_name=participant.display_name,
                    email_address=participant.email_address,
                    position_index=index,
                )
            )
    from_participant = parse_email_address(headers.get("from"))
    if from_participant:
        message.participants.append(
            MessageParticipant(
                participant_type="from",
                display_name=from_participant.display_name,
                email_address=from_participant.email_address,
                position_index=0,
            )
        )

    message.headers.clear()
    for name, value in headers.items():
        message.headers.append(MessageHeader(header_name=name, header_value=value))

    message.attachments.clear()
    for attachment in collect_attachment_metadata(payload):
        message.attachments.append(MessageAttachment(**attachment))


def sync_message_artifacts(message: Message, settings: Settings, raw_message: dict, body_text: str) -> None:
    mailbox_folder = settings.resolved_artifact_root / "raw-messages" / f"mailbox-{message.mailbox_id}"
    mailbox_folder.mkdir(parents=True, exist_ok=True)

    raw_path = mailbox_folder / f"{message.gmail_message_id}.json"
    raw_serialized = json.dumps(raw_message, indent=2, sort_keys=True)
    raw_path.write_text(raw_serialized, encoding="utf-8")
    raw_hash = hashlib.sha256(raw_serialized.encode("utf-8")).hexdigest()

    body_folder = settings.resolved_artifact_root / "processed-messages" / f"mailbox-{message.mailbox_id}"
    body_folder.mkdir(parents=True, exist_ok=True)
    body_path = body_folder / f"{message.gmail_message_id}.txt"
    body_path.write_text(body_text, encoding="utf-8")
    body_hash = hashlib.sha256(body_text.encode("utf-8")).hexdigest()

    upsert_message_artifact(message, "raw_gmail_message", raw_path, raw_hash)
    upsert_message_artifact(message, "normalized_body_text", body_path, body_hash)


def upsert_message_artifact(message: Message, artifact_type: str, path: Path, content_sha256: str) -> None:
    existing = next((artifact for artifact in message.artifacts if artifact.artifact_type == artifact_type), None)
    if existing is None:
        message.artifacts.append(
            MessageArtifact(
                artifact_type=artifact_type,
                storage_uri=str(path),
                content_sha256=content_sha256,
            )
        )
        return

    existing.storage_uri = str(path)
    existing.content_sha256 = content_sha256


def read_body_artifact(message: Message) -> str:
    artifact = next((item for item in message.artifacts if item.artifact_type == "normalized_body_text"), None)
    if artifact is None:
        return ""
    path = Path(artifact.storage_uri)
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def parse_review_form(body: bytes) -> dict[str, object]:
    parsed = parse_form_body(body)

    priority = normalize_priority((parsed.get("priority", ["normal"])[0] or "normal").strip().lower())

    reply_raw = (parsed.get("reply_needed", ["unknown"])[0] or "unknown").strip().lower()
    if reply_raw == "yes":
        reply_needed: bool | None = True
    elif reply_raw == "no":
        reply_needed = False
    else:
        reply_needed = None

    return {
        "priority": priority,
        "informational_only": "informational_only" in parsed,
        "reply_needed": reply_needed,
        "assigned_category_id": normalize_optional_int(parsed.get("assigned_category_id", [""])[0]),
        "assigned_subcategory_id": normalize_optional_int(parsed.get("assigned_subcategory_id", [""])[0]),
    }


def parse_return_to(body: bytes, default: str) -> str:
    parsed = parse_form_body(body)
    return normalize_return_to(parsed.get("return_to", [default])[0], default)


def parse_form_body(body: bytes) -> dict[str, list[str]]:
    return parse_qs(body.decode("utf-8"), keep_blank_values=True)


def normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def normalize_optional_int(value: str | None) -> int | None:
    normalized = normalize_optional_text(value)
    if normalized is None:
        return None
    return int(normalized) if normalized.isdigit() else None


def normalize_priority(value: str | None) -> str:
    normalized = (value or "normal").strip().lower()
    legacy_priority_map = {
        "urgent": "critical",
        "high": "critical",
    }
    normalized = legacy_priority_map.get(normalized, normalized)
    if normalized not in {"critical", "normal", "low"}:
        return "normal"
    return normalized


def normalize_return_to(value: str | None, default: str) -> str:
    candidate = (value or "").strip()
    if not candidate.startswith("/"):
        return default
    return candidate


def is_sent_message(message: Message) -> bool:
    mailbox_address = (message.mailbox.gmail_address if message.mailbox else None) or ""
    from_address = message.from_address or ""
    return bool(mailbox_address and from_address and mailbox_address.casefold() == from_address.casefold())


def get_reply_to_addresses(message: Message) -> str:
    if message.from_address:
        return message.from_address
    return ""


def get_reply_cc_addresses(message: Message) -> str:
    mailbox_address = (message.mailbox.gmail_address if message.mailbox else "").casefold()
    primary_from = (message.from_address or "").casefold()
    cc_addresses: list[str] = []
    seen = {mailbox_address, primary_from}
    for participant in message.participants:
        if participant.participant_type not in {"cc", "to"}:
            continue
        normalized = participant.email_address.casefold()
        if normalized in seen:
            continue
        seen.add(normalized)
        cc_addresses.append(participant.email_address)
    return ", ".join(cc_addresses)


def build_reply_subject(message: Message) -> str:
    subject = (message.subject or "").strip()
    if not subject:
        return "Re:"
    if subject.lower().startswith("re:"):
        return subject
    return f"Re: {subject}"


def build_default_draft_html(message: Message) -> str:
    recipient_name = message.from_display or message.from_address or "there"
    return (
        f"<p>Hello {recipient_name},</p>"
        "<p><br></p>"
        "<p>Thanks,</p>"
        "<p><strong>CATA Administrator</strong><br>CATA</p>"
    )
