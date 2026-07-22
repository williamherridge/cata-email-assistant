"""Poll and ingest workflow for the lean pilot portal."""

from __future__ import annotations

import base64
import hashlib
import html
import json
import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import getaddresses
from pathlib import Path
from urllib.parse import parse_qs

from googleapiclient.errors import HttpError
from sqlalchemy import desc, or_, select
from sqlalchemy.orm import Session, selectinload

from src.gmail_ingest.client import GmailClient
from src.gmail_ingest.parsing import (
    collect_attachment_metadata,
    extract_body_html,
    extract_body_text,
    headers_to_dict,
    parse_address_list,
    parse_datetime_header,
    parse_email_address,
    parse_internal_date,
    sanitize_email_html,
)
from src.shared.config import Settings
from src.shared.config import get_settings
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

TEST_SEND_AUDIT_RULE = "forced_test_recipient_override"
SENT_REPLY_HTML_ARTIFACT = "sent_reply_html"
SENT_REPLY_METADATA_ARTIFACT = "sent_reply_metadata"
PORTAL_DRAFT_ARTIFACT = "portal_reply_draft"
DEFAULT_SIGNATURE_LOGO_PATH = Path("src/admin_portal/static/images/tennis-austin-full-logo")
logger = logging.getLogger(__name__)
_DEFAULT_SIGNATURE_LOGO_HTML: str | None = None


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


@dataclass
class PollOutcome:
    poll_run_id: int
    messages_discovered: int
    messages_persisted: int


@dataclass
class SentReplyRecord:
    html: str
    metadata: dict[str, object]
    created_at: datetime | None


def ensure_runtime_directories(settings: Settings) -> None:
    Path(settings.resolved_artifact_root).mkdir(parents=True, exist_ok=True)
    if settings.resolved_database_url.startswith("sqlite:///"):
        sqlite_path = Path(settings.resolved_database_url.removeprefix("sqlite:///"))
        sqlite_path.parent.mkdir(parents=True, exist_ok=True)


def ensure_default_mailbox(session: Session, settings: Settings) -> Mailbox | None:
    mailbox_address = settings.default_gmail_address
    display_name = settings.default_gmail_display_name

    if not mailbox_address:
        existing_mailbox = session.scalar(select(Mailbox).where(Mailbox.is_active.is_(True)).order_by(Mailbox.id))
        if existing_mailbox is not None:
            return existing_mailbox

    if not mailbox_address:
        try:
            profile = GmailClient(settings).get_profile()
        except Exception:
            logger.exception("Default mailbox discovery from Gmail profile failed.")
            session.rollback()
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
    try:
        session.commit()
        session.refresh(mailbox)
    except Exception:
        session.rollback()
        logger.exception("Default mailbox creation failed for %s.", mailbox_address)
        return None
    return mailbox


def list_mailboxes(session: Session) -> list[Mailbox]:
    return list(session.scalars(select(Mailbox).order_by(Mailbox.gmail_address)))


def list_queue_messages(
    session: Session,
    *,
    search_text: str | None = None,
    category_id: int | None = None,
    priority: str | None = None,
    reply_needed: str | None = None,
) -> list[Message]:
    statement = (
        select(Message)
        .where(Message.status == "new")
        .order_by(desc(Message.received_at), desc(Message.id))
    )
    normalized_search = (search_text or "").strip()
    if normalized_search:
        search_pattern = f"%{normalized_search}%"
        statement = statement.where(
            or_(
                Message.subject.ilike(search_pattern),
                Message.from_display.ilike(search_pattern),
                Message.from_address.ilike(search_pattern),
                Message.snippet.ilike(search_pattern),
            )
        )
    if category_id is not None:
        statement = statement.where(Message.assigned_category_id == category_id)
    if priority in {"critical", "normal", "low"}:
        statement = statement.where(Message.priority == priority)
    if reply_needed == "yes":
        statement = statement.where(Message.reply_needed.is_(True))
    elif reply_needed == "no":
        statement = statement.where(Message.reply_needed.is_(False))
    elif reply_needed == "unknown":
        statement = statement.where(Message.reply_needed.is_(None))

    messages = list(session.scalars(statement))
    return [message for message in messages if not is_sent_message(message)]


def list_history_messages(
    session: Session,
    *,
    tab: str,
    search_text: str | None = None,
    ignored_scope: str = "manual",
) -> list[Message]:
    normalized_tab = normalize_history_tab(tab)
    statement = (
        select(Message)
        .options(
            selectinload(Message.mailbox),
            selectinload(Message.thread),
            selectinload(Message.participants),
            selectinload(Message.attachments),
            selectinload(Message.assigned_category),
            selectinload(Message.artifacts),
            selectinload(Message.audit_events),
        )
    )

    normalized_search = (search_text or "").strip()
    if normalized_search:
        search_pattern = f"%{normalized_search}%"
        statement = statement.where(
            or_(
                Message.subject.ilike(search_pattern),
                Message.from_display.ilike(search_pattern),
                Message.from_address.ilike(search_pattern),
                Message.snippet.ilike(search_pattern),
            )
        )

    if normalized_tab == "ignored":
        statement = statement.where(Message.status == "ignored").order_by(desc(Message.ignored_at), desc(Message.id))
        messages = list(session.scalars(statement))
        if normalize_ignored_scope(ignored_scope) == "manual":
            return [message for message in messages if get_ignore_source(message) == "manual"]
        return messages

    statement = statement.where(Message.status == "responded").order_by(desc(Message.responded_at), desc(Message.id))
    return list(session.scalars(statement))


def get_message_detail(session: Session, message_id: int) -> Message | None:
    return get_message_detail_for_view(session, message_id, view="full")


