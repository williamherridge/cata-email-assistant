# Runtime And Platform Decision

## Decision

Use a two-tier runtime strategy:

1. `Lean Pilot` as the default starting architecture
2. `Managed AWS Growth Path` as the upgrade target after the pilot proves value

The key design rule is:

- keep the application and data model capable of supporting the full MVP feature set
- keep the initial infrastructure as cheap and replaceable as possible

This means we do **not** optimize first for scalability, high availability, or managed-service polish. We optimize first for feature completeness, auditability, and low monthly cost.

## Why the original managed-first shape is too expensive

The earlier managed AWS stack was a reasonable technical shape, but it is too heavy for the current business question.

The current business question is not:

- how do we run a polished, scalable production service

The real question is:

- will this tool save enough administrator time and frustration to justify continued use and later investment

For that reason, the architecture should favor cheap infrastructure even when it gives up some operational conveniences.

## Lean Pilot default

### Summary

Start with one small, low-cost host running one Python application codebase.

Preferred pilot shape:

- one small VM or equivalent low-cost host
- one Python web application process
- one lightweight background job runner inside the same app or host
- `SQLite` as the default pilot database
- local filesystem storage for retained artifacts by default
- optional `S3` only if artifact handling becomes awkward locally
- host-level environment variables or a local `.env`-style deployment secret file
- cron or scheduler-based polling on the host instead of managed queue-heavy infrastructure

### Why this is the right pilot default

- It keeps monthly cost close to the original target.
- It still supports the full product workflow.
- It avoids spending most of the budget on infrastructure before the product is validated.
- It makes it easier to change hosting direction later without feeling locked into AWS-specific services.

### Lean Pilot service choices

- application runtime: `FastAPI`
- portal rendering: server-rendered templates with light JavaScript
- database: `SQLite`
- scheduler: host cron or equivalent simple scheduler
- background execution: in-process queue, database-backed job table, or same-host worker process
- artifact storage: local filesystem first
- logs: application logs written to the host and rotated simply

### Lean Pilot tradeoffs

This approach intentionally accepts:

- no managed high availability
- manual backup and restore planning
- lower operational resilience
- simpler secret handling
- less elasticity

Those are acceptable tradeoffs for the pilot as long as:

- no email is auto-sent
- audit history is preserved
- backups are good enough for pilot protection
- the system can be migrated forward cleanly

## Managed AWS growth path

Once the pilot proves value, move to a managed AWS stack that preserves the same application boundaries.

Preferred managed path:

- `Amazon ECS Express Mode` or full `ECS on Fargate`
- `Amazon RDS PostgreSQL`
- `Amazon S3`
- `Amazon SQS`
- `Amazon EventBridge Scheduler`
- `AWS Secrets Manager`
- `Amazon CloudWatch`

This should be treated as the upgrade target, not the day-one default.

## Decision table

| Area | Lean Pilot default | Managed growth path |
|---|---|---|
| App hosting | One small host | `ECS Express Mode` or `ECS/Fargate` |
| Database | `SQLite` | `RDS PostgreSQL` |
| Background jobs | In-process or same-host worker | `SQS` + worker service |
| Scheduling | Host cron | `EventBridge Scheduler` |
| Artifact storage | Local disk | `S3` |
| Secrets | Host env vars / local secret file | `Secrets Manager` |
| Logging | Host logs | `CloudWatch` |
| Cost posture | Optimize for `$10-$20/month` pilot | Optimize for durability and scale |

## Portal framework and packaging choice

Use `FastAPI` as the application framework with server-rendered HTML templates for the admin portal.

Recommended packaging approach:

- `FastAPI` for HTTP routes, auth/session endpoints, and admin actions
- `Jinja` templates for server-rendered portal pages
- light client-side JavaScript only where needed for queue refresh, polling progress, and workbench interactions
- one Python package tree under `src/` for portal, workflow, Gmail integration, knowledge retrieval, and audit services
- one deployable Python application that can run either:
  - as a single-process pilot deployment
  - or as split `web` and `worker` runtimes later

## Why this portal approach fits MVP

- The current repo is already Python-first.
- The MVP is an internal admin tool, not a public marketing site.
- Server-rendered pages reduce frontend build complexity and deployment surface.
- Most screens are workflow-heavy forms and tables, which fit server rendering well.
- We can still add targeted JavaScript where the response workbench benefits from it.

## Application packaging rules

- Keep one deployable repository and one application image for the MVP.
- Split code by product boundary, not by deployment target.
- Expose separate runtime commands for `web`, `worker`, and one-off administrative tasks.
- Keep prompt/config manifests and category instructions in version-controlled files where practical.
- Keep infrastructure adapters thin so `SQLite` can be replaced by PostgreSQL and local storage can be replaced by S3 later.

Recommended near-term package layout:

- `src/admin_portal/`
- `src/gmail_integration/`
- `src/message_processing/`
- `src/knowledge_base/`
- `src/notifications/`
- `src/taxonomy/`
- `src/workflow/`
- `src/common/`

## Lean Pilot deployment shape

### Web application

Responsibilities:

- administrator login
- queue view
- message detail and response workbench
- send, ignore, regenerate, and poll-now actions
- read APIs needed by the portal

### Background execution

Responsibilities:

- run scheduled poll tasks
- run ingest, analysis, prework, and draft workflows
- write artifacts and audit events
- dispatch SMS notifications when rules require it

Implementation note:

- begin with same-host execution or a simple same-host worker process
- do not require a managed queue in the pilot unless reliability problems force it

### Scheduler

Responsibilities:

- trigger the Gmail poll cadence
- support the approved day/night polling intervals
- remain configurable without code redesign

Implementation note:

- start with host cron or an application scheduler
- keep the polling service boundary explicit so it can later move behind EventBridge

## Cost stance

This choice intentionally optimizes for learning whether the product is worth keeping.

The main cost controls remain:

- one host
- one codebase
- `SQLite` first
- local artifact storage first
- bounded LLM usage
- minimal always-on infrastructure

## Revisit triggers

Revisit this decision if:

- the pilot proves strong enough value to justify higher monthly spend
- local storage and backup management become painful
- concurrent admin activity reveals locking or reliability issues
- `SQLite` becomes a genuine bottleneck
- background jobs need stronger isolation and retry behavior
- infrastructure risk starts to outweigh cost savings
