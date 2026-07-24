# Deterministic Rules Reference

This document describes the message categories the app can currently assign without using an LLM.

Use this as a quick admin-facing reference for what the system already knows how to recognize automatically.

## Current deterministic categories

### `Make-up date form`

- Outcome:
  - category assigned automatically
  - auto-ignored
  - `reply_needed = false`
  - `priority = low`
- Current recognition pattern:
  - sender: `web@site.tennisaustin.org`
  - subject starts with: `New submission from Make Up Match DATE Notification`
  - body markers include:
    - `Match ID`
    - `Date for Doubles 1`

### `Make-up match line up`

- Outcome:
  - category assigned automatically
  - auto-ignored
  - `reply_needed = false`
  - `priority = low`
- Current recognition pattern:
  - sender: `web@site.tennisaustin.org`
  - subject starts with: `Make-Up Match Line Up from`
  - body markers include:
    - `Original Match Number`
    - `Captain's Name`
    - `Opposing Captain`

### `Team registration submission`

- Outcome:
  - category assigned automatically
  - not auto-ignored
  - `reply_needed = false` by default
  - `priority = normal`
- Current recognition pattern:
  - sender is one of:
    - `no-reply@austintennis.org`
    - `leaguecommittee@austintennis.org`
  - subject contains a supported registration marker such as:
    - `team registration from`
    - `new fall team registration from`
    - `new spring team registration from`
    - `new summer team registration from`
    - `new winter team registration from`
  - body markers include:
    - `Captain Name`
    - `Captain USTA Number`
    - `Registration Type`
    - `Team Name`
    - league / level structure
- Additional post-classification behavior:
  - qualifying registrations are written to the Google Sheet and then marked `processed`
  - some facility-permission cases are blocked and kept for manual follow-up instead
  - duplicate detection is applied before a sheet row is inserted

### `Facility Request > UT-W`

- Outcome:
  - category assigned automatically
  - subcategory assigned automatically: `UT-W`
  - auto-ignored
  - `reply_needed = false`
  - `priority = low`
- Current recognition pattern:
  - sender: `web@site.tennisaustin.org`
  - subject starts with: `UT-W League Facility Request from`

### `Ineligible League Player Form`

- Outcome:
  - category assigned automatically
  - auto-ignored
  - `reply_needed = false`
  - `priority = low`
- Current recognition pattern:
  - sender: `noreply@formresponse.com`
  - subject starts with: `❗️ Ineligible League Player Form`

## Notes

- Reply messages such as `Re:` are intentionally excluded from these deterministic form rules.
- Deterministic rules run before any LLM-assisted classification.
- This file should be updated whenever a new rule is added, removed, or materially changed.
