# Queue Workbench Layout

This design note captures the first split-pane direction for the main administrator work screen.

## Purpose

The queue screen should evolve into the primary workbench for the administrator.

The administrator should be able to:

- scan incoming work quickly
- select a message without leaving the queue screen
- review and adjust metadata
- shape the reply recipients and subject
- compose or edit the reply draft
- ignore a message when no response is needed

The full detail screen should remain available for lower-frequency needs such as:

- audit trail review
- attachment inspection
- opening the original thread in Gmail

## Layout

Use a split-pane layout:

- left pane: compact mail-style queue
- right pane: stacked workbench

### Left Pane

The queue should behave more like an email client list than a wide data table.

Queue rows should include:

- unread/new visual emphasis through typography
- `From`
- fixed-width `Subject`
- right-aligned `Date`
- one compact metadata icon cluster

Queue metadata icons should appear in a fixed left-to-right order:

1. reply-needed or informational icon
2. priority icon
3. thread/grouping indicator in a future version
4. attachment icon

Current screen decisions:

- do not show the status column on the default queue screen
- do not show a separate attachments column header
- keep `Date` compact like Outlook:
  - today: time only
  - yesterday: `Yesterday`
  - older: short date
- limit `From` and `Subject` to two visible lines with truncation
- if a reopened message was previously responded to, show a compact sent-history indicator in the metadata icon cluster

## Right Pane

Stack three panels vertically:

1. metadata and action controls
2. draft composition area
3. original email body

### Top Panel

Include:

- editable `To`
- editable `Cc`
- editable reply subject
- category and subcategory controls
- priority
- reply-needed
- informational-only flag
- action buttons such as save review and ignore
- when a reopened message has prior reply history, include a `Return to Responded` action alongside the active-queue actions

### Middle Panel

This is the primary work area.

It should be a large draft composition surface with:

- rich text formatting controls
- a default signature at the bottom
- future save / regenerate / send behavior
- outbound send behavior that appends prior sent reply history and the original inbound message below the newly authored reply

### Bottom Panel

Display the original email body in a lower-priority scrollable surface.

If a selected `new` message has prior sent-reply history, insert a read-only `Previous Reply Sent` panel above the original email panel.

## Priority Model

The MVP priority model is:

- `critical`
- `normal`
- `low`

Visual treatment:

- `critical`: red exclamation mark
- `normal`: no icon
- `low`: muted down arrow

## Future Enhancements

- optional thread grouping in the queue
- richer draft-state visualization in the queue
- persistent draft save behavior
- regenerate flow
- send flow
- richer category pills or badges when the queue earns them through usability testing
- dedicated `History` screen for responded and ignored messages
