# Priority Model

## Decision

Use three priority levels in MVP:

- `critical`
- `normal`
- `low`

Priority exists to change administrator workflow, not just to label messages. It should affect sorting, filtering, visual emphasis, and notification behavior.

## Priority levels

### `critical`

Use for messages that may require unusually fast attention because of urgency, deadline risk, operational impact, or high-sensitivity content.

Expected behavior:

- sort above all other open messages
- receive strong visual treatment in the portal
- support SMS notification to the configured administrator phone number
- include a direct portal link in the SMS notification

### `normal`

Use for ordinary messages that need standard handling.

Expected behavior:

- appear in the standard work queue
- sort below `critical` and above `low`
- receive standard visual treatment

### `low`

Use for messages that can reasonably wait or are lower-value to process immediately.

Expected behavior:

- sort below `critical` and `normal`
- remain visible in the default queue unless filtered out
- support filtering so administrators can focus on higher-priority work

## Extensibility

The system should store priority as configurable data or a constrained enum that can be migrated cleanly. If CATA later needs another level, the data model and UI should support adding it without redesigning the workflow.

## Open design details

- exact critical priority rules
- SMS provider choice
- SMS retry and failure behavior
- whether SMS notification should be enabled in MVP or built as a near-term follow-up
