from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.admin_portal.main import app
from src.shared.database import Base, get_db_session
from src.shared.models import AuditEvent, Mailbox, Message, MessageArtifact, MessageThread


def test_queue_and_message_detail_render(tmp_path):
    db_path = tmp_path / "portal-test.db"
    engine = create_engine(
        f"sqlite:///{db_path}",
        future=True,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    session = session_factory()

    mailbox = Mailbox(gmail_address="pilot@cata.test", display_name="Pilot Inbox", is_active=True)
    session.add(mailbox)
    session.flush()

    thread = MessageThread(mailbox_id=mailbox.id, gmail_thread_id="thread-1", subject_canonical="Registration question")
    session.add(thread)
    session.flush()

    message = Message(
        mailbox_id=mailbox.id,
        thread_id=thread.id,
        gmail_message_id="msg-1",
        subject="Registration question",
        from_address="parent@example.com",
        snippet="League registration opens next week.",
        status="new",
        draft_state="not_started",
        priority="normal",
        informational_only=False,
    )
    session.add(message)
    session.flush()

    sent_message = Message(
        mailbox_id=mailbox.id,
        thread_id=thread.id,
        gmail_message_id="msg-2",
        subject="Sent update",
        from_address="pilot@cata.test",
        snippet="This should stay out of the default queue.",
        status="new",
        draft_state="not_started",
        priority="normal",
        informational_only=False,
    )
    session.add(sent_message)
    session.flush()

    ignored_message = Message(
        mailbox_id=mailbox.id,
        thread_id=thread.id,
        gmail_message_id="msg-3",
        subject="Already ignored",
        from_address="member@example.com",
        snippet="This should stay hidden too.",
        status="ignored",
        draft_state="not_started",
        priority="normal",
        informational_only=False,
    )
    session.add(ignored_message)
    session.flush()

    body_path = tmp_path / "body.txt"
    body_path.write_text("League registration opens next week.", encoding="utf-8")
    session.add(
        MessageArtifact(
            message_id=message.id,
            artifact_type="normalized_body_text",
            storage_uri=str(body_path),
        )
    )
    session.commit()

    def override_db():
        try:
            yield session
        finally:
            pass

    app.dependency_overrides[get_db_session] = override_db

    try:
        client = TestClient(app)

        queue_response = client.get("/queue")
        assert queue_response.status_code == 200
        assert "Registration question" in queue_response.text
        assert "Pilot Inbox" in queue_response.text
        assert "Sent update" not in queue_response.text
        assert "Already ignored" not in queue_response.text
        assert "pilot@cata.test</div>" not in queue_response.text

        poll_runs_response = client.get("/poll-runs")
        assert poll_runs_response.status_code == 200
        assert "Recent Poll Runs" in poll_runs_response.text

        detail_response = client.get(f"/messages/{message.id}")
        assert detail_response.status_code == 200
        assert "League registration opens next week." in detail_response.text
        assert "parent@example.com" in detail_response.text

        review_response = client.post(
            f"/messages/{message.id}/review",
            data={
                "priority": "high",
                "reply_needed": "yes",
                "informational_only": "1",
                "proposed_category_label": "Registration",
                "proposed_subcategory_label": "League signup",
            },
            follow_redirects=True,
        )
        assert review_response.status_code == 200
        assert "Review changes were saved." in review_response.text
        session.expire_all()

        refreshed = session.get(Message, message.id)
        assert refreshed is not None
        assert refreshed.priority == "high"
        assert refreshed.reply_needed is True
        assert refreshed.informational_only is True
        assert refreshed.proposed_category_label == "Registration"
        assert refreshed.proposed_subcategory_label == "League signup"

        event_types = list(session.scalars(select(AuditEvent.event_type).where(AuditEvent.message_id == message.id)))
        assert "message_review_updated" in event_types

        ignore_response = client.post(f"/messages/{message.id}/ignore", follow_redirects=True)
        assert ignore_response.status_code == 200
        assert "The queue view was updated after your last message action." in ignore_response.text
        assert "Registration question" not in ignore_response.text

        session.expire_all()
        ignored = session.get(Message, message.id)
        assert ignored is not None
        assert ignored.status == "ignored"
        assert ignored.ignored_at is not None

        event_types = list(session.scalars(select(AuditEvent.event_type).where(AuditEvent.message_id == message.id)))
        assert "message_ignored" in event_types

        reopen_response = client.post(f"/messages/{message.id}/reopen", follow_redirects=True)
        assert reopen_response.status_code == 200
        assert "Review changes were saved." in reopen_response.text

        session.expire_all()
        reopened = session.get(Message, message.id)
        assert reopened is not None
        assert reopened.status == "new"
        assert reopened.ignored_at is None

        event_types = list(session.scalars(select(AuditEvent.event_type).where(AuditEvent.message_id == message.id)))
        assert "message_reopened" in event_types
    finally:
        app.dependency_overrides.clear()
        session.close()
