# Response Workbench

## Decision

The message detail screen should be a collaborative response workbench, not only a generated-reply textbox.

The workbench is where system-generated analysis and administrator judgment come together to produce the final communication.

## Workbench areas

- Original email and thread context
- Sender, recipients, reply-all metadata, attachments, and Gmail link
- System analysis: category, subcategory, priority, topics, detected questions, informational-only flag, and reply-needed state
- Editable prework: deterministic facts, RAG results, citations, source links, notes, and outline
- Draft controls: generate draft, regenerate draft, and draft provenance
- Final draft editor
- Send, reply-all, ignore, and audit information

## Drafting flow

1. The system ingests and analyzes the email.
2. The system prepares prework when useful and cost-effective.
3. The administrator reviews and edits the prework.
4. The administrator clicks `Generate Draft`, or the system generates automatically for configured categories.
5. The system generates a formal reply from the current prework.
6. The administrator edits the final draft.
7. The administrator sends, reply-alls, or marks the message ignored.

## Tone standard

Tone should be governed by configurable system instructions so it can be refined over time.

Initial standard:

- professional
- polite
- direct
- concise
- no flowery language
- no unnecessary reasoning
- no over-explanation

## Rule-response standard

For rule-related messages, the system should provide applicable rule information and citations. It should avoid interpreting rules beyond documented text.

When a response requires judgment beyond the cited rules, the system should make that visible in prework rather than inventing an interpretation.

## Design details to resolve later

- exact workbench layout
- how editable citations should appear
- whether prework changes need explicit save behavior
- how draft provenance should be displayed
- default signature block
