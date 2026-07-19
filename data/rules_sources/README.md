# Rules Source Intake

Place authoritative rule and local-parameter source files here before they are processed into the application knowledge base.

## Folder hierarchy

- `national/` — National rules and regulations. These have highest precedence.
- `section/` — Section/state-level rules and regulations. These apply when they do not conflict with national rules.
- `local/` — CATA/local league rules, procedures, and published guidance. These apply when they do not conflict with national or section rules.
- `local_parameters/` — Structured local operating values such as roster limits, due dates, playoff dates, facility details, and event parameters.

## Recommended file naming

Use descriptive, version-aware names where possible:

- `2026_usta_national_league_regulations.pdf`
- `2026_texas_section_league_regulations.pdf`
- `2026_cata_local_league_rules.pdf`
- `2026_spring_adult_40_roster_parameters.xlsx`

## Source metadata to preserve

Source metadata is tracked in `sources_manifest.json`. When available, each source should identify:

- Source URL
- Effective date or season
- Version or publication date
- Rule level: national, section, local, or local parameter
- Any known replacement/supersession details

For MVP, these files are treated as CATA-curated authoritative sources. Automated monitoring of external source URLs is deferred until a later phase.
