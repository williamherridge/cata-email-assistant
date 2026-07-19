"""SQLAlchemy models for the Milestone A pilot schema."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.shared.database import Base


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    display_name: Mapped[str | None] = mapped_column(Text)
    role: Mapped[str] = mapped_column(Text, nullable=False, default="admin")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow, onupdate=utcnow)


class Mailbox(Base):
    __tablename__ = "mailboxes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    gmail_address: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    display_name: Mapped[str | None] = mapped_column(Text)
    gmail_profile_id: Mapped[str | None] = mapped_column(Text)
    last_successful_history_id: Mapped[str | None] = mapped_column(Text)
    last_polled_at: Mapped[datetime | None] = mapped_column(DateTime)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow, onupdate=utcnow)

    poll_runs: Mapped[list[PollRun]] = relationship(back_populates="mailbox")
    work_items: Mapped[list[WorkItem]] = relationship(back_populates="mailbox")
    threads: Mapped[list[MessageThread]] = relationship(back_populates="mailbox")
    messages: Mapped[list[Message]] = relationship(back_populates="mailbox")


class PollRun(Base):
    __tablename__ = "poll_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    mailbox_id: Mapped[int] = mapped_column(ForeignKey("mailboxes.id"), nullable=False)
    trigger_source: Mapped[str] = mapped_column(Text, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="running")
    history_id_start: Mapped[str | None] = mapped_column(Text)
    history_id_end: Mapped[str | None] = mapped_column(Text)
    messages_discovered: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    messages_enqueued: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_summary: Mapped[str | None] = mapped_column(Text)

    mailbox: Mapped[Mailbox] = relationship(back_populates="poll_runs")
    work_items: Mapped[list[WorkItem]] = relationship(back_populates="poll_run")


class MessageThread(Base):
    __tablename__ = "message_threads"
    __table_args__ = (UniqueConstraint("mailbox_id", "gmail_thread_id", name="uq_message_threads_mailbox_thread"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    mailbox_id: Mapped[int] = mapped_column(ForeignKey("mailboxes.id"), nullable=False)
    gmail_thread_id: Mapped[str] = mapped_column(Text, nullable=False)
    subject_canonical: Mapped[str | None] = mapped_column(Text)
    latest_message_received_at: Mapped[datetime | None] = mapped_column(DateTime)
    latest_message_id: Mapped[int | None] = mapped_column(ForeignKey("messages.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow, onupdate=utcnow)

    mailbox: Mapped[Mailbox] = relationship(back_populates="threads")
    messages: Mapped[list[Message]] = relationship(back_populates="thread", foreign_keys="Message.thread_id")
    latest_message: Mapped[Message | None] = relationship(foreign_keys=[latest_message_id], post_update=True)


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (UniqueConstraint("mailbox_id", "gmail_message_id", name="uq_messages_mailbox_message"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    mailbox_id: Mapped[int] = mapped_column(ForeignKey("mailboxes.id"), nullable=False)
    thread_id: Mapped[int | None] = mapped_column(ForeignKey("message_threads.id"))
    gmail_message_id: Mapped[str] = mapped_column(Text, nullable=False)
    gmail_history_id: Mapped[str | None] = mapped_column(Text)
    rfc_message_id: Mapped[str | None] = mapped_column(Text)
    gmail_internal_date: Mapped[datetime | None] = mapped_column(DateTime)
    from_display: Mapped[str | None] = mapped_column(Text)
    from_address: Mapped[str | None] = mapped_column(Text)
    subject: Mapped[str | None] = mapped_column(Text)
    snippet: Mapped[str | None] = mapped_column(Text)
    received_at: Mapped[datetime | None] = mapped_column(DateTime)
    has_attachments: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="new")
    draft_state: Mapped[str] = mapped_column(Text, nullable=False, default="not_started")
    priority: Mapped[str] = mapped_column(Text, nullable=False, default="normal")
    informational_only: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    reply_needed: Mapped[bool | None] = mapped_column(Boolean)
    assigned_category_id: Mapped[int | None] = mapped_column(Integer)
    assigned_subcategory_id: Mapped[int | None] = mapped_column(Integer)
    proposed_category_label: Mapped[str | None] = mapped_column(Text)
    proposed_subcategory_label: Mapped[str | None] = mapped_column(Text)
    latest_analysis_id: Mapped[int | None] = mapped_column(Integer)
    latest_prework_id: Mapped[int | None] = mapped_column(Integer)
    latest_draft_id: Mapped[int | None] = mapped_column(Integer)
    latest_sent_reply_id: Mapped[int | None] = mapped_column(Integer)
    opened_in_portal_at: Mapped[datetime | None] = mapped_column(DateTime)
    responded_at: Mapped[datetime | None] = mapped_column(DateTime)
    ignored_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow, onupdate=utcnow)

    mailbox: Mapped[Mailbox] = relationship(back_populates="messages")
    thread: Mapped[MessageThread | None] = relationship(back_populates="messages", foreign_keys=[thread_id])
    participants: Mapped[list[MessageParticipant]] = relationship(back_populates="message", cascade="all, delete-orphan")
    headers: Mapped[list[MessageHeader]] = relationship(back_populates="message", cascade="all, delete-orphan")
    attachments: Mapped[list[MessageAttachment]] = relationship(back_populates="message", cascade="all, delete-orphan")
    artifacts: Mapped[list[MessageArtifact]] = relationship(back_populates="message", cascade="all, delete-orphan")
    work_items: Mapped[list[WorkItem]] = relationship(back_populates="message")
    audit_events: Mapped[list[AuditEvent]] = relationship(back_populates="message")


class WorkItem(Base):
    __tablename__ = "work_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    work_type: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="pending")
    mailbox_id: Mapped[int | None] = mapped_column(ForeignKey("mailboxes.id"))
    message_id: Mapped[int | None] = mapped_column(ForeignKey("messages.id"))
    poll_run_id: Mapped[int | None] = mapped_column(ForeignKey("poll_runs.id"))
    scheduled_for: Mapped[datetime | None] = mapped_column(DateTime)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    lease_token: Mapped[str | None] = mapped_column(Text)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime)
    payload_json: Mapped[str | None] = mapped_column(Text)
    error_summary: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)

    mailbox: Mapped[Mailbox | None] = relationship(back_populates="work_items")
    message: Mapped[Message | None] = relationship(back_populates="work_items")
    poll_run: Mapped[PollRun | None] = relationship(back_populates="work_items")


class MessageParticipant(Base):
    __tablename__ = "message_participants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    message_id: Mapped[int] = mapped_column(ForeignKey("messages.id"), nullable=False)
    participant_type: Mapped[str] = mapped_column(Text, nullable=False)
    display_name: Mapped[str | None] = mapped_column(Text)
    email_address: Mapped[str] = mapped_column(Text, nullable=False)
    position_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    message: Mapped[Message] = relationship(back_populates="participants")


class MessageHeader(Base):
    __tablename__ = "message_headers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    message_id: Mapped[int] = mapped_column(ForeignKey("messages.id"), nullable=False)
    header_name: Mapped[str] = mapped_column(Text, nullable=False)
    header_value: Mapped[str] = mapped_column(Text, nullable=False)

    message: Mapped[Message] = relationship(back_populates="headers")


class MessageAttachment(Base):
    __tablename__ = "message_attachments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    message_id: Mapped[int] = mapped_column(ForeignKey("messages.id"), nullable=False)
    gmail_attachment_id: Mapped[str | None] = mapped_column(Text)
    filename: Mapped[str | None] = mapped_column(Text)
    mime_type: Mapped[str | None] = mapped_column(Text)
    size_bytes: Mapped[int | None] = mapped_column(Integer)
    is_inline: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    message: Mapped[Message] = relationship(back_populates="attachments")


class MessageArtifact(Base):
    __tablename__ = "message_artifacts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    message_id: Mapped[int] = mapped_column(ForeignKey("messages.id"), nullable=False)
    artifact_type: Mapped[str] = mapped_column(Text, nullable=False)
    storage_uri: Mapped[str] = mapped_column(Text, nullable=False)
    content_sha256: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)

    message: Mapped[Message] = relationship(back_populates="artifacts")


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    message_id: Mapped[int | None] = mapped_column(ForeignKey("messages.id"))
    mailbox_id: Mapped[int | None] = mapped_column(ForeignKey("mailboxes.id"))
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    actor_type: Mapped[str] = mapped_column(Text, nullable=False, default="system")
    actor_id: Mapped[str | None] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text)
    detail_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)

    message: Mapped[Message | None] = relationship(back_populates="audit_events")
