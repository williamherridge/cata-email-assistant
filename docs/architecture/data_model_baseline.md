# Data Model Baseline

## Goal

Define the initial relational model for the MVP so application code, migrations, and audit behavior can begin from a stable baseline.

## Modeling stance

- The lean pilot should start with `SQLite` as the default system of record.
- The same relational model should remain portable to PostgreSQL when the pilot is promoted.
- Local filesystem storage should be the default pilot artifact store.
- S3 remains the growth-path artifact store for large retained payloads.
- Current-state tables power the portal.
- Append-only history tables preserve what happened.
- Official taxonomy ids stay separate from free-text proposed labels.

## Pilot-first schema stance

The schema should be read in two layers:

- `pilot required`: needed for the first real end-to-end vertical slice
- `planned growth`: valuable for the full MVP, but not required to prove the workflow

We should preserve forward-looking tables in the design, but implementation should start with the smallest set that supports:

- Gmail poll
- message persistence
- queue visibility
- message detail
- lightweight background execution
- auditability for meaningful actions

## Core table groups

### Identity and access

#### `users`

- `id`
- `email`
- `display_name`
- `role`
- `is_active`
- `created_at`
- `updated_at`

MVP note:

- start with two full administrators

### Gmail integration

#### `mailboxes`

- `id`
- `gmail_address`
- `display_name`
- `gmail_profile_id`
- `last_successful_history_id`
- `last_polled_at`
- `is_active`
- `created_at`
- `updated_at`

#### `poll_runs`

- `id`
- `mailbox_id`
- `trigger_source`
- `started_at`
- `completed_at`
- `status`
- `history_id_start`
- `history_id_end`
- `messages_discovered`
- `messages_enqueued`
- `error_summary`

#### `work_items`

- `id`
- `work_type`
- `status`
- `mailbox_id`
- `message_id`
- `poll_run_id`
- `scheduled_for`
- `attempt_count`
- `max_attempts`
- `lease_token`
- `lease_expires_at`
- `payload_json`
- `error_summary`
- `created_at`
- `started_at`
- `completed_at`

Pilot note:

- this is the lean-pilot replacement for a managed queue
- one table can support poll, ingest, analysis, prework, draft, and notification work

#### `message_threads`

- `id`
- `mailbox_id`
- `gmail_thread_id`
- `subject_canonical`
- `latest_message_received_at`
- `latest_message_id`
- `created_at`
- `updated_at`

#### `messages`

- `id`
- `mailbox_id`
- `thread_id`
- `gmail_message_id`
- `gmail_history_id`
- `rfc_message_id`
- `gmail_internal_date`
- `from_display`
- `from_address`
- `subject`
- `snippet`
- `received_at`
- `has_attachments`
- `status`
- `draft_state`
- `priority`
- `informational_only`
- `reply_needed`
- `assigned_category_id`
- `assigned_subcategory_id`
- `proposed_category_label`
- `proposed_subcategory_label`
- `latest_analysis_id`
- `latest_prework_id`
- `latest_draft_id`
- `latest_sent_reply_id`
- `opened_in_portal_at`
- `responded_at`
- `ignored_at`
- `created_at`
- `updated_at`

Portal filters and sorting should primarily use this table.

#### `message_participants`

- `id`
- `message_id`
- `participant_type`
- `display_name`
- `email_address`
- `position_index`

`participant_type` should support `from`, `to`, `cc`, and `bcc` if available.

#### `message_headers`

- `id`
- `message_id`
- `header_name`
- `header_value`

Store the RFC headers needed for reply threading and fallback Gmail linking.

#### `message_attachments`

- `id`
- `message_id`
- `gmail_attachment_id`
- `filename`
- `mime_type`
- `size_bytes`
- `is_inline`

#### `message_artifacts`

- `id`
- `message_id`
- `artifact_type`
- `storage_uri`
- `content_sha256`
- `created_at`

Use for raw and processed message snapshots stored in local artifact storage first, then S3 later if promoted.

### Taxonomy and configuration

#### `categories`

- `id`
- `name`
- `description`
- `is_active`
- `default_draft_behavior`
- `default_reply_needed`
- `default_informational_only`
- `priority_hint`
- `created_at`
- `updated_at`

#### `subcategories`

- `id`
- `category_id`
- `name`
- `description`
- `is_active`
- `created_at`
- `updated_at`

#### `topics`

- `id`
- `name`
- `description`
- `is_active`
- `created_at`
- `updated_at`

#### `message_topics`

- `message_id`
- `topic_id`

#### `detected_questions`

- `id`
- `message_id`
- `question_text`
- `position_index`
- `source_type`
- `created_at`

#### `category_response_configs`

- `id`
- `category_id`
- `is_active`
- `draft_behavior`
- `auto_generate_draft`
- `instructions_version`
- `template_key`
- `rag_mode`
- `reply_needed_default`
- `informational_only_default`
- `priority_hint`
- `created_at`
- `updated_at`

### Analysis, prework, and drafts

