# MVP Architecture Baseline

## Purpose

This document defines the initial target architecture for the CATA Email Assistant MVP so the repository can enter the architecture phase with a concrete technical direction.

The architecture favors:

- low monthly operating cost
- explicit administrator control
- auditable workflows
- incremental delivery from the current exploratory codebase

## Architectural stance

The MVP should be a workflow-driven web application, not an autonomous agent.

Core principles:

- Gmail ingest, classification, drafting, review, and send should be modeled as explicit state transitions.
- Deterministic rules should run before LLM calls whenever practical.
- No component may send email without an explicit administrator action.
- Expensive AI steps should be optional, observable, and budget-constrained.
- Current message state should be separated from append-only audit history.

## System context

Primary external systems:

- Gmail API for inbound message retrieval and approved outbound replies
- OpenAI API for bounded classification, prioritization, prework, and draft generation
- AWS for hosting, storage, scheduling, and operational services
- Twilio or equivalent SMS provider for critical-priority notifications

Primary human actors:

- CATA administrator 1
- CATA administrator 2

High-level flow:

1. A scheduled poll or admin-triggered poll retrieves new Gmail messages.
2. The system stores normalized message data and raw snapshots.
3. A processing workflow applies deterministic rules, then LLM-assisted analysis only when needed.
4. The portal shows the work queue and message workbench.
5. Administrators review results, edit prework and drafts, and explicitly send or ignore messages.
6. Every meaningful action is written to an audit trail.

## Recommended MVP deployment shape

Use a small AWS-hosted monolith for the application layer, with background jobs for polling and draft generation.

Recommended logical components:

- web application
- workflow/job workers
- relational application database
- object storage for large artifacts
- scheduled poll trigger
- budget and audit monitoring

This keeps the system simple enough for the first deployment while preserving clear boundaries for later decomposition.

## AWS service selection

Recommended MVP services:

- `AWS App Runner` or `ECS Fargate` for the web application and worker runtime
- `Amazon RDS PostgreSQL` for operational state
- `Amazon S3` for raw message snapshots, draft/prework artifacts, sent-message artifacts, and source documents
- `Amazon EventBridge Scheduler` for Gmail polling cadence
- `Amazon SQS` for background job dispatch
- `Amazon CloudWatch` for logs, alarms, and budget-related operational signals
- `AWS Secrets Manager` for Gmail OAuth material, app secrets, and provider credentials

Preferred default:

- Start with one deployable Python application image.
- Run the web process and worker process from the same codebase.
- Use managed services instead of self-hosted infrastructure wherever possible.

## Application components

### 1. Gmail integration

Responsibilities:

- poll the configured Gmail mailbox
- fetch message metadata and content
- preserve Gmail identifiers and RFC headers
- send approved replies using the same mailbox
- support reply-all behavior using stored recipient metadata

Boundaries:

- no automatic outbound send in MVP
- no attachment-content understanding in MVP
- ingest attachment metadata only

### 2. Message processing workflow

Responsibilities:

- normalize message bodies and headers
- de-duplicate and merge thread context
- apply deterministic rules
- assign category, subcategory, topics, and detected questions
- assign priority and informational-only state
- decide whether reply prework or draft generation is needed

This layer should be implemented as small, inspectable steps rather than one large prompt.

### 3. Knowledge and RAG layer

Responsibilities:

- store authoritative rule-source metadata
- extract and chunk approved source documents
- retrieve relevant passages for rule-related drafting
- attach citations with precedence-aware metadata

The authoritative source hierarchy remains:

1. National
2. Section
3. Local
4. Local parameters

### 4. Response workbench

Responsibilities:

- present original email and thread context
- show system analysis and confidence
- expose editable prework
- support draft generation and regeneration
- support final draft editing and send
- support ignore and audit review

This should be the primary administrator working surface for MVP.

### 5. Audit and history

Responsibilities:

