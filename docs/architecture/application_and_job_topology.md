# Application And Job Topology

## Goal

Define the concrete workflow boundaries for poll, ingest, analysis, prework, draft generation, send, and audit so implementation can begin with an explicit execution model.

The topology should preserve the full MVP workflow while staying compatible with the `Lean Pilot` runtime decision.

## Topology decision

Start with a same-host execution model for the pilot.

Pilot runtime shape:

- one web application process
- one lightweight background execution path on the same host
- one relational database file or instance used by both paths
- one local artifact storage area on disk
- one simple scheduler on the same host

This means the pilot does **not** require:

- a dedicated managed queue
- a separate always-on worker service
- managed scheduler infrastructure

## Design rule

Keep the **workflow boundaries** explicit even when the **runtime execution** is simple.

That means we still define poll, ingest, analysis, prework, draft, notification, and send as separate logical steps, even if some of them initially run in the same process or on the same host.

This preserves a clean path to future promotion into:

- separate worker processes
- queue-backed retries
- `SQS`
- `EventBridge Scheduler`
- containerized web and worker services

## Pilot runtime topology

The pilot should consist of:

- one `FastAPI` web application
- one background task runner on the same host
- one `SQLite` database
- one filesystem artifact root
- one host scheduler such as cron

## Execution principles

- Every logical step should have one clear responsibility.
- Steps should be idempotent where practical.
- Deterministic work should happen before LLM work.
- The portal must not block on long-running operations when that can be avoided.
- Failures should surface in workflow state instead of disappearing into logs.
- The runtime should stay cheap even if this means simpler retry mechanics at first.

## Logical workflow steps

These are logical workflow steps, not necessarily separate infrastructure services in the pilot.

### 1. Poll step

Trigger sources:

- host scheduler
- administrator `Poll now` action

Responsibilities:

- request new or changed Gmail messages since the last successful checkpoint
- register a poll run record
- create ingest work items for candidate messages
- update the mailbox checkpoint only after safe completion

Pilot execution options:

- synchronous orchestration that records pending ingest work
- lightweight background kickoff from the web app
- cron-invoked command

### 2. Message ingest step

Responsibilities:

- fetch the Gmail message payload
- normalize headers, recipients, body, and attachment metadata
- create or update the canonical message and thread records
- store raw message artifacts locally
- detect duplicate processing safely
- register follow-on analysis work when the message is new or materially changed

### 3. Message analysis step

Responsibilities:

- run deterministic screening first
- assign or suggest category, subcategory, topics, and detected questions
- assign priority and informational-only state
- decide whether a reply is needed
- decide whether prework should be prepared
- write current-state fields and append-only analysis history
- mark draft state as `not_required` when no reply is needed

### 4. Prework generation step

Responsibilities:

- gather deterministic context
- retrieve authoritative rule passages when needed
- assemble citations and source links
- prepare editable notes and outline
- write prework history and update latest pointers
- register draft generation when automatic drafting is configured

### 5. Draft generation step

Trigger sources:

- automatic category-configured drafting
- administrator `Generate Draft`
- administrator regeneration after edits

Responsibilities:

- assemble prompt context from message, analysis, category configuration, and prework
- generate the draft or use a deterministic template path
- record provenance such as `deterministic_template`, `llm_draft`, or `hybrid`
- update draft history and current draft pointers
- set draft state to `ready` or `failed`

### 6. Notification step

Responsibilities:

- send SMS only for `critical` messages that meet configured rules
- include a portal link when available
- record success or failure for administrator visibility

### 7. Send reply step

This should remain an explicit administrator-controlled action.

Responsibilities:

- lock and re-read current message state
- build the outbound Gmail reply using the approved draft and reply-all metadata
- send through Gmail
- persist sent-message metadata and artifact snapshot
- set message status to `responded`
- write append-only audit events

## Pilot execution model

### Recommended initial execution approach

Use a database-backed work-item pattern instead of a managed queue.

Recommended pilot mechanism:

- a `work_items` table or equivalent lightweight job registry
- each logical workflow step creates the next needed work item
- a same-host runner processes pending work items
- the portal can show pending, running, failed, and completed states from the database

This gives us:

- visibility into background work
- replay and retry support
- minimal infrastructure cost
- a clean later migration to `SQS`

### Why not rely only on in-memory background tasks

Pure in-memory background tasks are too fragile for this workflow because:

- process restarts can lose pending work
- retries are awkward
- administrator visibility is weak
- auditability suffers

A small database-backed work registry gives most of the value we need without the cost of managed queue infrastructure.

## Suggested pilot work item types

- `poll_mailbox`
- `ingest_message`
- `analyze_message`
- `generate_prework`
- `generate_draft`
- `send_notification`

These may all live in one table at first.

## Suggested work item states

- `pending`
- `running`
- `completed`
- `failed`
- `cancelled`

## Recommended pilot worker patterns

Any of these are acceptable for the pilot:

- a cron-triggered command that drains pending work
- a same-host long-running worker process
- a hybrid approach where cron handles polling and a worker handles downstream steps

Preferred default:

- cron for scheduled polling
- a same-host worker process for draining background work items

This keeps portal actions responsive while staying inexpensive.

## Failure handling

- Poll failures should preserve the previous successful checkpoint.
- Ingest failures should be retryable without duplicating message records.
- Analysis, prework, and draft failures should update visible workflow state.
- Draft failure should not block queue visibility.
- Administrators should be able to retry prework or draft generation from the portal.
- Worker restarts should not erase pending work.

## Idempotency expectations

- Poll runs should use a poll-run id.
- Ingest work should key on Gmail message id plus mailbox identity.
- Analysis work should key on message id plus content revision.
- Prework and draft work should key on the current source inputs so regeneration history remains explicit.
- Send actions should use a one-time approval path and store the resulting Gmail sent id.

## Local artifact layout

Recommended artifact prefix families under one root:

- `raw-messages/`
- `processed-messages/`
- `analysis/`
- `prework/`
- `drafts/`
- `sent-replies/`
- `knowledge-base/`

The directory naming should mirror the later S3 prefix strategy so migration is mechanical.

## Promotion path to managed infrastructure

If the pilot proves value, promote the same logical workflow into managed components:

- host scheduler to `EventBridge Scheduler`
- database-backed work items to `SQS`
- same-host worker to dedicated worker service
- local filesystem artifacts to `S3`
- `SQLite` to `PostgreSQL`

The application code should be written so this is an adapter swap, not a workflow redesign.

## Operational notes

- Start with modest concurrency, possibly one worker process.
- Keep work item payloads small and retrieve large context from the database or artifact storage.
- Favor recoverability and visibility over theoretical throughput.
- Measure draft latency, poll success rate, and failure counts from the start.
