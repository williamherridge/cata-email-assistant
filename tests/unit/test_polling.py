import json
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from src.shared.database import Base
from src.shared.models import Category, Mailbox, Message, MessageArtifact, MessageThread, PollRun, WorkItem
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


class FakeMakeupLineupGmailClient:
    def __init__(self, _settings):
        pass

    def get_profile(self):
        return {"emailAddress": "pilot@cata.test", "historyId": "333"}

    def discover_message_ids(self, _since_history_id):
        return type("Discovery", (), {"history_id": "333", "message_ids": ["msg-2"]})()

    def get_message(self, _message_id):
        body = (
            "Make-Up Match Line Up from Amy Saunders\n"
            "Original Match Number 1011881746\n"
            "Captain's Name Amy Saunders\n"
            "Opposing Captain Kathleen McDonald\n"
        )
        return {
            "id": "msg-2",
            "threadId": "thread-2",
            "historyId": "333",
            "internalDate": "1721404800000",
            "snippet": "Make-Up Match Line Up from Amy Saunders Original Match Number 1011881746",
            "payload": {
                "mimeType": "multipart/alternative",
                "headers": [
                    {"name": "Subject", "value": "Make-Up Match Line Up from Amy Saunders"},
                    {"name": "From", "value": "CATA <no-reply@austintennis.org>"},
                    {"name": "To", "value": "pilot@cata.test"},
                    {"name": "Date", "value": "Fri, 19 Jul 2024 10:00:00 -0500"},
                    {"name": "Message-Id", "value": "<msg-2@example.com>"},
                ],
                "parts": [
                    {
                        "mimeType": "text/plain",
                        "body": {"data": "TWFrZS1VcCBNYXRjaCBMaW5lIFVwIGZyb20gQW15IFNhdW5kZXJzCk9yaWdpbmFsIE1hdGNoIE51bWJlciAxMDExODgxNzQ2CkNhcHRhaW4ncyBOYW1lIEFteSBTYXVuZGVycwpPcHBvc2luZyBDYXB0YWluIEthdGhsZWVuIE1jRG9uYWxkCg=="},
                    }
                ],
            },
        }


class FakeReplyToMakeupLineupGmailClient:
    def __init__(self, _settings):
        pass

    def get_profile(self):
        return {"emailAddress": "pilot@cata.test", "historyId": "444"}

    def discover_message_ids(self, _since_history_id):
        return type("Discovery", (), {"history_id": "444", "message_ids": ["msg-3"]})()

    def get_message(self, _message_id):
        return {
            "id": "msg-3",
            "threadId": "thread-2",
            "historyId": "444",
            "internalDate": "1721404800000",
            "snippet": "The other captain is not cooperating. Can you help?",
            "payload": {
                "mimeType": "multipart/alternative",
                "headers": [
                    {"name": "Subject", "value": "Re: Make-Up Match Line Up from Amy Saunders"},
                    {"name": "From", "value": "Amy Saunders <asaunders512@gmail.com>"},
                    {"name": "To", "value": "pilot@cata.test"},
                    {"name": "Date", "value": "Fri, 19 Jul 2024 11:00:00 -0500"},
                    {"name": "Message-Id", "value": "<msg-3@example.com>"},
                ],
                "parts": [
                    {
                        "mimeType": "text/plain",
                        "body": {"data": "VGhlIG90aGVyIGNhcHRhaW4gaXMgbm90IGNvb3BlcmF0aW5nLiBDYW4geW91IGhlbHA/"},
                    }
                ],
            },
        }


