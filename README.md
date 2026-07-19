# cata-email-assistant

This repository is evolving into a CATA email assistant that:

- monitors a Gmail inbox
- classifies and prioritizes incoming email
- flags informational-only messages
- drafts responses for administrator review
- lets an administrator edit and send approved replies
- uses rules, deterministic logic, and LLM-assisted reasoning
- supports rule-aware RAG for national, section, and local guidance

## Current focus

The project is in the requirements and planning stage for the full application. Existing code includes:

- Gmail read-only ingestion helpers in `src/gmail_ingest/`
- taxonomy exploration utilities in `src/email_analytics/` and `web/taxonomy_review_app/`

## Project docs

- `docs/product_requirements.md`: product and functional requirements
- `docs/requirements/mvp_scope.md`: frozen MVP scope and remaining blockers
- `docs/phases.md`: lifecycle phases, milestones, and deliverables
- `docs/repo_structure.md`: recommended repository structure for project artifacts
- `docs/taxonomy_review_app.md`: taxonomy review utility
