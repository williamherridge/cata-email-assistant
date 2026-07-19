# Audit and Retention Model

## Decision

MVP architecture should separate current message state from append-only audit and history records.

Current state powers the portal. Append-only records preserve what happened, who did it, and what changed.

## Current message state

Current state should support fast queue and message-detail views:

- Message status: `new`, `responded`, or `ignored`.
- Assigned category and proposed category label.
- Subcategory, topics, detected questions, priority, and informational-only flag.
- Draft readiness state.
- Latest prework and latest draft pointers.
- Gmail message/thread identifiers.

## Retained records

MVP should retain:

- Inbound message snapshots, including Gmail ids, headers, recipients, subject, body, received time, and attachment metadata.
- System analysis, including category, priority, informational-only flag, topics, confidence, model, prompt version, and rule versions where applicable.
- RAG/prework, including retrieved rule chunks, source citations, generated notes, outline, and administrator edits.
- Draft history, including generated drafts, regenerated drafts, admin-edited drafts, and final approved draft.
- Final sent replies, including body, recipients, timestamp, Gmail sent message id, and Gmail thread id.
- Administrator action events, including user, action, timestamp, target record, previous value, and new value where applicable.

## Actions to audit

Audit events should be recorded for:

- Category, subcategory, topic, priority, and informational-only changes.
- Proposed category approval, dismissal, or promotion to official taxonomy.
- Prework edits.
- Draft generation and regeneration.
- Draft edits.
- Send reply and reply-all.
- Mark ignored.
- Source document add, replacement, activation, deactivation, and re-index.
- Category instructions, templates, and prompt configuration changes.

## Retention approach

- Keep structured metadata and audit events durably during MVP.
- Prefer low-cost object storage for larger message bodies, drafts, prework snapshots, sent replies, and extracted source artifacts.
- Do not delete retained records automatically during MVP.
- Preserve enough history to compare system-generated output with administrator-approved final communication.

## Architecture implications

- Use a mutable current-state record for portal workflow.
- Use append-only event/history records for audit and future improvement analysis.
- Store enough user attribution to distinguish the two administrator logins.
- Keep audit and history writes independent of UI filtering so hidden messages remain recoverable.
