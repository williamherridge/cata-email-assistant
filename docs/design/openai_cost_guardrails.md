# OpenAI Cost Guardrails

## Decision

MVP architecture should enforce conservative OpenAI usage guardrails:

- Soft budget: $10/month.
- Hard cap: $15-$20/month.
- Cost is more important than immediate draft availability.

## Behavior

When usage approaches the soft budget, the application should alert administrators or visibly warn them in the portal.

When usage reaches the hard cap, the application should pause non-essential AI draft generation while preserving core operations:

- Gmail ingest continues.
- Deterministic categorization and deterministic reply rules continue.
- Queue review continues.
- Existing drafts and prework remain editable.
- Administrator sending remains available.
- Manual portal refresh and `Poll now` remain available.

## Architecture implications

- Track OpenAI usage and estimated cost by request type.
- Separate lower-cost classification/prework from higher-cost formal drafting.
- Cache classification, retrieval, prework, and generated drafts where safe.
- Prefer manual or category-configured draft generation over drafting every message by default.
- Keep prompts scoped to the assigned category, detected topics, and curated rule context.
- Provide clear fallback behavior so the portal remains usable if AI drafting is paused.

## MVP non-goals

- Automatic full replies are not allowed.
- Budget exhaustion must not block email viewing or administrator response workflow.
- Advanced cost optimization can be improved after pilot usage data is available.
