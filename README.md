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

The project is now in early `Milestone B` work for the lean pilot runtime. Current application work includes:

- a `FastAPI` admin portal in `src/admin_portal/`
- `SQLite` persistence and Alembic migrations for the first operational schema
- Gmail poll and ingest workflow scaffolding in `src/workflow/` and `src/gmail_ingest/`
- scheduled polling support for lean host-based operation
- earlier Gmail read-only ingestion helpers and taxonomy exploration utilities

## Project docs

- `docs/product_requirements.md`: product and functional requirements
- `docs/requirements/mvp_scope.md`: frozen MVP scope and remaining blockers
- `docs/phases.md`: lifecycle phases, milestones, and deliverables
- `docs/operations/automatic_polling_setup.md`: lean pilot scheduled polling setup
- `docs/repo_structure.md`: recommended repository structure for project artifacts
- `docs/taxonomy_review_app.md`: taxonomy review utility

## Local app bootstrap

1. Create or update `config/.env` from `config/.env.example`.
2. Ensure `DEFAULT_GMAIL_ADDRESS` points at the mailbox you want to pilot.
3. Run `alembic upgrade head`.
4. Start the portal with `python -m src.admin_portal.main`.
5. Optional: run scheduled polling with `./.venv/bin/python3 scripts/run_scheduled_poll.py`.

The queue surface will be available at `http://127.0.0.1:8000/queue`.
