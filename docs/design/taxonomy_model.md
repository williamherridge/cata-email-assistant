# Taxonomy Model

## Decision

Use category and subcategory for workflow. Use topics for subject matter, retrieval, reporting, and future analysis.

## Classification fields

- `category`: the primary workflow or request type
- `subcategory`: an optional refinement under category
- `assigned_category_id`: a reference to an approved category record
- `assigned_subcategory_id`: an optional reference to an approved subcategory record
- `proposed_category_label`: optional free-text category suggestion
- `proposed_subcategory_label`: optional free-text subcategory suggestion
- `topics`: one or more subject-matter labels
- `detected_questions`: one or more questions, intents, or issues found in the message

## Cardinality

- MVP uses exactly one primary category per message.
- MVP uses zero or one subcategory per message.
- MVP supports multiple topics per message.
- MVP supports multiple detected questions or intents per message.

## Proposed category handling

- `assigned_category_id` must reference an approved category.
- `assigned_subcategory_id` must reference an approved subcategory when present.
- Proposed category and subcategory labels remain free text until administrator promotion.
- Proposed labels do not receive rules, instructions, templates, or receipt-reply settings until promoted.
- Administrator promotion creates or selects the approved taxonomy record, then updates the assigned category fields.
- Repeated proposed labels should be tracked so the system can later surface candidates for taxonomy cleanup.

## Examples

```text
Category: rules_question
Subcategory: eligibility
Topics: roster_management, league_play
Detected questions:
- Can I add a player after the roster deadline?
```

```text
Category: schedule_change_request
Subcategory: rainout
Topics: city_playoffs, court_availability
Detected questions:
- Can we reschedule a rained-out match?
- Are city playoff dates affected?
```

```text
Category: informational_notice
Subcategory: event_update
Topics: tournament, local_event
```

## Intended behavior

- Category drives workflow routing, draft instructions, deterministic templates, and reply-needed defaults.
- Subcategory refines category-specific behavior without creating too many top-level categories.
- Topics guide RAG retrieval, reporting, filtering, and trend analysis.
- Detected questions help draft generation answer every material question in the sender's email.
- Topics should not be treated as message disposition or priority.
- Proposed categories should not affect workflow automation until an administrator approves them.

## RAG implications

Rule and local-parameter chunks should store topic metadata. During draft generation, the system can use message topics and detected questions as retrieval hints while still allowing semantic search to find relevant sources.

## Open design details

- how many topics can be assigned per message
- whether topics are admin-editable in MVP
- whether detected questions are admin-editable in MVP
- how topics map to rule-source metadata
- the exact review-screen flow for accepting, editing, or dismissing proposed category labels
