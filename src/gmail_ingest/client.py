"""Gmail client abstractions for the poll/ingest workflow."""

from __future__ import annotations

import base64
from dataclasses import dataclass
from email.message import EmailMessage

from src.gmail_ingest.auth import get_gmail_service
from src.shared.config import Settings


@dataclass
class GmailDiscoveryResult:
    history_id: str | None
    message_ids: list[str]


class GmailClient:
    """Thin wrapper around the Gmail API."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self._service = None

    @property
    def service(self):
        if self._service is None:
            self._service = get_gmail_service(
                credentials_path=self.settings.gmail_oauth_credentials_path,
                token_path=self.settings.gmail_oauth_token_path,
            )
        return self._service

    def get_profile(self) -> dict:
        return self.service.users().getProfile(userId="me").execute()

    def discover_message_ids(self, since_history_id: str | None) -> GmailDiscoveryResult:
        profile = self.get_profile()
        current_history_id = profile.get("historyId")

        if since_history_id:
            message_ids: set[str] = set()
            page_token = None
            while True:
                response = (
                    self.service.users()
                    .history()
                    .list(
                        userId="me",
                        startHistoryId=since_history_id,
                        historyTypes=["messageAdded"],
                        pageToken=page_token,
                    )
                    .execute()
                )
                for event in response.get("history", []):
                    for added in event.get("messagesAdded", []):
                        message = added.get("message", {})
                        message_id = message.get("id")
                        if message_id:
                            message_ids.add(message_id)
                page_token = response.get("nextPageToken")
                if not page_token:
                    break
            return GmailDiscoveryResult(history_id=current_history_id, message_ids=sorted(message_ids))

        query = f"newer_than:{self.settings.gmail_initial_sync_days}d"
        response = (
            self.service.users()
            .messages()
            .list(
                userId="me",
                q=query,
                maxResults=self.settings.gmail_initial_sync_max_results,
            )
            .execute()
        )
        message_ids = [message["id"] for message in response.get("messages", []) if message.get("id")]
        return GmailDiscoveryResult(history_id=current_history_id, message_ids=message_ids)

    def get_message(self, message_id: str) -> dict:
        return self.service.users().messages().get(userId="me", id=message_id, format="full").execute()

    def get_thread(self, thread_id: str) -> dict:
        return self.service.users().threads().get(userId="me", id=thread_id, format="full").execute()

    def send_message(
        self,
        *,
        to_addresses: list[str],
        cc_addresses: list[str],
        subject: str,
        html_body: str,
        thread_id: str | None = None,
        in_reply_to: str | None = None,
        references: str | None = None,
    ) -> dict:
        message = EmailMessage()
        message["To"] = ", ".join(to_addresses)
        if cc_addresses:
            message["Cc"] = ", ".join(cc_addresses)
        message["Subject"] = subject
        if in_reply_to:
            message["In-Reply-To"] = in_reply_to
        if references:
            message["References"] = references
        message.set_content("This message contains an HTML reply.")
        message.add_alternative(html_body, subtype="html")

        payload = {
            "raw": base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8"),
        }
        if thread_id:
            payload["threadId"] = thread_id

        return self.service.users().messages().send(userId="me", body=payload).execute()
