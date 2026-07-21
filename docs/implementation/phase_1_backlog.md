# Phase 1 Backlog

## Goal

Turn the approved MVP architecture into the first implementation sequence for the CATA email assistant.

## Delivery principles

- Build the end-to-end queue path early.
- Keep the first milestone usable without waiting for perfect drafting.
- Defer costly LLM work until the deterministic workflow, audit model, and review surface exist.
- Prefer small vertical slices over isolated infrastructure work.

## Phase 1 epics

### 1. Application foundation

- Create the Python application skeleton under `src/` using product-oriented packages.
- Add `FastAPI` app bootstrap, configuration loading, health endpoint, and local run entrypoint.
- Add database session, migration tooling, and environment config structure.
- Add a shared logging and audit helper layer.
- Add Docker packaging with `web` and `worker` entry commands.

### 2. Data model and persistence

- Create the first PostgreSQL migration set for mailbox, thread, message, participant, taxonomy, draft, and audit tables.
- Add ORM or query-layer models for the initial schema.
- Add repository/service methods for queue reads and message detail reads.
- Add S3 artifact helpers for raw snapshots and draft artifacts.

### 3. Gmail poll and ingest slice

- Convert the existing Gmail auth and read helpers into application services.
- Add mailbox configuration and poll checkpoint storage.
- Implement `Poll now` and scheduled poll entrypoints.
- Persist message threads, headers, recipients, attachment metadata, and raw snapshots.
- Add idempotent ingest behavior keyed on Gmail ids.

### 4. Queue and message workbench MVP

- Build admin login for the two launch administrators.
- Build the default queue view with status, priority, draft-state, and last-refresh behavior.
- Build the message detail page with original email, participants, attachments, Gmail link, and audit summary.
- Add admin controls for category, priority, reply-needed, informational-only, ignore, and refresh.
- Keep initial pages server-rendered and simple.

### 5. Deterministic analysis path

- Add deterministic rules for obvious routing, informational-only, and critical-priority cases.
- Persist analysis history and current message state updates.
- Add topic assignment and detected-question scaffolding, even if early logic is basic.
- Surface analysis reason summaries in the workbench.

### 6. Draft workflow baseline

- Add category response configuration records.
- Implement manual `Generate Draft` with a placeholder deterministic template path first.
- Add draft history, provenance tracking, and failure handling.
- Add final draft editing and explicit send flow through Gmail.
- Set message status to `responded` only after successful send.

### 7. Knowledge base and rule citations

- Formalize source document metadata from `data/rules_sources/sources_manifest.json`.
- Add source-document and source-chunk persistence.
- Build a first retrieval path for rule-related categories.
- Attach citations and source links in prework and draft records.

### 8. Bounded OpenAI workflow

- Add OpenAI adapters behind explicit workflow service boundaries.
- Implement category suggestion, priority suggestion, and reply-needed reasoning where deterministic logic is insufficient.
- Add prework generation before full draft generation.
- Add soft-budget and hard-cap enforcement behavior from the MVP scope.

### 9. Notifications and operations

- Add SMS notification path for `critical` messages.
- Add CloudWatch-friendly structured logs and job metrics.
- Add Secrets Manager integration and deployment environment config.
- Add operator runbooks for poll failures, draft failures, and send failures.

## Suggested milestone order

### Milestone A: Queue visibility

Target outcome:

- administrators can poll Gmail and see `new` messages in the portal with current-state persistence

Includes:

- epics 1, 2, and the ingest half of 3
- the read-only half of 4

### Milestone B: Reviewable workflow

Target outcome:

- administrators can review one message, adjust analysis fields, and mark it ignored

Includes:

- remaining work from 4
- epic 5
- audit trail basics

### Milestone C: Sendable draft path

Target outcome:

- administrators can generate, edit, and send a reply from the workbench

Includes:

- epic 6
- Gmail outbound reply flow

### Milestone D: Rule-aware assistance

Target outcome:

- rule-related messages include citations and bounded AI assistance

Includes:

- epics 7 and 8

### Milestone E: Pilot hardening

Target outcome:

- deployment, alerting, notifications, and operator support are in place for a real pilot

Includes:

- epic 9

## Recommended first coding target

Start with `Milestone A`.

It creates the fastest path to something operationally useful:

- Gmail poll
- persistent inbox records
- queue view
- message detail view

That path will validate the mailbox integration, the schema, and the portal shape before we spend effort on drafts or RAG.

## Parking lot from Milestone A validation

- Make threaded conversations more obvious in the queue.
- Add a queue hint such as thread message count or grouped conversation rows so related emails are visually connected at a glance.
- Treat the default queue as an active work list for administrators, not a full mailbox mirror.
- Hide messages sent from the monitored mailbox from the default queue because they usually represent completed work rather than new tasks.
- Preserve the ability to review older responded messages and sent-message history in secondary views, but keep them out of the default queue by default.
- Add future workbench behaviors that support task tracking, including reminders, snooze or hide-until dates, and follow-up management.
- Add a dedicated `History` screen with separate `Sent/Responded` and `Ignored` tabs.
- Make reopened messages visibly distinct in the active queue when a reply had already been sent previously.
