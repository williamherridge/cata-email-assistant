# Recommended Repository Structure

## Goal

Keep product artifacts, source code, and operational assets organized so the repository can support the full lifecycle: requirements, architecture, design, development, testing, and implementation.

## Recommended shape

```text
.
├── config/
├── data/
├── docs/
│   ├── architecture/
│   ├── design/
│   ├── implementation/
│   ├── requirements/
│   ├── testing/
│   ├── architecture.md
│   ├── phases.md
│   ├── product_requirements.md
│   └── repo_structure.md
├── scripts/
├── src/
│   ├── admin_portal/
│   ├── gmail_ingest/
│   ├── knowledge_base/
│   ├── message_processing/
│   ├── notifications/
│   ├── taxonomy/
│   └── workflow/
├── tests/
│   ├── integration/
│   ├── prompts/
│   └── unit/
└── web/
```

## Near-term guidance

The current repository does not need a large code move immediately. A low-risk next step is:

- keep existing exploratory modules where they are
- add new lifecycle artifacts under `docs/`
- add new product code in purpose-based packages instead of one-off utilities
- split tests into `unit/` and `integration/` as the codebase grows

## Directory intent

### `config/`

- local configuration examples
- prompt/config manifests
- rule-source manifests
- deployment configuration templates

### `data/`

- local development data
- exported samples
- evaluation datasets
- temporary artifacts that should not become the long-term system of record

### `docs/requirements/`

- stakeholder notes
- use cases
- user stories
- glossary
- decision logs related to scope

### `docs/architecture/`

- diagrams
- AWS option analysis
- security model
- cost model
- integration boundaries

### `docs/design/`

- UI flows
- API contracts
- prompt design
- rule engine design
- data schemas

### `docs/testing/`

- test strategy
- evaluation plans
- UAT scripts
- regression checklists

### `docs/implementation/`

- deployment runbooks
- onboarding guides
- production support notes

### `src/gmail_ingest/`

- Gmail API sync and send integration

### `src/message_processing/`

- normalization
- deterministic rules
- orchestration of classification and priority

### `src/knowledge_base/`

- rule ingestion
- chunking
- retrieval
- citations

### `src/taxonomy/`

- taxonomy catalog
- taxonomy suggestion logic
- admin taxonomy updates

### `src/admin_portal/`

- server-side web application code
- admin authentication
- review queue and editing flows

### `src/workflow/`

- message state transitions
- review lifecycle
- audit events

### `tests/prompts/`

- prompt fixtures
- evaluation cases for classification and draft generation

## Recommended next repo changes

1. Add phase-specific subfolders under `docs/`.
2. Introduce product-oriented packages under `src/` for new application work.
3. Separate exploratory scripts from production application entry points.
4. Remove committed secrets and OAuth tokens from version control before the repo is shared more broadly.