def get_message_detail_for_view(session: Session, message_id: int, *, view: str = "full") -> Message | None:
    if view == "queue":
        options = [
            selectinload(Message.mailbox),
            selectinload(Message.thread),
            selectinload(Message.participants),
            selectinload(Message.attachments),
            selectinload(Message.artifacts),
            selectinload(Message.assigned_category),
            selectinload(Message.assigned_subcategory),
        ]
    elif view == "history":
        options = [
            selectinload(Message.mailbox),
            selectinload(Message.thread),
            selectinload(Message.participants),
            selectinload(Message.attachments),
            selectinload(Message.artifacts),
            selectinload(Message.audit_events),
            selectinload(Message.assigned_category),
            selectinload(Message.assigned_subcategory),
        ]
    else:
        options = [
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
        ]

    statement = (
        select(Message)
        .where(Message.id == message_id)
        .options(*options)
    )
    return session.scalar(statement)


def mark_message_opened(session: Session, message: Message) -> None:
    message.opened_in_portal_at = utcnow()
    try:
        session.commit()
    except Exception:
        session.rollback()
        logger.exception("Failed to persist opened timestamp for message %s.", message.id)


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
    if status not in {"new", "ignored", "responded"}:
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
        elif status == "responded":
            if message.responded_at is None:
                message.responded_at = utcnow()
                summary = "Administrator marked the message responded."
            else:
                summary = "Administrator returned the message to responded history without sending a new reply."
            event_type = "message_responded"
        else:
            message.ignored_at = None
            if old_status == "ignored":
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
            if analyze_item is None:
                continue
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
) -> WorkItem | None:
    work_item.status = "running"
    work_item.attempt_count += 1
    work_item.started_at = utcnow()
    session.flush()

    try:
        payload = json.loads(work_item.payload_json or "{}")
    except (TypeError, ValueError):
        fail_work_item(
            session,
            mailbox_id=mailbox.id,
            work_item=work_item,
            event_type="message_ingest_payload_invalid",
            summary="Skipped an ingest work item because its payload was invalid.",
            error_summary="Malformed ingest work item payload.",
            detail={"poll_run_id": poll_run.id},
        )
        return None

    gmail_message_id = normalize_optional_text(str(payload.get("gmail_message_id") or ""))
    if not gmail_message_id:
        fail_work_item(
            session,
            mailbox_id=mailbox.id,
            work_item=work_item,
            event_type="message_ingest_payload_invalid",
            summary="Skipped an ingest work item because it did not include a Gmail message id.",
            error_summary="Missing Gmail message id in ingest work item payload.",
            detail={"poll_run_id": poll_run.id},
        )
        return None

    try:
        message_payload = client.get_message(gmail_message_id)
    except HttpError as exc:
        if exc.resp is not None and exc.resp.status == 404:
            work_item.status = "cancelled"
            work_item.completed_at = utcnow()
            work_item.error_summary = "Gmail message no longer exists."
            session.add(
                AuditEvent(
                    mailbox_id=mailbox.id,
                    event_type="message_missing_from_gmail",
                    summary=f"Skipped Gmail message {gmail_message_id} because it no longer exists.",
                    detail_json=json.dumps(
                        {
                            "poll_run_id": poll_run.id,
                            "gmail_message_id": gmail_message_id,
                        },
                        sort_keys=True,
                    ),
                )
            )
            session.flush()
            return None
        raise

    try:
        message = upsert_message_from_gmail(session, settings, mailbox, message_payload)
        sync_direct_gmail_reply_to_related_messages(session, settings, mailbox, message)
    except (KeyError, TypeError, ValueError, OSError):
        logger.exception("Failed to ingest Gmail message %s.", gmail_message_id)
        fail_work_item(
            session,
            mailbox_id=mailbox.id,
            work_item=work_item,
            event_type="message_ingest_failed",
            summary=f"Failed to ingest Gmail message {gmail_message_id}.",
            error_summary="Unexpected message payload or artifact failure during ingest.",
            detail={"poll_run_id": poll_run.id, "gmail_message_id": gmail_message_id},
        )
        return None

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
        fail_work_item(
            session,
            mailbox_id=work_item.mailbox_id,
            work_item=work_item,
            event_type="message_analysis_failed",
            summary="Skipped an analysis work item because its type was not supported.",
            error_summary=f"Unsupported analysis work item type: {work_item.work_type}",
        )
        return

    message = session.get(Message, work_item.message_id)
    if message is None:
        fail_work_item(
            session,
            mailbox_id=work_item.mailbox_id,
            work_item=work_item,
            event_type="message_analysis_failed",
            summary="Skipped an analysis work item because its message was missing.",
            error_summary=f"Message {work_item.message_id} was not found for analysis.",
        )
        return

    work_item.status = "running"
    work_item.attempt_count += 1
    work_item.started_at = utcnow()
    session.flush()

    result = None
    try:
        if not is_sent_message(message) and message.assigned_category_id is None:
            result = apply_deterministic_classification(session, message)
    except (OSError, ValueError, TypeError):
        logger.exception("Deterministic analysis failed for message %s.", message.id)
        fail_work_item(
            session,
            mailbox_id=message.mailbox_id,
            message_id=message.id,
            work_item=work_item,
            event_type="message_analysis_failed",
            summary=f"Deterministic analysis failed for message {message.id}.",
            error_summary="Unexpected content or artifact failure during deterministic analysis.",
        )
        return

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

    subcategory = None
    if result.subcategory_name:
        subcategory = session.scalar(
            select(Subcategory).where(
                Subcategory.category_id == category.id,
                Subcategory.name == result.subcategory_name,
                Subcategory.is_active.is_(True),
            )
        )

    message.assigned_category_id = category.id
    message.assigned_subcategory_id = subcategory.id if subcategory is not None else None
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
                    "subcategory_name": subcategory.name if subcategory is not None else None,
                    "rule_code": result.rule_code,
                    "reason_summary": result.reason_summary,
                    "reply_needed": result.reply_needed,
                    "informational_only": result.informational_only,
                    "priority": normalize_priority(result.priority),
                    "auto_ignore": result.auto_ignore,
                },
                sort_keys=True,
            ),
        )
    )

    if result.auto_ignore and message.status != "ignored":
        message.status = "ignored"
        message.ignored_at = utcnow()
        session.add(
            AuditEvent(
                mailbox_id=message.mailbox_id,
                message_id=message.id,
                event_type="message_ignored",
                actor_type="workflow",
                summary="Message was automatically ignored by deterministic classification.",
                detail_json=json.dumps(
                    {
                        "category_name": category.name,
                        "subcategory_name": subcategory.name if subcategory is not None else None,
                        "rule_code": result.rule_code,
                        "source": "deterministic_classification",
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
    sync_message_artifacts(
        message,
        settings,
        raw_message,
        extract_body_text(payload),
        extract_body_html(payload),
    )

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


def sync_message_artifacts(
    message: Message,
    settings: Settings,
    raw_message: dict,
    body_text: str,
    body_html: str,
) -> None:
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
    body_html_sanitized = sanitize_email_html(body_html)
    body_html_path = body_folder / f"{message.gmail_message_id}.html"
    body_html_path.write_text(body_html_sanitized, encoding="utf-8")
    body_html_hash = hashlib.sha256(body_html_sanitized.encode("utf-8")).hexdigest()

    upsert_message_artifact(message, "raw_gmail_message", raw_path, raw_hash)
    upsert_message_artifact(message, "normalized_body_text", body_path, body_hash)
    upsert_message_artifact(message, "sanitized_body_html", body_html_path, body_html_hash)


def create_message_artifact(message: Message, artifact_type: str, path: Path, content_sha256: str | None) -> MessageArtifact:
    artifact = MessageArtifact(
        artifact_type=artifact_type,
        storage_uri=str(path),
        content_sha256=content_sha256,
    )
    message.artifacts.append(artifact)
    return artifact


def sync_direct_gmail_reply_to_related_messages(
    session: Session,
    settings: Settings,
    mailbox: Mailbox,
    sent_message: Message,
) -> None:
    mailbox_address = (mailbox.gmail_address or "").casefold()
    from_address = (sent_message.from_address or "").casefold()
    if not mailbox_address or from_address != mailbox_address:
        return
    if sent_message.thread_id is None:
        return

    statement = (
        select(Message)
        .where(
            Message.thread_id == sent_message.thread_id,
            Message.id != sent_message.id,
        )
        .options(
            selectinload(Message.mailbox),
            selectinload(Message.artifacts),
            selectinload(Message.audit_events),
        )
        .order_by(desc(Message.received_at), desc(Message.id))
    )
    related_messages = [
        message
        for message in session.scalars(statement)
        if not is_sent_message(message)
        and message.status in {"new", "responded"}
        and (
            sent_message.received_at is None
            or message.received_at is None
            or message.received_at <= sent_message.received_at
        )
    ]
    if not related_messages:
        return

    sent_reply_record = build_sent_reply_record_from_message(sent_message)
    if sent_reply_record is None:
        return

    for related_message in related_messages:
        if has_synced_external_reply(related_message, sent_message.gmail_message_id):
            continue

        old_status = related_message.status
        related_message.status = "responded"
        if sent_message.received_at and (
            related_message.responded_at is None or sent_message.received_at >= related_message.responded_at
        ):
            related_message.responded_at = sent_message.received_at

        html_artifact = persist_sent_reply_record(
            related_message,
            settings,
            sent_reply_record,
            source_message_id=sent_message.gmail_message_id,
        )
        session.flush()
        related_message.latest_sent_reply_id = html_artifact.id

        session.add(
            AuditEvent(
                mailbox_id=related_message.mailbox_id,
                message_id=related_message.id,
                event_type="message_reply_synced_from_gmail",
                actor_type="gmail_sync",
                summary="Detected a reply sent directly in Gmail and synced it into message history.",
                detail_json=json.dumps(
                    {
                        "old_status": old_status,
                        "new_status": "responded",
                        "source_gmail_message_id": sent_message.gmail_message_id,
                        "source_thread_id": sent_message.thread.gmail_thread_id if sent_message.thread else None,
                        "delivery_rule": "gmail_direct_reply_sync",
                    },
                    sort_keys=True,
                ),
            )
        )


def backfill_direct_gmail_reply_sync(
    session: Session,
    settings: Settings,
    *,
    mailbox_id: int | None = None,
) -> dict[str, int]:
    statement = (
        select(Message)
        .options(
            selectinload(Message.mailbox),
            selectinload(Message.thread),
            selectinload(Message.participants),
            selectinload(Message.artifacts),
            selectinload(Message.audit_events),
        )
        .order_by(Message.received_at, Message.id)
    )
    if mailbox_id is not None:
        statement = statement.where(Message.mailbox_id == mailbox_id)

    sent_messages = [message for message in session.scalars(statement) if is_sent_message(message)]
    touched_threads = 0
    synced_messages = 0

    for sent_message in sent_messages:
        if sent_message.mailbox is None:
            continue
        before_count = session.query(AuditEvent).filter(
            AuditEvent.event_type == "message_reply_synced_from_gmail",
            AuditEvent.detail_json.contains(sent_message.gmail_message_id),
        ).count()
        before_responded_count = session.query(Message).filter(
            Message.thread_id == sent_message.thread_id,
            Message.id != sent_message.id,
            Message.status == "responded",
        ).count()
        sync_direct_gmail_reply_to_related_messages(session, settings, sent_message.mailbox, sent_message)
        session.flush()
        after_count = session.query(AuditEvent).filter(
            AuditEvent.event_type == "message_reply_synced_from_gmail",
            AuditEvent.detail_json.contains(sent_message.gmail_message_id),
        ).count()
        after_responded_count = session.query(Message).filter(
            Message.thread_id == sent_message.thread_id,
            Message.id != sent_message.id,
            Message.status == "responded",
        ).count()
        if after_count > before_count:
            synced_messages += after_count - before_count
        if after_responded_count > before_responded_count:
            touched_threads += 1

    messages_with_sent_reply_history = session.query(Message).filter(Message.latest_sent_reply_id.is_not(None)).count()
    session.commit()
    return {
        "sent_messages_scanned": len(sent_messages),
        "threads_touched": touched_threads,
        "messages_synced": synced_messages,
        "messages_with_sent_reply_history": messages_with_sent_reply_history,
    }


def build_sent_reply_record_from_message(message: Message) -> SentReplyRecord | None:
    html_body = read_body_html_artifact(message)
    if not html_body.strip():
        body_text = read_body_artifact(message)
        if body_text.strip():
            html_body = f"<pre>{html.escape(body_text)}</pre>"
    if not html_body.strip():
        return None

    to_addresses = [
        participant.email_address
        for participant in sorted(message.participants, key=lambda item: (item.position_index, item.id))
        if participant.participant_type == "to"
    ]
    cc_addresses = [
        participant.email_address
        for participant in sorted(message.participants, key=lambda item: (item.position_index, item.id))
        if participant.participant_type == "cc"
    ]

    return SentReplyRecord(
        html=html_body,
        metadata={
            "effective_to": to_addresses,
            "effective_cc": cc_addresses,
            "subject": message.subject,
            "sent_at": message.received_at.isoformat() if message.received_at else None,
            "delivery_rule": "gmail_direct_reply_sync",
        },
        created_at=message.received_at,
    )


def has_synced_external_reply(message: Message, source_message_id: str) -> bool:
    for artifact in message.artifacts:
        if artifact.artifact_type != SENT_REPLY_METADATA_ARTIFACT:
            continue
        path = Path(artifact.storage_uri)
        if not path.exists():
            continue
        try:
            metadata = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if metadata.get("source_gmail_message_id") == source_message_id:
            return True
    return False


def persist_sent_reply_record(
    message: Message,
    settings: Settings,
    sent_reply_record: SentReplyRecord,
    *,
    source_message_id: str,
) -> MessageArtifact:
    sent_reply_folder = settings.resolved_artifact_root / "sent-replies" / f"mailbox-{message.mailbox_id}"
    sent_reply_folder.mkdir(parents=True, exist_ok=True)
    sent_reply_stem = f"{message.gmail_message_id}-external-{source_message_id}"

    sent_reply_html = sanitize_email_html(sent_reply_record.html)
    sent_reply_html_path = sent_reply_folder / f"{sent_reply_stem}.html"
    sent_reply_html_path.write_text(sent_reply_html, encoding="utf-8")
    sent_reply_html_hash = hashlib.sha256(sent_reply_html.encode("utf-8")).hexdigest()

    sent_reply_metadata = dict(sent_reply_record.metadata)
    sent_reply_metadata["source_gmail_message_id"] = source_message_id
    sent_reply_metadata_path = sent_reply_folder / f"{sent_reply_stem}.json"
    sent_reply_metadata_serialized = json.dumps(sent_reply_metadata, indent=2, sort_keys=True)
    sent_reply_metadata_path.write_text(sent_reply_metadata_serialized, encoding="utf-8")
    sent_reply_metadata_hash = hashlib.sha256(sent_reply_metadata_serialized.encode("utf-8")).hexdigest()

    html_artifact = create_message_artifact(message, SENT_REPLY_HTML_ARTIFACT, sent_reply_html_path, sent_reply_html_hash)
    create_message_artifact(message, SENT_REPLY_METADATA_ARTIFACT, sent_reply_metadata_path, sent_reply_metadata_hash)
    return html_artifact


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
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        logger.exception("Failed to read body artifact for message %s from %s.", message.id, path)
        return ""


def read_body_html_artifact(message: Message) -> str:
    artifact = next((item for item in message.artifacts if item.artifact_type == "sanitized_body_html"), None)
    if artifact is not None:
        path = Path(artifact.storage_uri)
        if path.exists():
            try:
                return trim_leading_rendered_email_html(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError):
                logger.exception("Failed to read HTML body artifact for message %s from %s.", message.id, path)
                return ""

    raw_artifact = next((item for item in message.artifacts if item.artifact_type == "raw_gmail_message"), None)
    if raw_artifact is None:
        return ""
    raw_path = Path(raw_artifact.storage_uri)
    if not raw_path.exists():
        return ""

    try:
        raw_message = json.loads(raw_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError):
        return ""

    payload = raw_message.get("payload") or {}
    return trim_leading_rendered_email_html(sanitize_email_html(extract_body_html(payload)))


def trim_leading_rendered_email_html(rendered_html: str) -> str:
    trimmed = rendered_html.lstrip()
    if not trimmed:
        return ""

    leading_empty_block_pattern = re.compile(
        r"^(?:"
        r"<br\s*/?>"
        r"|&nbsp;"
        r"|<div>\s*(?:&nbsp;|\s|<br\s*/?>)*</div>"
        r"|<p>\s*(?:&nbsp;|\s|<br\s*/?>)*</p>"
        r"|<span>\s*(?:&nbsp;|\s|<br\s*/?>)*</span>"
        r")+",
        flags=re.IGNORECASE,
    )

    while True:
        updated = leading_empty_block_pattern.sub("", trimmed, count=1).lstrip()
        if updated == trimmed:
            break
        trimmed = updated
    return trimmed


def read_sent_reply_records(
    message: Message,
    settings: Settings | None = None,
    *,
    allow_gmail_fallback: bool = True,
) -> list[SentReplyRecord]:
    html_artifacts = sorted(
        (artifact for artifact in message.artifacts if artifact.artifact_type == SENT_REPLY_HTML_ARTIFACT),
        key=lambda artifact: (artifact.created_at or datetime.min),
        reverse=True,
    )

    metadata_by_path: dict[str, dict[str, object]] = {}
    for artifact in message.artifacts:
        if artifact.artifact_type != SENT_REPLY_METADATA_ARTIFACT:
            continue
        path = Path(artifact.storage_uri)
        if not path.exists():
            continue
        try:
            metadata_by_path[path.stem] = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue

    records: list[SentReplyRecord] = []
    for artifact in html_artifacts:
        path = Path(artifact.storage_uri)
        if not path.exists():
            continue
        try:
            html_value = path.read_text(encoding="utf-8")
        except OSError:
            continue
        metadata = metadata_by_path.get(path.stem, {})
        records.append(SentReplyRecord(html=html_value, metadata=metadata, created_at=artifact.created_at))
    if records or settings is None or not allow_gmail_fallback:
        return records

    fallback_record = fetch_latest_sent_reply_from_gmail(message, settings)
    if fallback_record is None:
        return records
    return [fallback_record]


def fetch_latest_sent_reply_from_gmail(message: Message, settings: Settings) -> SentReplyRecord | None:
    if message.thread is None or message.mailbox is None or not message.thread.gmail_thread_id:
        return None

    mailbox_address = (message.mailbox.gmail_address or "").casefold()
    if not mailbox_address:
        return None

    try:
        thread_payload = GmailClient(settings).get_thread(message.thread.gmail_thread_id)
    except Exception:
        return None

    candidates: list[tuple[datetime | None, dict]] = []
    for thread_message in thread_payload.get("messages", []):
        payload = thread_message.get("payload") or {}
        headers = headers_to_dict(payload.get("headers", []))
        from_participant = parse_email_address(headers.get("from"))
        if from_participant is None or from_participant.email_address.casefold() != mailbox_address:
            continue
        sent_at = parse_datetime_header(headers.get("date")) or parse_internal_date(thread_message.get("internalDate"))
        candidates.append((sent_at, thread_message))

    if not candidates:
        return None

    candidates.sort(key=lambda item: item[0] or datetime.min, reverse=True)
    _, thread_message = candidates[0]
    payload = thread_message.get("payload") or {}
    headers = headers_to_dict(payload.get("headers", []))
    sent_at = parse_datetime_header(headers.get("date")) or parse_internal_date(thread_message.get("internalDate"))
    html_body = sanitize_email_html(extract_body_html(payload))
    if not html_body.strip():
        body_text = extract_body_text(payload)
        if body_text.strip():
            html_body = f"<pre>{html.escape(body_text)}</pre>"

    return SentReplyRecord(
        html=html_body,
        metadata={
            "effective_to": [participant.email_address for participant in parse_address_list(headers.get("to"))],
            "effective_cc": [participant.email_address for participant in parse_address_list(headers.get("cc"))],
            "subject": headers.get("subject"),
            "sent_at": sent_at.isoformat() if sent_at else None,
            "delivery_rule": "gmail_thread_fallback",
        },
        created_at=sent_at,
    )


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


def parse_send_form(body: bytes) -> dict[str, object]:
    parsed = parse_form_body(body)
    return {
        "draft_to": normalize_email_list(parsed.get("draft_to", [""])[0]),
        "draft_cc": normalize_email_list(parsed.get("draft_cc", [""])[0]),
        "draft_subject": normalize_optional_text(parsed.get("draft_subject", [""])[0]) or "Re:",
        "draft_html": normalize_optional_text(parsed.get("draft_html", [""])[0]) or "",
    }


def parse_draft_form(body: bytes) -> dict[str, object]:
    parsed = parse_form_body(body)
    return {
        "draft_to": normalize_optional_text(parsed.get("draft_to", [""])[0]) or "",
        "draft_cc": normalize_optional_text(parsed.get("draft_cc", [""])[0]) or "",
        "draft_subject": normalize_optional_text(parsed.get("draft_subject", [""])[0]) or "Re:",
        "draft_html": normalize_optional_text(parsed.get("draft_html", [""])[0]) or "",
    }


def parse_return_to(body: bytes, default: str) -> str:
    parsed = parse_form_body(body)
    return normalize_return_to(parsed.get("return_to", [default])[0], default)


def parse_form_body(body: bytes) -> dict[str, list[str]]:
    return parse_qs(body.decode("utf-8", errors="replace"), keep_blank_values=True)


def fail_work_item(
    session: Session,
    *,
    mailbox_id: int,
    work_item: WorkItem,
    event_type: str,
    summary: str,
    error_summary: str,
    detail: dict[str, object] | None = None,
    message_id: int | None = None,
) -> None:
    work_item.status = "failed"
    work_item.completed_at = utcnow()
    work_item.error_summary = error_summary
    session.add(
        AuditEvent(
            mailbox_id=mailbox_id,
            message_id=message_id,
            event_type=event_type,
            summary=summary,
            detail_json=json.dumps(detail or {}, sort_keys=True),
        )
    )
    session.flush()


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


def normalize_email_list(value: str | None) -> list[str]:
    normalized = normalize_optional_text(value)
    if normalized is None:
        return []
    return [email for _, email in getaddresses([normalized]) if email]


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


def normalize_history_tab(value: str | None) -> str:
    normalized = (value or "responded").strip().lower()
    if normalized not in {"responded", "ignored"}:
        return "responded"
    return normalized


def normalize_ignored_scope(value: str | None) -> str:
    normalized = (value or "manual").strip().lower()
    if normalized not in {"manual", "all"}:
        return "manual"
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


def normalize_participant_name(value: str | None) -> str:
    normalized = (value or "").strip().casefold()
    normalized = re.sub(r"^(cata\s*-\s*|cata\s+)", "", normalized)
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
    return " ".join(normalized.split())


def get_self_identity_addresses(message: Message) -> set[str]:
    settings = get_settings()
    identities: set[str] = set()
    mailbox_address = ((message.mailbox.gmail_address if message.mailbox else "") or "").strip().casefold()
    if mailbox_address:
        identities.add(mailbox_address)
    for alias in settings.default_gmail_aliases:
        normalized_alias = str(alias).strip().casefold()
        if normalized_alias:
            identities.add(normalized_alias)

    self_names: set[str] = set()
    for participant in message.participants:
        participant_email = ((participant.email_address or "") or "").strip().casefold()
        if participant_email and participant_email in identities:
            normalized_name = normalize_participant_name(participant.display_name)
            if normalized_name:
                self_names.add(normalized_name)

    if self_names:
        for participant in message.participants:
            normalized_name = normalize_participant_name(participant.display_name)
            participant_email = ((participant.email_address or "") or "").strip().casefold()
            if normalized_name and participant_email and normalized_name in self_names:
                identities.add(participant_email)

    return identities


def get_reply_to_addresses(message: Message) -> str:
    saved = read_saved_draft_record(message)
    if saved is not None:
        return str(saved.get("draft_to") or "")
    if message.from_address:
        return message.from_address
    return ""


def get_default_reply_to_addresses(message: Message) -> list[str]:
    reply_to_addresses = normalize_email_list(message.from_address)
    if reply_to_addresses:
        return reply_to_addresses
    return []


def get_reply_cc_addresses(message: Message) -> str:
    saved = read_saved_draft_record(message)
    if saved is not None:
        return str(saved.get("draft_cc") or "")
    self_identity_addresses = get_self_identity_addresses(message)
    reply_target_addresses = {address.casefold() for address in get_default_reply_to_addresses(message)}
    sender_address = ((message.from_address or "") or "").strip().casefold()
    sender_display = ((message.from_display or "") or "").strip().casefold()
    cc_addresses: list[str] = []
    seen: set[str] = set()
    for participant in sorted(message.participants, key=lambda item: (item.position_index, item.id)):
        participant_email = ((participant.email_address or "") or "").strip()
        normalized_email = participant_email.casefold()
        normalized_name = ((participant.display_name or "") or "").strip().casefold()
        if not participant_email:
            continue
        if normalized_email in self_identity_addresses:
            continue
        if normalized_email in reply_target_addresses:
            continue
        if sender_address and normalized_email == sender_address:
            continue
        if sender_display and normalized_name and normalized_name == sender_display:
            continue
        if normalized_email in seen:
            continue
        seen.add(normalized_email)
        cc_addresses.append(participant_email)
    return ", ".join(cc_addresses)


def has_prior_sent_reply(message: Message) -> bool:
    return bool(message.responded_at or message.latest_sent_reply_id)


def get_ignore_source(message: Message) -> str:
    ignore_events = [event for event in message.audit_events if event.event_type == "message_ignored"]
    if not ignore_events:
        return "automatic"
    latest_event = max(ignore_events, key=lambda event: event.created_at or datetime.min)
    if latest_event.actor_type == "admin_portal":
        return "manual"
    return "automatic"


def build_reply_subject(message: Message) -> str:
    saved = read_saved_draft_record(message)
    if saved is not None:
        subject = str(saved.get("draft_subject") or "").strip()
        if subject:
            return subject
    subject = (message.subject or "").strip()
    if not subject:
        return "Re:"
    if subject.lower().startswith("re:"):
        return subject
    return f"Re: {subject}"


def send_reply_message(
    session: Session,
    settings: Settings,
    message_id: int,
    *,
    draft_to: list[str],
    draft_cc: list[str],
    draft_subject: str,
    draft_html: str,
) -> Message:
    message = get_message_detail(session, message_id)
    if message is None:
        raise ValueError(f"Message {message_id} was not found.")
    if not draft_html.strip():
        raise ValueError("Reply draft is empty.")

    requested_to = draft_to
    requested_cc = draft_cc
    effective_to = requested_to
    effective_cc = requested_cc
    audit_rule = None

    override_address = normalize_optional_text(settings.gmail_test_send_override)
    if override_address:
        effective_to = [override_address]
        effective_cc = []
        audit_rule = TEST_SEND_AUDIT_RULE

    client = GmailClient(settings)
    outbound_html = build_outbound_reply_html(message, draft_html, read_sent_reply_records(message, settings))

    send_result = client.send_message(
        to_addresses=effective_to,
        cc_addresses=effective_cc,
        subject=draft_subject,
        html_body=outbound_html,
        thread_id=message.thread.gmail_thread_id if message.thread else None,
        in_reply_to=message.rfc_message_id,
        references=message.rfc_message_id,
    )

    old_status = message.status
    message.status = "responded"
    message.responded_at = utcnow()

    if message.draft_state == "not_started":
        message.draft_state = "ready"

    sent_reply_folder = settings.resolved_artifact_root / "sent-replies" / f"mailbox-{message.mailbox_id}"
    sent_reply_folder.mkdir(parents=True, exist_ok=True)
    sent_reply_stem = f"{message.gmail_message_id}-{int(message.responded_at.timestamp())}"
    sent_reply_html = sanitize_email_html(outbound_html)
    sent_reply_html_path = sent_reply_folder / f"{sent_reply_stem}.html"
    sent_reply_html_path.write_text(sent_reply_html, encoding="utf-8")
    sent_reply_html_hash = hashlib.sha256(sent_reply_html.encode("utf-8")).hexdigest()

    sent_reply_metadata = {
        "requested_to": requested_to,
        "requested_cc": requested_cc,
        "effective_to": effective_to,
        "effective_cc": effective_cc,
        "subject": draft_subject,
        "gmail_send_result": send_result,
        "delivery_rule": audit_rule,
        "sent_at": message.responded_at.isoformat() if message.responded_at else None,
    }
    sent_reply_metadata_path = sent_reply_folder / f"{sent_reply_stem}.json"
    sent_reply_metadata_serialized = json.dumps(sent_reply_metadata, indent=2, sort_keys=True)
    sent_reply_metadata_path.write_text(sent_reply_metadata_serialized, encoding="utf-8")
    sent_reply_metadata_hash = hashlib.sha256(sent_reply_metadata_serialized.encode("utf-8")).hexdigest()

    html_artifact = create_message_artifact(
        message,
        SENT_REPLY_HTML_ARTIFACT,
        sent_reply_html_path,
        sent_reply_html_hash,
    )
    create_message_artifact(
        message,
        SENT_REPLY_METADATA_ARTIFACT,
        sent_reply_metadata_path,
        sent_reply_metadata_hash,
    )
    session.flush()
    message.latest_sent_reply_id = html_artifact.id

    session.add(
        AuditEvent(
            mailbox_id=message.mailbox_id,
            message_id=message.id,
            event_type="message_reply_sent",
            actor_type="admin_portal",
            summary="Administrator sent a reply through the portal.",
            detail_json=json.dumps(
                {"old_status": old_status, "new_status": "responded", **sent_reply_metadata},
                sort_keys=True,
            ),
        )
    )
    session.commit()
    return get_message_detail(session, message_id) or message


def save_message_draft(
    session: Session,
    settings: Settings,
    message_id: int,
    *,
    draft_to: str,
    draft_cc: str,
    draft_subject: str,
    draft_html: str,
) -> Message:
    message = get_message_detail(session, message_id)
    if message is None:
        raise ValueError(f"Message {message_id} was not found.")
    if not draft_html.strip():
        raise ValueError("Reply draft is empty.")

    draft_folder = settings.resolved_artifact_root / "drafts" / f"mailbox-{message.mailbox_id}"
    draft_folder.mkdir(parents=True, exist_ok=True)
    draft_path = draft_folder / f"{message.gmail_message_id}.json"
    payload = {
        "draft_to": draft_to,
        "draft_cc": draft_cc,
        "draft_subject": draft_subject,
        "draft_html": sanitize_email_html(draft_html),
        "saved_at": utcnow().isoformat(),
    }
    serialized = json.dumps(payload, indent=2, sort_keys=True)
    draft_path.write_text(serialized, encoding="utf-8")
    draft_hash = hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    existing = next((artifact for artifact in message.artifacts if artifact.artifact_type == PORTAL_DRAFT_ARTIFACT), None)
    if existing is None:
        existing = create_message_artifact(message, PORTAL_DRAFT_ARTIFACT, draft_path, draft_hash)
    else:
        existing.storage_uri = str(draft_path)
        existing.content_sha256 = draft_hash

    session.flush()
    message.latest_draft_id = existing.id
    message.draft_state = "ready"
    message.updated_at = utcnow()
    session.add(
        AuditEvent(
            mailbox_id=message.mailbox_id,
            message_id=message.id,
            event_type="message_draft_saved",
            actor_type="admin_portal",
            summary="Administrator saved a reply draft in the portal.",
        )
    )
    session.commit()
    return get_message_detail(session, message_id) or message


def build_default_draft_html(message: Message) -> str:
    saved = read_saved_draft_record(message)
    if saved is not None:
        saved_html = str(saved.get("draft_html") or "").strip()
        if saved_html:
            return saved_html

    summary_html = build_manual_work_summary_html(message)
    if summary_html:
        return summary_html

    recipient_name = resolve_reply_recipient_name(message)
    return (
        f'<p style="margin: 0 0 0.35rem; font-family: Aptos, Calibri, sans-serif; font-size: 12pt; font-weight: 400;">Hi {html.escape(recipient_name)},</p>'
        '<p style="margin: 0; font-family: Aptos, Calibri, sans-serif; font-size: 12pt; font-weight: 400;"><br></p>'
        '<p style="margin: 0; font-family: Aptos, Calibri, sans-serif; font-size: 12pt; font-weight: 400;"><br></p>'
        '<p style="margin: 0; font-family: Aptos, Calibri, sans-serif; font-size: 12pt; font-weight: 400;">Thank you,</p>'
        '<p style="margin: 0; font-family: Tahoma, sans-serif; font-size: 11pt; font-weight: 700;">Casey Herridge</p>'
        '<p style="margin: 0; font-family: Tahoma, sans-serif; font-size: 11pt; font-weight: 400;">Leagues Director | (210) 275.3173</p>'
        '<p style="margin: 0; line-height: 1.1;">'
        '<span style="font-family: Tahoma, sans-serif; font-size: 9pt; font-weight: 400;">Capital Area Tennis Association </span>'
        '<span style="font-family: Tahoma, sans-serif; font-size: 5pt; font-weight: 400;">d/b/a</span>'
        '<span style="font-family: Tahoma, sans-serif; font-size: 9pt; font-weight: 400;"> Tennis Austin</span>'
        "</p>"
        f"{build_default_signature_logo_html()}"
    )


def build_default_signature_logo_html() -> str:
    global _DEFAULT_SIGNATURE_LOGO_HTML
    if _DEFAULT_SIGNATURE_LOGO_HTML is not None:
        return _DEFAULT_SIGNATURE_LOGO_HTML
    if not DEFAULT_SIGNATURE_LOGO_PATH.exists():
        _DEFAULT_SIGNATURE_LOGO_HTML = ""
        return ""
    try:
        encoded = base64.b64encode(DEFAULT_SIGNATURE_LOGO_PATH.read_bytes()).decode("ascii")
    except OSError:
        _DEFAULT_SIGNATURE_LOGO_HTML = ""
        return ""
    _DEFAULT_SIGNATURE_LOGO_HTML = (
        '<div style="margin-top: 4px;">'
        '<img '
        f'src="data:image/webp;base64,{encoded}" '
        'alt="Tennis Austin" '
        'style="display: block; width: 180px; height: auto;">'
        "</div>"
    )
    return _DEFAULT_SIGNATURE_LOGO_HTML


def resolve_reply_recipient_name(message: Message) -> str:
    candidate = first_name_from_sender(message.from_display)
    if candidate:
        return candidate
    candidate = first_name_from_sender(message.from_address)
    if candidate:
        return candidate
    return "there"


def read_saved_draft_record(message: Message) -> dict[str, object] | None:
    artifact = next((item for item in message.artifacts if item.artifact_type == PORTAL_DRAFT_ARTIFACT), None)
    if artifact is None:
        return None
    path = Path(artifact.storage_uri)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeDecodeError):
        logger.exception("Failed to read saved portal draft for message %s.", message.id)
        return None
    return payload if isinstance(payload, dict) else None


def first_name_from_sender(value: str | None) -> str | None:
    normalized = (value or "").strip()
    if not normalized:
        return None

    if "@" in normalized and "<" not in normalized and " " not in normalized:
        local_part = normalized.split("@", 1)[0]
        normalized = local_part.replace(".", " ").replace("_", " ").replace("-", " ")

    normalized = normalized.strip().strip("\"' ")
    normalized = re.sub(r"\s+via\s+.*$", "", normalized, flags=re.IGNORECASE).strip()
    normalized = re.sub(r"\s*<[^>]+>$", "", normalized).strip()
    if not normalized:
        return None

    for token in re.split(r"\s+", normalized):
        cleaned = re.sub(r"^[^A-Za-z]+|[^A-Za-z'-]+$", "", token)
        if cleaned and re.search(r"[A-Za-z]", cleaned):
            return cleaned.capitalize() if cleaned.islower() or cleaned.isupper() else cleaned
    return None


def build_outbound_reply_html(
    message: Message,
    draft_html: str,
    prior_sent_replies: list[SentReplyRecord] | None = None,
) -> str:
    cleaned_draft = sanitize_email_html(draft_html)
    sections = [cleaned_draft]

    prior_records = prior_sent_replies or []
    if prior_records:
        latest_prior = prior_records[0]
        sent_label = ""
        if message.responded_at is not None:
            sent_label = f"Sent previously: {html.escape(message.responded_at.isoformat(sep=' ', timespec='minutes'))}"
        sections.append(
            "<hr>"
            "<div><strong>Previous reply</strong>"
            f"{f'<div>{sent_label}</div>' if sent_label else ''}"
            "</div>"
            f"{latest_prior.html}"
        )
    else:
        original_subject = html.escape((message.subject or "").strip() or "(No subject)")
        original_from = html.escape(message.from_display or message.from_address or "Unknown")
        original_received = ""
        if message.received_at is not None:
            original_received = html.escape(message.received_at.isoformat(sep=" ", timespec="minutes"))
        original_body_html = read_body_html_artifact(message)
        if not original_body_html.strip():
            body_text = read_body_artifact(message)
            original_body_html = f"<pre>{html.escape(body_text)}</pre>" if body_text.strip() else ""

        sections.append(
            "<hr>"
            "<div><strong>Original message</strong></div>"
            f"<div><strong>From:</strong> {original_from}</div>"
            f"{f'<div><strong>Sent:</strong> {original_received}</div>' if original_received else ''}"
            f"<div><strong>Subject:</strong> {original_subject}</div>"
            f"{original_body_html}"
        )
    return "".join(sections)


def build_manual_work_summary_html(message: Message) -> str:
    category_name = (message.assigned_category.name if message.assigned_category else "").casefold()
    body_text = read_body_artifact(message)

    if category_name == "team registration submission":
        registration_fields = parse_team_registration_fields(body_text)
        if registration_fields:
            rows = "".join(
                f"<tr><th>{html.escape(label)}</th><td>{html.escape(value)}</td></tr>"
                for label, value in registration_fields
            )
            return (
                "<p><strong>Manual Processing Summary</strong></p>"
                "<p>Use this extracted registration snapshot while batching team-number setup.</p>"
                "<table>"
                f"{rows}"
                "</table>"
            )

    return ""


def parse_team_registration_fields(body_text: str) -> list[tuple[str, str]]:
    label_aliases = {
        "Date": ["Date"],
        "Captain Name": ["Captain Name"],
        "Captain USTA Number": ["Captain USTA Number"],
        "Registration Type": ["Registration Type"],
        "Phone": ["Phone"],
        "Email": ["Email"],
        "Team Name": ["Team Name"],
        "Gender/Day": ["Gender/Day"],
        "League NTRP Level of Play": ["League NTRP Level of Play"],
        "League Home Courts or Event (do not select a facility unless you have ALREADY received permission to play out of this facility)": [
            "League Home Courts or Event (do not select a facility unless you have ALREADY received permission to play out of this facility)",
            "Home Courts or Event (do not select a facility unless you have ALREADY received permission to play out of this facility)",
        ],
        "Home Courts Contact (the name of the person who has given you written permission to use their courts)": [
            "Home Courts Contact (the name of the person who has given you written permission to use their courts)"
        ],
        "Home Courts Contact Phone": ["Home Courts Contact Phone"],
        "Do you have permission to use these courts? (if you select yes, you are confirming that you have already received written permission from this facility to use their courts)": [
            "Do you have permission to use these courts? (if you select yes, you are confirming that you have already received written permission from this facility to use their courts)"
        ],
    }
    parsed = extract_ordered_fields(" ".join(body_text.split()), label_aliases)
    labels = [
        ("Captain Name", "Captain Name"),
        ("Captain USTA Number", "Captain USTA Number"),
        ("Registration Type", "Registration Type"),
        ("Captain Email", "Email"),
        ("Team Name", "Team Name"),
        ("League", "Gender/Day"),
        ("Level", "League NTRP Level of Play"),
        (
            "Facility",
            "League Home Courts or Event (do not select a facility unless you have ALREADY received permission to play out of this facility)",
        ),
    ]
    return [(output_label, parsed[source_label]) for output_label, source_label in labels if parsed.get(source_label)]


def extract_ordered_fields(body_text: str, label_aliases: dict[str, list[str]]) -> dict[str, str]:
    found_labels: list[tuple[int, str, str]] = []
    for canonical_label, aliases in label_aliases.items():
        for alias in aliases:
            match = re.search(re.escape(alias), body_text, re.IGNORECASE)
            if match:
                found_labels.append((match.start(), canonical_label, alias))
                break

    found_labels.sort()
    extracted: dict[str, str] = {}
    for index, (start, canonical_label, matched_alias) in enumerate(found_labels):
        value_start = start + len(matched_alias)
        value_end = found_labels[index + 1][0] if index + 1 < len(found_labels) else len(body_text)
        value = body_text[value_start:value_end].strip()
        if value:
            extracted[canonical_label] = value
    return extracted
