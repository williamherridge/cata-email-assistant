# MVP Scope

## Purpose

This document freezes the current MVP boundary for the CATA Email Assistant and separates what is approved, what still needs clarification before architecture, and what is intentionally deferred.

## MVP product intent

The MVP should let CATA administrators rely on the portal as the primary workflow for reviewing incoming Gmail messages. The system should ingest all incoming email from one Gmail mailbox, classify and prioritize messages, identify informational-only messages, generate proposed replies when appropriate, and allow administrators to review, edit, ignore, or send responses.

The MVP must preserve administrator control. Generated response drafts must never be sent automatically.

## Approved MVP decisions

### Users and access

- Use one Gmail mailbox.
- Support two administrator logins at launch.
- Give both administrators full admin capabilities.
- Use one shared work queue.
- Use separate logins for audit attribution, not assignment or ownership.
- Defer assignment, ownership, and multi-role workflow.

### Queue and status

- Message status describes administrator disposition.
- Supported MVP message statuses are `new`, `responded`, and `ignored`.
- Draft readiness is separate from message status.
- Supported draft states are `not_required`, `pending`, `ready`, and `failed`.
- Messages remain `new` while draft generation is pending or ready.
- The default queue hides `responded` messages, `ignored` messages, and sent replies.

### Priority

- Supported MVP priorities are `critical`, `normal`, and `low`.
- Priority affects queue sorting, filtering, and portal emphasis.
- `critical` can trigger SMS notification with a link to the portal message.
- The system should support adding more priority levels later without redesign.

### Taxonomy

- Seed the initial taxonomy from categories created through the taxonomy review app.
- Use category and subcategory for workflow or request type.
- Use topics for RAG retrieval, reporting, filtering, and analysis.
- Use exactly one primary category per message in MVP.
- Use zero or one subcategory per message in MVP.
- Support multiple topics per message.
- Support multiple detected questions or intents per message.
- Use topics and detected questions to handle emails that ask about multiple things.

### Proposed categories

- `assigned_category_id` references only approved taxonomy categories.
- `assigned_subcategory_id` references only approved taxonomy subcategories.
- Proposed category and subcategory labels are stored separately as free text.
- Proposed labels do not receive rules, instructions, templates, or automation until promoted.
- Administrator promotion is required before a proposed category becomes official.

### Email handling

- Ingest all email received by the single configured Gmail mailbox.
- Ingest sender, recipients, subject, body, date, thread id, message id, and recipient metadata needed for reply-all.
- Ingest stable Gmail API identifiers needed to retrieve or link back to the original email, including Gmail message id, Gmail thread id, history id, label ids, internal date, and mailbox account identity.
- Ingest RFC email headers needed for fallback lookup and reply threading, including `Message-ID`, `References`, `In-Reply-To`, `From`, `To`, `Cc`, `Subject`, and `Date`.
- Provide an `Open in Gmail` action from the portal; validate exact Gmail browser URL construction during prototype and support fallback lookup using stored identifiers.
- Ingest attachment metadata, but do not process attachment content in MVP.
- Surface attachment presence in the portal.
- Send generated response replies only after explicit administrator approval.
- Use the same Gmail account and credentials for receiving and sending.
- Mark messages `responded` when a reply is sent through the application.
- Retain sent message content and metadata in the application for audit and future improvement analysis, if cost allows.
- Evaluate low-cost object storage, such as S3, for sent message bodies and related artifacts.
- Allow administrators to mark messages `ignored` without sending a reply.

### Drafting and automation

- Generated replies must remain drafts until administrator review and send.
- Receipt replies are deferred from MVP.
- Category and priority are internal metadata and must not appear in outgoing email content unless explicitly written by an administrator.
- Category-specific drafting instructions are allowed and encouraged.
- MVP architecture must support category-level response configuration.
- Category configuration should support default draft behavior, instructions, examples, templates, RAG settings, reply-needed defaults, informational-only defaults, and priority hints.
- Supported draft behavior types should include `no_draft`, `deterministic_template`, `llm_draft`, and `hybrid`.
- Draft generation should run automatically only for categories configured to generate drafts.
- Messages in other reply-needed categories should expose a manual `Generate Draft` action.
- The system should prepare editable prework before final draft generation when cost-effective.
- Prework should include deterministic context, RAG retrieval results, citations, and a reply outline when useful.
- Prework should not require generating the final email body.
- Administrators should be able to review and edit prework before generating the formal reply.
- Full reply generation should use the current prework, including administrator edits.
- The message detail screen should provide a collaborative response workbench where the administrator and system work from the same prework and draft materials.
- Tone and signature standards should be managed through configurable system instructions.
- Initial tone should be professional, polite, direct, and concise.
- Generated replies should avoid flowery language, unnecessary reasoning, and over-explanation.
- For rule-related responses, the system should provide the applicable rule or source and avoid interpreting rules beyond the documented text.
- Deterministic rules should run before LLM calls when practical.
- Store administrator corrections and overrides for future analysis.