#### `message_analyses`

- `id`
- `message_id`
- `analysis_version`
- `analysis_source`
- `model_name`
- `prompt_version`
- `deterministic_rule_hits`
- `assigned_category_id`
- `assigned_subcategory_id`
- `proposed_category_label`
- `proposed_subcategory_label`
- `priority`
- `informational_only`
- `reply_needed`
- `confidence_tier`
- `reason_summary`
- `created_at`
- `created_by_user_id`

#### `analysis_topics`

- `analysis_id`
- `topic_id`

#### `analysis_artifacts`

- `id`
- `analysis_id`
- `artifact_type`
- `storage_uri`
- `created_at`

#### `prework_records`

- `id`
- `message_id`
- `source_analysis_id`
- `status`
- `retrieval_mode`
- `outline_text`
- `admin_notes`
- `artifact_uri`
- `created_at`
- `created_by_user_id`

#### `prework_citations`

- `id`
- `prework_id`
- `source_document_id`
- `source_chunk_id`
- `citation_label`
- `source_url`
- `excerpt_text`
- `precedence_rank`
- `position_index`

#### `draft_records`

- `id`
- `message_id`
- `source_analysis_id`
- `source_prework_id`
- `draft_version`
- `draft_state`
- `provenance`
- `subject_line`
- `body_text`
- `artifact_uri`
- `generation_error`
- `created_at`
- `created_by_user_id`

### Knowledge base

#### `source_documents`

- `id`
- `source_scope`
- `title`
- `version_label`
- `effective_date`
- `source_url`
- `storage_uri`
- `is_active`
- `precedence_rank`
- `created_at`
- `updated_at`

#### `source_chunks`

- `id`
- `source_document_id`
- `chunk_key`
- `section_label`
- `chunk_text`
- `token_estimate`
- `embedding_ref`
- `created_at`

MVP note:

- embedding storage can remain simple at first and may stay outside PostgreSQL if we use a lightweight retrieval approach

### Outbound replies and notifications

#### `sent_replies`

- `id`
- `message_id`
- `draft_id`
- `gmail_sent_message_id`
- `gmail_thread_id`
- `sent_to`
- `sent_cc`
- `subject_line`
- `body_text`
- `sent_at`
- `sent_by_user_id`
- `artifact_uri`

#### `notification_events`

- `id`
- `message_id`
- `channel`
- `destination_masked`
- `event_type`
- `status`
- `provider_message_id`
- `error_summary`
- `created_at`

### Audit and event history

#### `audit_events`

- `id`
- `message_id`
- `actor_type`
- `actor_user_id`
- `event_type`
- `target_table`
- `target_id`
- `summary`
- `before_json`
- `after_json`
- `created_at`

## Key enum families

- message `status`: `new`, `responded`, `ignored`
- message `draft_state`: `not_required`, `pending`, `ready`, `failed`
- `priority`: `critical`, `normal`, `low`
- draft `provenance`: `deterministic_template`, `llm_draft`, `hybrid`, `manual_only`
- poll `trigger_source`: `scheduler`, `admin`

## Current-state versus history pattern

Use this rule consistently:

- `messages` stores the latest portal-visible workflow state
- `work_items` stores lean-pilot background execution state
- `message_analyses`, `prework_records`, `draft_records`, `sent_replies`, and `audit_events` preserve history

The current message should point to the latest applicable history rows so queue reads remain simple.

## Pilot-required tables

These are the tables we should treat as the initial implementation baseline for `Milestone A`.

### Required for first vertical slice

- `users`
- `mailboxes`
- `poll_runs`
- `work_items`
- `message_threads`
- `messages`
- `message_participants`
- `message_headers`
- `message_attachments`
- `message_artifacts`
- `audit_events`

### Recommended early if low effort

- `categories`
- `subcategories`
- `topics`
- `message_topics`
- `message_analyses`

These help us avoid repainting the house immediately after the first queue view exists.

## Planned-growth tables

These remain part of the target MVP model, but they do not need to block the first implementation slice.

- `detected_questions`
- `category_response_configs`
- `analysis_topics`
- `analysis_artifacts`
- `prework_records`
- `prework_citations`
- `draft_records`
- `source_documents`
- `source_chunks`
- `sent_replies`
- `notification_events`

## Pilot migration priority

The first database migration set should create these tables first:

1. `users`
2. `mailboxes`
3. `poll_runs`
4. `work_items`
5. `message_threads`
6. `messages`
7. `message_participants`
8. `message_headers`
9. `message_attachments`
10. `message_artifacts`
11. `audit_events`

Second migration set:

1. `categories`
2. `subcategories`
3. `topics`
4. `message_topics`
5. `message_analyses`

Third migration set:

1. `category_response_configs`
2. `detected_questions`
3. `analysis_topics`
4. `analysis_artifacts`
5. `prework_records`
6. `prework_citations`
7. `draft_records`
8. `source_documents`
9. `source_chunks`
10. `sent_replies`
11. `notification_events`
