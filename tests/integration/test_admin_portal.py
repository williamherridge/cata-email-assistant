from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.admin_portal.main import app
from src.shared.database import Base, get_db_session
from src.shared.models import (
    AuditEvent,
    Category,
    Mailbox,
    Message,
    MessageArtifact,
    MessageParticipant,
    MessageThread,
    Subcategory,
)
from src.workflow import polling


class FakeSendGmailClient:
    sent_messages: list[dict] = []

    def __init__(self, _settings):
        pass

    def send_message(
        self,
        *,
        to_addresses,
        cc_addresses,
        subject,
        html_body,
        thread_id=None,
        in_reply_to=None,
        references=None,
    ):
        payload = {
            "to_addresses": to_addresses,
            "cc_addresses": cc_addresses,
            "subject": subject,
            "html_body": html_body,
            "thread_id": thread_id,
            "in_reply_to": in_reply_to,
            "references": references,
        }
        self.__class__.sent_messages.append(payload)
        return {"id": "sent-1", "threadId": thread_id or "thread-1"}


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
        rfc_message_id="<msg-1@example.com>",
        from_address="parent@example.com",
        snippet="League registration opens next week.",
        status="new",
        draft_state="not_started",
        priority="normal",
        informational_only=False,
        assigned_category_id=None,
    )
    session.add(message)
    session.flush()

    session.add(
        MessageParticipant(
            message_id=message.id,
            participant_type="cc",
            display_name="Casey",
            email_address="casey@austintennis.org",
        )
    )

    category = Category(name="Registration", is_active=True)
    session.add(category)
    session.flush()

    subcategory = Subcategory(category_id=category.id, name="League signup", is_active=True)
    session.add(subcategory)
    session.flush()
    message.assigned_category_id = category.id
    message.assigned_subcategory_id = subcategory.id

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
        FakeSendGmailClient.sent_messages.clear()
        original_gmail_client = polling.GmailClient
        polling.GmailClient = FakeSendGmailClient
        client = TestClient(app)

        queue_response = client.get("/queue")
        assert queue_response.status_code == 200
        assert "Registration question" in queue_response.text
        assert "Pilot Inbox" in queue_response.text
        assert "Sent update" not in queue_response.text
        assert "Already ignored" not in queue_response.text
        assert "Reply Draft" in queue_response.text
        assert "Original Email" in queue_response.text
        assert "Full Detail" in queue_response.text
        assert 'name="draft_cc" value=""' in queue_response.text

        filtered_search_response = client.get("/queue?search=Registration")
        assert filtered_search_response.status_code == 200
        assert "Registration question" in filtered_search_response.text
        assert "Apply" in filtered_search_response.text

        filtered_category_response = client.get(f"/queue?category_id={category.id}")
        assert filtered_category_response.status_code == 200
        assert "Registration question" in filtered_category_response.text

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
                "return_to": f"/queue?selected_message_id={message.id}",
                "priority": "critical",
                "reply_needed": "yes",
                "informational_only": "1",
                "assigned_category_id": str(category.id),
                "assigned_subcategory_id": str(subcategory.id),
            },
            follow_redirects=True,
        )
        assert review_response.status_code == 200
        assert "The queue view was updated after your last message action." in review_response.text
        session.expire_all()

        refreshed = session.get(Message, message.id)
        assert refreshed is not None
        assert refreshed.priority == "critical"
        assert refreshed.reply_needed is True
        assert refreshed.informational_only is True
        assert refreshed.assigned_category_id == category.id
        assert refreshed.assigned_subcategory_id == subcategory.id

        event_types = list(session.scalars(select(AuditEvent.event_type).where(AuditEvent.message_id == message.id)))
        assert "message_review_updated" in event_types

        failed_review_response = client.post(
            f"/messages/{message.id}/review",
            data={
                "return_to": f"/queue?selected_message_id={message.id}",
                "priority": "critical",
                "reply_needed": "yes",
                "assigned_category_id": "",
                "assigned_subcategory_id": str(subcategory.id),
            },
            follow_redirects=True,
        )
        assert failed_review_response.status_code == 200
        assert "Review changes could not be saved." in failed_review_response.text

        send_response = client.post(
            f"/messages/{message.id}/send",
            data={
                "return_to": "/queue",
                "priority": "normal",
                "reply_needed": "no",
                "assigned_category_id": str(category.id),
                "assigned_subcategory_id": str(subcategory.id),
                "draft_to": "parent@example.com",
                "draft_cc": "casey@austintennis.org",
                "draft_subject": "Re: Registration question",
                "draft_html": "<p>Test reply</p>",
            },
            follow_redirects=True,
        )
        assert send_response.status_code == 200
        assert "Reply sent. [Only to william@theherridges.com for testing] The message was marked responded and removed from the default queue." in send_response.text
        assert "Registration question" not in send_response.text

        assert len(FakeSendGmailClient.sent_messages) == 1
        sent_payload = FakeSendGmailClient.sent_messages[0]
        assert sent_payload["to_addresses"] == ["william@theherridges.com"]
        assert sent_payload["cc_addresses"] == []
        assert sent_payload["subject"] == "Re: Registration question"
        assert "Test reply" in sent_payload["html_body"]
        assert "Original message" in sent_payload["html_body"]
        assert "League registration opens next week." in sent_payload["html_body"]
        assert sent_payload["thread_id"] == "thread-1"
        assert sent_payload["in_reply_to"] == "<msg-1@example.com>"
        assert sent_payload["references"] == "<msg-1@example.com>"

        session.expire_all()
        responded = session.get(Message, message.id)
        assert responded is not None
        assert responded.status == "responded"
        assert responded.responded_at is not None

        event_types = list(session.scalars(select(AuditEvent.event_type).where(AuditEvent.message_id == message.id)))
        assert "message_reply_sent" in event_types

        history_response = client.get("/history?tab=responded")
        assert history_response.status_code == 200
        assert "History" in history_response.text
        assert "Sent/Responded" in history_response.text
        assert "Sent Reply" in history_response.text
        assert "Test reply" in history_response.text
        assert "Registration question" in history_response.text

        reopen_from_history_response = client.post(
            f"/messages/{message.id}/reopen",
            data={"return_to": f"/queue?selected_message_id={message.id}"},
            follow_redirects=True,
        )
        assert reopen_from_history_response.status_code == 200
        assert "Previous Reply Sent" in reopen_from_history_response.text
        assert "Test reply" in reopen_from_history_response.text

        session.expire_all()
        reopened_from_history = session.get(Message, message.id)
        assert reopened_from_history is not None
        assert reopened_from_history.status == "new"
        assert reopened_from_history.responded_at is not None

        return_to_responded_response = client.post(
            f"/messages/{message.id}/responded",
            data={"return_to": "/history?tab=responded"},
            follow_redirects=True,
        )
        assert return_to_responded_response.status_code == 200
        assert "History" in return_to_responded_response.text
        assert "Registration question" in return_to_responded_response.text

        session.expire_all()
        restored = session.get(Message, message.id)
        assert restored is not None
        assert restored.status == "responded"
        restored_responded_at = restored.responded_at
        assert restored_responded_at is not None

        second_send_response = client.post(
            f"/messages/{message.id}/reopen",
            data={"return_to": f"/queue?selected_message_id={message.id}"},
            follow_redirects=True,
        )
        assert second_send_response.status_code == 200

        second_send = client.post(
            f"/messages/{message.id}/send",
            data={
                "return_to": "/queue",
                "priority": "normal",
                "reply_needed": "no",
                "assigned_category_id": str(category.id),
                "assigned_subcategory_id": str(subcategory.id),
                "draft_to": "parent@example.com",
                "draft_cc": "",
                "draft_subject": "Re: Registration question",
                "draft_html": "<p>Second reply</p>",
            },
            follow_redirects=True,
        )
        assert second_send.status_code == 200

        assert len(FakeSendGmailClient.sent_messages) == 2
        second_sent_payload = FakeSendGmailClient.sent_messages[1]
        assert "Second reply" in second_sent_payload["html_body"]
        assert "Previous reply" in second_sent_payload["html_body"]
        assert "Test reply" in second_sent_payload["html_body"]
        assert second_sent_payload["html_body"].count("Original message") == 1
        assert second_sent_payload["html_body"].count("League registration opens next week.") == 1

        session.expire_all()
        second_responded = session.get(Message, message.id)
        assert second_responded is not None
        assert second_responded.status == "responded"
        assert second_responded.responded_at is not None
        assert second_responded.responded_at >= restored_responded_at

        ignore_response = client.post(
            f"/messages/{message.id}/ignore",
            data={"return_to": "/queue"},
            follow_redirects=True,
        )
        assert ignore_response.status_code == 200
        assert "The queue view was updated after your last message action." in ignore_response.text
        assert "Registration question" not in ignore_response.text

        session.expire_all()
        ignored = session.get(Message, message.id)
        assert ignored is not None
        assert ignored.status == "ignored"
        assert ignored.ignored_at is not None
        assert ignored.responded_at is not None

        event_types = list(session.scalars(select(AuditEvent.event_type).where(AuditEvent.message_id == message.id)))
        assert "message_ignored" in event_types

        ignored_history_response = client.get("/history?tab=ignored&ignored_scope=manual")
        assert ignored_history_response.status_code == 200
        assert "Ignored" in ignored_history_response.text
        assert "Manual only" in ignored_history_response.text
        assert "Registration question" in ignored_history_response.text

        reopen_response = client.post(
            f"/messages/{message.id}/reopen",
            data={"return_to": f"/messages/{message.id}"},
            follow_redirects=True,
        )
        assert reopen_response.status_code == 200
        assert "Review changes were saved." in reopen_response.text

        session.expire_all()
        reopened = session.get(Message, message.id)
        assert reopened is not None
        assert reopened.status == "new"
        assert reopened.ignored_at is None
        assert reopened.responded_at is not None

        event_types = list(session.scalars(select(AuditEvent.event_type).where(AuditEvent.message_id == message.id)))
        assert "message_reopened" in event_types
    finally:
        polling.GmailClient = original_gmail_client
        app.dependency_overrides.clear()
        session.close()