### Rules and RAG

- CATA will provide authoritative rule and local-parameter documentation.
- Rule precedence is national > section > local.
- Generated rule-based replies should cite relevant source links.
- Architecture should support document replacement and re-indexing workflows, likely using S3 or trusted source URLs.
- MVP authoritative regulation sources are the CATA-curated National, Section, and Local PDFs listed in `data/rules_sources/sources_manifest.json`.
- Local parameters are a launch content prerequisite and should use the same metadata/precedence model when provided.

### Cost and operations

- Initial cost target is under $20/month where feasible.
- Future budget may increase to $200-$300/month if the solution proves valuable.
- Cost is more important than instant draft generation.
- Recoverable faults caused by malformed data, stale Gmail references, unexpected user actions, or partial artifact corruption must degrade safely instead of crashing the portal.
- Draft generation should generally complete within a few minutes.
- Avoid timer-based portal auto-refresh and repeated expensive queries in MVP.
- Provide manual portal refresh and show a last refreshed timestamp.
- Refresh portal data after send actions and after draft generation completes.
- Do not automatically refresh after mark-ignored actions or category/priority changes.
- Poll every 15 minutes between 7:00 AM and 7:00 PM every day.
- Poll every 2 hours outside 7:00 AM to 7:00 PM.
- Provide an administrator-triggered `Poll now` button for immediate Gmail ingest, especially for mobile use.
- Polling intervals should remain configurable.
- Architecture should prefer low-cost storage for sent messages, drafts, prework, and audit artifacts.
- OpenAI spend should use an MVP soft budget of $10/month and a hard cap of $15-$20/month.
- When the hard cap is reached, non-essential AI draft generation should pause while Gmail ingest, deterministic rules, queue review, editing, and sending continue.
- Architecture should separate current message state from append-only audit/history records.
- MVP should retain inbound message snapshots, system analysis, RAG/prework, draft history, final sent replies, and administrator action audit events.

## MVP blockers before architecture

No unresolved MVP blockers remain before architecture.

## Design-phase questions

These do not need to block architecture, but they should be resolved during design:

- What should the admin review flow look like for accepting, editing, or dismissing proposed category labels?
- What should the admin review flow look like for reviewing and editing prework before generating a full reply?
- What exact response workbench layout best supports fast administrator review and editing?
- What default signature block should be used?
- Which categories should produce deterministic templates, LLM drafts, hybrid drafts, or no draft by default?
- Which approved categories should receive category-specific draft instructions first?
- How should the portal display draft state without confusing it with message status?
- Should topics be admin-editable in MVP?
- Should detected questions be admin-editable in MVP?
- How should citation links be displayed and edited in generated replies?
- What exact visual emphasis should `critical` messages receive?
- How should SMS notification failures be displayed?

## Deferred from MVP

- Automatic sending of generated response drafts
- Receipt replies
- Assignment or ownership workflow
- Multi-role permissions beyond full administrators
- Automatic `responded` status based on replies sent directly in Gmail
- Attachment content understanding
- Advanced analytics dashboards
- Fully automated learning from administrator corrections
- Complex workflow automation

## MVP success criteria

- Administrators can review all incoming email from one shared queue.
- The portal can be trusted as the primary inbox workflow.
- The system suggests category, priority, informational-only state, topics, and draft state.
- The system generates editable drafts for reply-needed messages where configured.
- No generated response draft can be sent without administrator approval.
- Administrators can send a reply, reply-all, or mark a message ignored.
- Responded messages, ignored messages, and sent replies are hidden from the default queue.
- Rule-based drafts include relevant citations when rule sources are used.
- The pilot stays within the initial monthly cost target.
