from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.admin_portal.main import app
from src.shared.database import Base, get_db_session
from src.shared.models import Mailbox, Message, MessageArtifact, MessageThread


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

        detail_response = client.get(f"/messages/{message.id}")
        assert detail_response.status_code == 200
        assert "League registration opens next week." in detail_response.text
        assert "parent@example.com" in detail_response.text
    finally:
        app.dependency_overrides.clear()
        session.close()
