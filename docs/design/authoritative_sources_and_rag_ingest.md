# Authoritative Sources and RAG Ingest

## Decision

MVP regulation sources are the CATA-curated National, Section, and Local PDFs listed in `data/rules_sources/sources_manifest.json`.

Local parameters are still needed before launch, but they are a launch content prerequisite rather than an architecture blocker.

## Source hierarchy

Rule precedence must be preserved in source metadata:

1. National
2. Section
3. Local
4. Local parameters

Local and parameter sources cannot override higher-precedence sources.

## MVP source workflow

- Store curated source files under `data/rules_sources/` during development.
- Track source URL, title, rule level, precedence, effective year, and status in `data/rules_sources/sources_manifest.json`.
- Extract PDF text into chunks for retrieval.
- Attach citation metadata to every chunk, including source id, source URL, rule level, local path, and page number when available.
- Require administrator review before replacing or re-indexing authoritative sources.

## Later enhancements

- Move curated source files to S3.
- Add automated source-change detection for trusted URLs.
- Add an admin source-management screen.
- Re-index changed sources after explicit administrator approval.
