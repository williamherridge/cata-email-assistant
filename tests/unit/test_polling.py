from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from src.shared.database import Base
from src.shared.models import Mailbox, Message, MessageArtifact, MessageThread, PollRun, WorkItem
from src.workflow import polling


class FakeGmailClient:
    def __init__(self, _settings):
        pass

    def get_profile(self):
        return {"emailAddress": "pilot@cata.test", "historyId": "222"}

    def discover_message_ids(self, _since_history_id):
        return type("Discovery", (), {"history_id": "222", "message_ids": ["msg-1"]})()

    def get_message(self, _message_id):
        return {
            "id": "msg-1",
            "threadId": "thread-1",
            "historyId": "222",
            "internalDate": "1721404800000",
            "snippet": "League registration opens next week.",
            "payload": {
                "mimeType": "multipart/alternative",
                "headers": [
                    {"name": "Subject", "value": "Registration question"},
                    {"name": "From", "value": "Parent Example <parent@example.com>"},
                    {"name": "To", "value": "pilot@cata.test"},
                    {"name": "Date", "value": "Fri, 19 Jul 2024 10:00:00 -0500"},
                    {"name": "Message-Id", "value": "<msg-1@example.com>"},
                ],
                "parts": [
                    {
                        "mimeType": "text/plain",
                        "body": {"data": "TGVhZ3VlIHJlZ2lzdHJhdGlvbiBvcGVucyBuZXh0IHdlZWsu"},
                    }
                ],
            },
        }


class FakeProfileOnlyGmailClient:
    def __init__(self, _settings):
        pass

    def get_profile(self):
        return {"emailAddress": "discovered@cata.test", "historyId": "222"}


def make_session() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    return session_factory()


def make_settings(tmp_path: Path):
    return type(
        "Settings",
        (),
        {
            "artifact_root": tmp_path / "artifacts",
            "database_url": f"sqlite:///{tmp_path / 'test.db'}",
            "default_gmail_address": "pilot@cata.test",
            "default_gmail_display_name": "Pilot Inbox",
            "gmail_oauth_credentials_path": Path("config/credentials.json"),
            "gmail_oauth_token_path": Path("config/token.json"),
            "gmail_initial_sync_days": 30,
            "gmail_initial_sync_max_results": 50,
            "resolved_artifact_root": tmp_path / "artifacts",
            "resolved_database_url": f"sqlite:///{tmp_path / 'test.db'}",
        },
    )()


def test_poll_mailbox_persists_messages_and_work_items(monkeypatch, tmp_path):
    session = make_session()
    settings = make_settings(tmp_path)
    mailbox = Mailbox(gmail_address="pilot@cata.test", display_name="Pilot Inbox", is_active=True)
    session.add(mailbox)
    session.commit()

    monkeypatch.setattr(polling, "GmailClient", FakeGmailClient)

    outcome = polling.poll_mailbox(session, settings, mailbox.id)

    assert outcome.messages_discovered == 1
    assert outcome.messages_persisted == 1

    stored_mailbox = session.get(Mailbox, mailbox.id)
    assert stored_mailbox.last_successful_history_id == "222"

    poll_runs = session.scalars(select(PollRun)).all()
    assert len(poll_runs) == 1
    assert poll_runs[0].status == "completed"

    threads = session.scalars(select(MessageThread)).all()
    assert len(threads) == 1
    assert threads[0].gmail_thread_id == "thread-1"

    messages = session.scalars(select(Message)).all()
    assert len(messages) == 1
    assert messages[0].subject == "Registration question"
    assert messages[0].from_address == "parent@example.com"

    work_items = session.scalars(select(WorkItem).order_by(WorkItem.id)).all()
    assert len(work_items) == 2
    assert work_items[0].work_type == "ingest_message"
    assert work_items[0].status == "completed"
    assert work_items[1].work_type == "analyze_message"
    assert work_items[1].status == "pending"

    artifacts = session.scalars(select(MessageArtifact)).all()
    assert {artifact.artifact_type for artifact in artifacts} == {"raw_gmail_message", "normalized_body_text"}
    for artifact in artifacts:
        assert Path(artifact.storage_uri).exists()


def test_ensure_default_mailbox_discovers_address_from_gmail_profile(monkeypatch, tmp_path):
    session = make_session()
    settings = make_settings(tmp_path)
    settings.default_gmail_address = None

    monkeypatch.setattr(polling, "GmailClient", FakeProfileOnlyGmailClient)

    mailbox = polling.ensure_default_mailbox(session, settings)

    assert mailbox is not None
    assert mailbox.gmail_address == "discovered@cata.test"
    assert mailbox.display_name == "Pilot Inbox"
