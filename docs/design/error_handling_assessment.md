# Error Handling Assessment

## Purpose

This document captures the July 21, 2026 error-handling assessment for the current pilot codebase, the minimum resilience standard for future work, and the hardening actions applied in this pass.

## Target standard

For normal software faults, malformed data, stale external references, unexpected user interactions, partial artifact corruption, and recoverable third-party API issues, the application should degrade safely and remain usable.

The application may still fail an individual operation when a physical dependency is unavailable, including:

- the SQLite database file or database engine
- the local filesystem used for artifacts
- the Gmail API or OAuth infrastructure

Even in those cases, the preferred behavior is:

- fail the smallest possible unit of work
- preserve auditability when feasible
- avoid taking down unrelated screens or the full process

## Current grade

- Overall grade before this hardening pass: `C`
- Overall grade after this hardening pass: `B-`

The app already had some strong foundations:

- explicit status models
- audit events for key workflow actions
- a pilot architecture that keeps logic centralized
- some defensive handling around Gmail send permissions and missing Gmail messages

The biggest weaknesses were:

- request handlers that still allowed unhandled exceptions to become 500 crashes
- per-message poll work that could fail the entire poll on malformed data
- file and artifact reads that assumed local data was always valid
- configuration/catalog parsing that could break primary screens
- inconsistent rollback behavior after exceptions

## Module-by-module assessment

### `src/admin_portal/main.py`

- Grade before: `C-`
- Main problems:
  - queue/history/detail routes could crash on taxonomy, artifact, or query failures
  - POST actions relied on happy-path workflow calls and often returned raw failures
  - no global unhandled exception experience for browser users
- Actions taken:
  - added a global exception handler with a controlled error screen
  - added guarded route-level fallbacks for queue, history, poll runs, and message detail
  - added safe redirects and user-facing error banners for POST actions
  - added rollback hygiene for caught route exceptions

### `src/shared/database.py`

- Grade before: `C`
- Main problems:
  - request-scoped sessions closed cleanly, but did not automatically rollback on unhandled exceptions
- Actions taken:
  - rollback now occurs before re-raising unhandled request errors

### `src/workflow/polling.py`

- Grade before: `C`
- Main problems:
  - malformed work item payloads could crash polling
  - malformed Gmail payloads could fail the full poll
  - body artifact reads could raise file and decoding errors into the UI
  - message-open tracking could fail page rendering
  - taxonomy/mailbox discovery failures were partially swallowed but not logged
- Actions taken:
  - invalid ingest work items now fail individually with audit trail entries
  - malformed Gmail payloads now fail the single work item instead of the full poll
  - missing Gmail messages already skipped are now covered by regression tests
  - deterministic analysis now fails the single work item instead of crashing the poll
  - body and HTML artifact reads now fail closed and log safely
  - form parsing now tolerates unexpected encoding
  - message-open tracking and mailbox auto-discovery now rollback/log safely

### `src/workflow/taxonomy.py`

- Grade before: `D+`
- Main problems:
  - malformed taxonomy catalog JSON could break queue/history loads
- Actions taken:
  - taxonomy catalog loading now logs and no-ops on invalid content instead of crashing the portal

### `src/gmail_ingest/parsing.py`

- Grade before: `C`
- Main problems:
  - malformed base64 payloads could raise during body decode
  - malformed Gmail headers could raise `KeyError`
- Actions taken:
  - decode now returns empty text for invalid base64
  - header normalization now ignores malformed header entries

### Utility scripts

- Scope reviewed:
  - `src/gmail_ingest/export_messages.py`
  - `src/gmail_ingest/rebuild_thread_index.py`
  - `src/email_cleaning/process_messages.py`
- Grade: `C`
- Notes:
  - these scripts are not part of the live portal request path
  - they already skip some malformed files, but still rely heavily on local filesystem and happy-path API calls
  - they should be hardened in a future CLI resilience pass, but they were not the highest-risk production-like crash paths for this round

## Findings and recommendations

### Critical findings

1. Request handlers were too close to raw workflow exceptions.
   - Impact: one bad artifact, taxonomy file, or unexpected workflow error could produce a full 500 response.
   - Recommendation: treat routes as resilience boundaries. Catch, rollback, log, and return a controlled browser experience.

2. Polling still had whole-run failure paths caused by one bad message record.
   - Impact: malformed Gmail payloads or invalid work item payloads could stop `Poll Now`.
   - Recommendation: isolate polling at the individual work-item level whenever the database itself remains healthy.

### High findings

3. Artifact reads assumed valid files and valid UTF-8 content.
   - Impact: a missing/corrupt artifact could break queue/history/detail rendering.
   - Recommendation: all artifact reads should fail closed and log.

4. Taxonomy file parsing was not safe enough for a user-facing dependency.
   - Impact: malformed JSON in a local catalog file could break queue and history.
   - Recommendation: treat local data catalogs as untrusted input and no-op with logging when invalid.

5. Session rollback behavior was inconsistent after caught exceptions.
   - Impact: later actions in the same request could run against a dirty session state.
   - Recommendation: every caught route exception must explicitly rollback before redirecting or rendering a fallback.

### Medium findings

6. Some helper functions still use broad exception swallowing without structured logging.
   - Impact: the app survives, but diagnosis is harder.
   - Recommendation: swallowing is acceptable only when paired with logging and a deliberate fallback.

7. Physical dependency failures are still not uniformly translated into user-facing messaging.
   - Impact: some database/filesystem failures may still surface as generic error pages.
   - Recommendation: future work should standardize domain exceptions for storage, Gmail, and database failures.

## Hardening changes applied in this pass

- Added request-scoped rollback in `src/shared/database.py`
- Added safer Gmail payload decode and header normalization in `src/gmail_ingest/parsing.py`
- Added guarded taxonomy loading in `src/workflow/taxonomy.py`
- Added logging and safe rollback behavior for mailbox discovery and message-open tracking in `src/workflow/polling.py`
- Added work-item failure handling for:
  - invalid ingest payloads
  - malformed Gmail message payloads
  - deterministic analysis failures
- Added safe artifact reads for text and HTML body artifacts
- Added tolerant form-body decoding
- Added guarded route handling and user-safe error flows in `src/admin_portal/main.py`
- Added a generic error page template

## New regression coverage

- invalid taxonomy catalog does not crash sync
- malformed Gmail message payload does not crash polling
- invalid review submission does not crash the portal and returns a controlled message
- stale Gmail message id regression remains covered

## Residual risks

- A true database outage can still fail whole requests or polling runs
- Filesystem write failures during ingest/send may still fail the current operation
- CLI/export utilities still need a dedicated resilience pass
- Gmail browser deep-link behavior still needs a separate validation/fallback improvement pass

## Future engineering rules

All future code should follow these rules:

1. Every request boundary must return a controlled response for recoverable faults.
2. Every background or batch loop must isolate failures to the smallest safe work unit.
3. All local file reads must assume corruption, absence, and decoding problems are possible.
4. All third-party payload parsing must assume malformed or incomplete structures.
5. All caught exceptions must either:
   - rollback and re-raise, or
   - rollback/log and return a deliberate fallback
6. Broad `except Exception` is allowed only at resilience boundaries, never as silent business logic.
7. New user-facing features must define:
   - what happens on validation failure
   - what happens on stale/missing data
   - what happens on Gmail/API failure
   - what happens on artifact read/write failure
