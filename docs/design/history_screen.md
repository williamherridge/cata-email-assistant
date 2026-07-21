# History Screen

## Purpose

The main queue is the active work list for `new` messages only.

Responded and ignored messages need a separate review surface that behaves more like an Outlook sent or archive view:

- read-only by default
- easy to scan chronologically
- easy to reopen a message back to `new`
- clear visibility into the original inbound email and any sent reply

## Entry Point

Add a top-level `History` link in the portal shell.

The screen opens on the `Sent/Responded` tab by default.

## Tabs

### Sent/Responded

Show only messages where:

- `status = responded`

Behavior:

- sort by `responded_at` descending
- support simple search by sender and subject
- render a compact Outlook-style list on the left
- render a read-only preview stack on the right

Primary actions:

- `Return to New`
- after reopen, redirect back to the main queue with the message selected so the administrator can send another reply if needed

### Ignored

Show only messages where:

- `status = ignored`

Behavior:

- sort by `ignored_at` descending
- support simple search by sender and subject
- default to `manual` ignored messages only
- allow switching to `all` ignored messages to include future programmatic ignores

Primary actions:

- `Return to New`

## Layout

Use a split-pane layout similar to a mail client:

- left pane: message list
- right pane: read-only preview

### Left Pane

List rows should show:

- sender
- subject
- sent or ignored date
- compact status-context metadata where useful

### Right Pane

For responded messages, show:

1. header and read-only metadata
2. the most recent sent reply in a locked preview surface
3. the original inbound message below it
4. audit context at the bottom

For ignored messages, show:

1. header and read-only metadata
2. original inbound message
3. ignore audit context including whether the ignore was manual or programmatic

## Reopened Messages

When a responded message is returned to `new`:

- `status` becomes `new`
- `responded_at` remains populated
- sent reply artifacts remain available
- the administrator may either send another follow-up or return the message to `responded` without sending anything new

When an ignored message is returned to `new`:

- `status` becomes `new`
- `ignored_at` remains available as historical context if needed later

## Main Queue Implications

If a reopened message has prior sent-reply history, the main queue should make that obvious:

- show a compact `previous reply sent` indicator in the queue row metadata cluster
- show a read-only `Previous Reply Sent` panel in the workbench when the message is selected

The administrator can still edit metadata and send another reply from the main queue once the message is back in `new`.
If the administrator reopens a previously responded message and then decides not to send anything else, the queue should offer a `Return to Responded` action so the message leaves the active queue without being misclassified as ignored.

## Outbound Reply Composition

Replies sent through the portal should behave like a standard mail client:

- the newly authored reply appears at the top
- the most recent prior sent reply is quoted below when one exists
- the original inbound message is included below the reply history
- separators and labels should make the context clear to the recipient

This ensures recipients always receive enough context even when the administrator sends a second or later follow-up from a reopened message.

## v1 Scope

Include:

- `History` link
- `Sent/Responded` tab
- `Ignored` tab
- simple search
- manual-vs-all ignored filter
- `Return to New`
- read-only sent reply visibility
- reopened-message indicator on the main queue

Defer:

- forward flow
- full thread-style sent conversation view
- deep pagination or virtual scrolling
- advanced filtering by category, date range, or priority
