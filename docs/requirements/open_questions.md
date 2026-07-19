# Open Questions

These questions should be resolved during the requirements phase before architecture is finalized.

## Current decisions

- The MVP will target one Gmail mailbox.
- The initial taxonomy will come from categories created with the taxonomy review app.
- The launch user base is likely two administrators with full admin capabilities.
- Application audit logs must track actions by user.
- The portal must be reliable enough that administrators can use it as the primary workflow for all incoming email.
- Cost is more important than instant draft generation, but draft responses should usually complete within a few minutes.
- Attachments do not need content processing in MVP, but attachment metadata should be visible.
- CATA will provide authoritative rule and local-parameter documentation.
- Message status will describe administrator disposition: `new`, `responded`, and `ignored`.
- Draft readiness will be tracked separately from message status.
- MVP priority levels will be `critical`, `normal`, and `low`.
- Priority will drive queue sorting, filtering, visual attention, and critical SMS notification.
- Receipt replies are deferred from MVP until administrators build confidence in category and priority accuracy.
- Administrator workflow will use one shared queue.
- Separate administrator logins exist for audit attribution, not assignment or ownership.
- Taxonomy shape will use category and subcategory for workflow, plus topics for RAG retrieval, reporting, and analysis.
- MVP uses exactly one primary category and zero or one subcategory per message.
- Multiple topics and detected questions or intents will handle emails that ask about more than one thing.
- Assigned category and subcategory fields will reference only approved taxonomy records.
- Proposed category and subcategory labels will be stored separately until administrator promotion.
- Rules, instructions, and templates will attach only to approved taxonomy categories.
- Drafts will be generated automatically only for categories configured to do so.
- Other reply-needed messages will provide a manual `Generate Draft` action.
- Editable prework may be prepared before final draft generation.
- Prework can include deterministic context, RAG retrieval results, citations, and a reply outline.
- Full reply generation will use the current prework, including administrator edits.
- Message detail should include a collaborative response workbench for system prework and administrator edits.
- Tone should be configurable through system instructions.
- Initial tone should be professional, polite, direct, and concise.
- Rule-related replies should provide applicable rules and citations without undocumented interpretation.
- Sent message content and metadata should be retained in the application for audit and future improvement analysis, if cost allows.
- Architecture should evaluate low-cost object storage, such as S3, for sent message bodies and related artifacts.

## Taxonomy

- What should the admin review flow look like for accepting, editing, or dismissing proposed category labels?

## Reply generation

- Which existing taxonomy categories should have deterministic handling rules?
- Which existing taxonomy categories should have category-specific draft instructions?
- Are there standard templates or signature blocks that must always appear?
- What default signature block should be used?
- What should the admin review flow look like for editing prework before generating a full reply?
- Which categories should produce no draft by default?
- After the MVP confidence period, which categories can produce a receipt reply?

## Rules and knowledge base

- Answered: MVP authoritative regulation sources are the CATA-curated National, Section, and Local PDFs listed in `data/rules_sources/sources_manifest.json`.
- How often do these sources change?
- Which local operational parameters change most often and need structured storage?
- Are there cases where operational guidance is authoritative even if not documented in a formal rule source?
- Should rule updates be fully automatic when documents change, or require admin approval before re-indexing?
- Should trusted source URLs be polled for changes, or should CATA replace source files in an S3 bucket?

## Integrations and operations

- Do you want the first production deployment to be internet-accessible immediately, or behind a smaller pilot access model?
- Should direct replies sent from Gmail mark the application message as `responded` in a post-MVP phase?
- Which SMS provider should be used for critical priority notifications?

## Cost and scale

- Roughly how many new emails arrive per day and per week?
- What percentage typically need a reply?
- How many rule-related questions arrive in a typical week?
- Answered: OpenAI MVP spend should use a $10/month soft budget and a $15-$20/month hard cap; non-essential AI drafting pauses at the hard cap.
- Should draft generation be automatic for all reply-needed emails, or only for selected categories at first?

## Governance

- Answered: MVP should audit administrator actions and retain inbound message snapshots, system analysis, RAG/prework, draft history, final sent replies, and sent/action metadata.
- Answered: architecture should separate current message state from append-only audit/history records.
- Who approves taxonomy changes and rule-source updates?