- record inbound snapshots
- record system analysis outputs
- record prework and draft versions
- record administrator actions and final sends
- preserve timestamps and actor identity

Audit records should be append-only even when current message state changes.

## Data architecture

### Operational database

Use PostgreSQL as the system of record for current application state.

Core entity groups:

- users
- messages
- message_threads
- message_analysis
- draft_state
- taxonomy entities
- notifications
- audit_events

Recommended modeling rules:

- keep current message status on the main message record
- keep draft readiness separate from message status
- store assigned taxonomy ids separately from proposed free-text labels
- store references to artifact blobs in S3 instead of large payloads directly in the database when practical

### Object storage

Use S3 for artifact classes that are large, versioned, or helpful to retain cheaply:

- raw inbound message snapshots
- processed message snapshots
- prework payloads
- draft history payloads
- final sent reply artifacts
- source documents and extracted chunks

## Workflow model

Recommended message lifecycle:

1. `ingested`
2. `analyzed`
3. `prework_ready` when applicable
4. `draft_ready` or `draft_failed`
5. administrator review
6. `responded` or `ignored`

Administrator-facing disposition must still use the approved MVP statuses:

- `new`
- `responded`
- `ignored`

Implementation note:

- internal workflow step markers can be more detailed than the portal-visible status model

## OpenAI integration pattern

Use OpenAI as a bounded service within workflow steps.

Recommended AI task types:

- category suggestion when deterministic rules do not settle the result
- priority suggestion when semantics matter
- reply-needed and informational-only reasoning
- prework preparation
- final draft generation

Guardrails:

- never let a model call decide whether to send
- prefer smaller prompts routed by category or task
- persist prompt inputs and outputs needed for audit and debugging
- enforce monthly cost caps and per-step usage policies
- pause non-essential generation when the hard budget cap is reached

## Security and identity

Recommended MVP identity stance:

- separate administrator logins for the two launch users
- application-level authentication with passwordless or managed identity later if needed
- authorization can remain simple full-admin access in MVP

Security controls:

- store secrets only in local ignored files for development and Secrets Manager in hosted environments
- encrypt database and S3 storage at rest
- use HTTPS-only access to the portal
- log administrative actions with actor identity
- avoid exposing internal model metadata in outbound replies

## Scheduling and background jobs

Polling cadence should match the approved MVP requirement:

- every 15 minutes from 7:00 AM to 7:00 PM
- every 2 hours outside that window
- administrator-triggered `Poll now` support in the portal

Background jobs are recommended for:

- Gmail polling
- message processing
- prework generation
- draft generation
- source re-indexing after administrator approval
- critical SMS notification dispatch

## Cost strategy

The architecture should optimize for predictable low cost.

Cost controls:

- use scheduled polling instead of always-on inbox streaming for MVP
- keep the application mostly idle outside request and job activity
- run deterministic rules before model calls
- generate drafts automatically only for selected categories
- store large artifacts in S3 instead of the database
- track OpenAI usage against the approved soft and hard monthly caps

## Delivery guidance from the current repo

To move safely from the current exploratory repository into implementation:

- keep existing ingestion and analytics utilities as reference modules
- add new product code in purpose-based packages under `src/`
- treat the taxonomy review app as a supporting utility, not the main application shell
- evolve toward `src/admin_portal/`, `src/workflow/`, `src/knowledge_base/`, and `src/message_processing/`

## Architecture decisions now considered settled

- workflow-first architecture instead of agent-first
- one Gmail mailbox for MVP
- two full-admin users for launch
- explicit no-auto-send rule
- PostgreSQL plus S3 storage split
- AWS-managed hosting and scheduling
- bounded OpenAI usage inside specific workflow steps

## Architecture decisions still to finalize during design

- App Runner versus ECS Fargate as the first hosting target
- exact admin authentication mechanism
- exact portal framework and server-side application structure
- final schema for audit, prework, and draft versioning
- SMS provider selection
- source-document chunking and citation rendering details