class FakeTeamRegistrationGmailClient:
    def __init__(self, _settings):
        pass

    def get_profile(self):
        return {"emailAddress": "pilot@cata.test", "historyId": "555"}

    def discover_message_ids(self, _since_history_id):
        return type("Discovery", (), {"history_id": "555", "message_ids": ["msg-4"]})()

    def get_message(self, _message_id):
        body = (
            "New Fall Team Registration from Jamie LayTBD Date 07/19/2026 "
            "Captain Name Jamie Lay "
            "Captain USTA Number 11413470 "
            "Registration Type Closed but Seeking (People can contact you to join your team) "
            "Phone 863-712-6296 "
            "Email jameswarnerlay@gmail.com "
            "Team Name TBD "
            "Gender/Day Mens Weekend League FALL 18+ "
            "League NTRP Level of Play 3.5 "
            "League Home Courts or Event (do not select a facility unless you have ALREADY received permission to play out of this facility) Anderson High School "
            "Do you have permission to use these courts? (if you select yes, you are confirming that you have already received written permission from this facility to use their courts) Yes"
        )
        return {
            "id": "msg-4",
            "threadId": "thread-4",
            "historyId": "555",
            "internalDate": "1721404800000",
            "snippet": "New Fall Team Registration from Jamie LayTBD Date 07/19/2026 Captain Name Jamie Lay Captain USTA Number 11413470",
            "payload": {
                "mimeType": "multipart/alternative",
                "headers": [
                    {"name": "Subject", "value": "New Fall Team Registration from Jamie LayTBD"},
                    {"name": "From", "value": "CATA <no-reply@austintennis.org>"},
                    {"name": "To", "value": "pilot@cata.test"},
                    {"name": "Date", "value": "Sun, 19 Jul 2026 10:00:00 -0500"},
                    {"name": "Message-Id", "value": "<msg-4@example.com>"},
                ],
                "parts": [
                    {
                        "mimeType": "text/plain",
                        "body": {
                            "data": "TmV3IEZhbGwgVGVhbSBSZWdpc3RyYXRpb24gZnJvbSBKYW1pZSBMYXlUQkQgRGF0ZSAwNy8xOS8yMDI2IENhcHRhaW4gTmFtZSBKYW1pZSBMYXkgQ2FwdGFpbiBVU1RBIE51bWJlciAxMTQxMzQ3MCBSZWdpc3RyYXRpb24gVHlwZSBDbG9zZWQgYnV0IFNlZWtpbmcgKFBlb3BsZSBjYW4gY29udGFjdCB5b3UgdG8gam9pbiB5b3VyIHRlYW0pIFBob25lIDg2My03MTItNjI5NiBFbWFpbCBqYW1lc3dhcm5lcmxheUBnbWFpbC5jb20gVGVhbSBOYW1lIFRCRCBHZW5kZXIvRGF5IE1lbnMgV2Vla2VuZCBMZWFndWUgRkFMTCAxOCsgTGVhZ3VlIE5UUlAgTGV2ZWwgb2YgUGxheSAzLjUgTGVhZ3VlIEhvbWUgQ291cnRzIG9yIEV2ZW50IChkbyBub3Qgc2VsZWN0IGEgZmFjaWxpdHkgdW5sZXNzIHlvdSBoYXZlIEFMUkVBRFkgcmVjZWl2ZWQgcGVybWlzc2lvbiB0byBwbGF5IG91dCBvZiB0aGlzIGZhY2lsaXR5KSBBbmRlcnNvbiBIaWdoIFNjaG9vbCBEbyB5b3UgaGF2ZSBwZXJtaXNzaW9uIHRvIHVzZSB0aGVzZSBjb3VydHM/IChpZiB5b3Ugc2VsZWN0IHllcywgeW91IGFyZSBjb25maXJtaW5nIHRoYXQgeW91IGhhdmUgYWxyZWFkeSByZWNlaXZlZCB3cml0dGVuIHBlcm1pc3Npb24gZnJvbSB0aGlzIGZhY2lsaXR5IHRvIHVzZSB0aGVpciBjb3VydHMpIFllcw=="
                        },
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
    taxonomy_catalog_path = tmp_path / "taxonomy_catalog.json"
    taxonomy_catalog_path.write_text(
        json.dumps(
            {
                "updated_at": "2026-07-20T00:00:00",
                "categories": [{"name": "Make-up match line up"}, {"name": "Team registration submission"}],
            }
        ),
        encoding="utf-8",
    )
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
            "taxonomy_catalog_path": taxonomy_catalog_path,
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
    assert work_items[1].status == "completed"

    artifacts = session.scalars(select(MessageArtifact)).all()
    assert {artifact.artifact_type for artifact in artifacts} == {
        "raw_gmail_message",
        "normalized_body_text",
        "sanitized_body_html",
    }
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


def test_poll_mailbox_auto_classifies_makeup_lineup(monkeypatch, tmp_path):
    session = make_session()
    settings = make_settings(tmp_path)
    mailbox = Mailbox(gmail_address="pilot@cata.test", display_name="Pilot Inbox", is_active=True)
    session.add(mailbox)
    session.commit()

    monkeypatch.setattr(polling, "GmailClient", FakeMakeupLineupGmailClient)

    polling.poll_mailbox(session, settings, mailbox.id)

    message = session.scalar(select(Message).where(Message.gmail_message_id == "msg-2"))
    assert message is not None
    assert message.assigned_category is not None
    assert message.assigned_category.name == "Make-up match line up"
    assert message.reply_needed is False
    assert message.informational_only is True
    assert message.priority == "low"

    category = session.scalar(select(Category).where(Category.name == "Make-up match line up"))
    assert category is not None
    assert category.default_draft_behavior == "auto_ignore_candidate"
    assert category.default_reply_needed is False
    assert category.default_informational_only is True
    assert category.priority_hint == "low"


def test_reply_to_makeup_lineup_is_not_auto_classified(monkeypatch, tmp_path):
    session = make_session()
    settings = make_settings(tmp_path)
    mailbox = Mailbox(gmail_address="pilot@cata.test", display_name="Pilot Inbox", is_active=True)
    session.add(mailbox)
    session.commit()

    monkeypatch.setattr(polling, "GmailClient", FakeReplyToMakeupLineupGmailClient)

    polling.poll_mailbox(session, settings, mailbox.id)

    message = session.scalar(select(Message).where(Message.gmail_message_id == "msg-3"))
    assert message is not None
    assert message.assigned_category_id is None


def test_team_registration_auto_classifies_and_builds_manual_summary(monkeypatch, tmp_path):
    session = make_session()
    settings = make_settings(tmp_path)
    mailbox = Mailbox(gmail_address="pilot@cata.test", display_name="Pilot Inbox", is_active=True)
    session.add(mailbox)
    session.commit()

    monkeypatch.setattr(polling, "GmailClient", FakeTeamRegistrationGmailClient)

    polling.poll_mailbox(session, settings, mailbox.id)

    message = session.scalar(select(Message).where(Message.gmail_message_id == "msg-4"))
    assert message is not None
    assert message.assigned_category is not None
    assert message.assigned_category.name == "Team registration submission"
    assert message.reply_needed is False
    assert message.informational_only is False
    assert message.priority == "normal"

    summary_html = polling.build_default_draft_html(message)
    assert "Manual Processing Summary" in summary_html
    assert "Jamie Lay" in summary_html
    assert "11413470" in summary_html
    assert "Closed but Seeking" in summary_html
    assert "jameswarnerlay@gmail.com" in summary_html
    assert "TBD" in summary_html
    assert "Mens Weekend League FALL 18+" in summary_html
    assert "3.5" in summary_html
    assert "Anderson High School" in summary_html


def test_parse_team_registration_fields_handles_home_courts_contact_variants():
    body_text = (
        "New Fall Team Registration from Adeena ReitbergerAll Set! Date 07/19/2026 "
        "Captain Name Adeena Reitberger "
        "Captain USTA Number 2019129126 "
        "Registration Type Closed Team (only those you give team number to can join) "
        "Phone 2408886800 "
        "Email adeena@gmail.com "
        "Team Name All Set! "
        "Gender/Day Womens WeekEND League FALL 18+ League "
        "League NTRP Level of Play 3.0 League "
        "Home Courts or Event (do not select a facility unless you have ALREADY received permission to play out of this facility) "
        "UT Whitaker "
        "Home Courts Contact (the name of the person who has given you written permission to use their courts) Casey Herridge "
        "Home Courts Contact Phone 512-443-1342 "
        "Do you have permission to use these courts? (if you select yes, you are confirming that you have already received written permission from this facility to use their courts) Yes"
    )

    parsed = dict(polling.parse_team_registration_fields(body_text))

    assert parsed["Level"] == "3.0"
    assert parsed["Facility"] == "UT Whitaker"


def test_parse_team_registration_fields_handles_mixed_level_and_facility():
    body_text = (
        "New Fall Team Registration from Gabrielle JamesBalls & Boujee Date 07/19/2026 "
        "Captain Name Gabrielle James "
        "Captain USTA Number 2010818963 "
        "Registration Type Closed Team (only those you give team number to can join) "
        "Phone 5125845075 "
        "Email spydergab@gmail.com "
        "Team Name Balls & Boujee "
        "Gender/Day Mixed League FALL 18+ Mixed "
        "League NTRP Level of Play Mixed 8.0 "
        "Home Courts or Event (do not select a facility unless you have ALREADY received permission to play out of this facility) "
        "Westlake Country Club "
        "Home Courts Contact (the name of the person who has given you written permission to use their courts) Steve "
        "Home Courts Contact Phone 512-892-0173 "
        "Do you have permission to use these courts? (if you select yes, you are confirming that you have already received written permission from this facility to use their courts) Yes"
    )

    parsed = dict(polling.parse_team_registration_fields(body_text))

    assert parsed["Level"] == "Mixed 8.0"
    assert parsed["Facility"] == "Westlake Country Club"


def test_read_body_html_artifact_falls_back_to_raw_gmail_message(tmp_path):
    session = make_session()

    mailbox = Mailbox(gmail_address="pilot@cata.test", display_name="Pilot Inbox", is_active=True)
    session.add(mailbox)
    session.flush()

    thread = MessageThread(mailbox_id=mailbox.id, gmail_thread_id="thread-html", subject_canonical="HTML body")
    session.add(thread)
    session.flush()

    message = Message(
        mailbox_id=mailbox.id,
        thread_id=thread.id,
        gmail_message_id="msg-html",
        subject="HTML body",
        from_address="sender@example.com",
        status="new",
        draft_state="not_started",
        priority="normal",
        informational_only=False,
    )
    session.add(message)
    session.flush()

    raw_path = tmp_path / "msg-html.json"
    raw_path.write_text(
        json.dumps(
            {
                "payload": {
                    "mimeType": "text/html",
                    "body": {
                        "data": "PGRpdj48cD5GaXJzdCBsaW5lPC9wPjxwPlNlY29uZCBsaW5lPC9wPjxzY3JpcHQ-YWxlcnQoMSk8L3NjcmlwdD48L2Rpdj4="
                    },
                }
            }
        ),
        encoding="utf-8",
    )
    session.add(
        MessageArtifact(
            message_id=message.id,
            artifact_type="raw_gmail_message",
            storage_uri=str(raw_path),
        )
    )
    session.commit()

    rendered = polling.read_body_html_artifact(message)

    assert "<p>First line</p>" in rendered
    assert "<p>Second line</p>" in rendered
    assert "script" not in rendered
