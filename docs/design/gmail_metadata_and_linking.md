# Gmail metadata and linking

## Decision

The application should store enough stable Gmail and RFC email metadata to retrieve, thread, audit, and link back to the original Gmail message.

This is no longer considered an MVP architecture blocker. The architecture should preserve the required identifiers, while the prototype/design phase should validate the exact Gmail browser URL pattern used by the portal's `Open in Gmail` action.

## Metadata to store

- `gmail_message_id`: immutable Gmail API message id
- `gmail_thread_id`: Gmail API thread id for conversation context
- `gmail_history_id`: Gmail history marker for later synchronization and change detection
- `gmail_label_ids`: Gmail labels present at ingest time
- `gmail_internal_date`: Gmail internal received timestamp used for mailbox ordering
- `mailbox_account`: configured Gmail account identity for link construction and audit
- `rfc_message_id`: RFC `Message-ID` header for fallback search and audit
- `rfc_references`: RFC `References` header for reply/thread context
- `rfc_in_reply_to`: RFC `In-Reply-To` header for reply/thread context
- `from`, `to`, `cc`, `bcc_if_available`, `subject`, and `date` headers
- Attachment metadata, including count, filenames, MIME types, and attachment ids when available

## Portal behavior

- Show an `Open in Gmail` action on the message detail/workbench screen.
- Prefer opening the Gmail thread or message directly using stored Gmail identifiers.
- If direct linking is unreliable, provide a fallback Gmail lookup using the stored RFC `Message-ID` and human-readable sender/subject/date metadata.
- Do not rely on Gmail browser URL behavior as the only source of truth; Gmail API ids remain the canonical stored identifiers.

## Prototype validation

During prototype, verify:

- Whether a Gmail thread can be opened reliably from `gmail_thread_id`.
- Whether an individual message can be focused reliably from `gmail_message_id`.
- Whether the link works for the configured mailbox when the admin is already signed into multiple Google accounts.
- Whether the fallback lookup can locate the original message reliably from `rfc_message_id`.
- Whether attachment indicators and Gmail links are sufficient for messages with attachments in MVP.
