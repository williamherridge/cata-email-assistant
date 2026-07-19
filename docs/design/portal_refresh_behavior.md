# Portal refresh behavior

## Decision

The MVP portal should avoid timer-based auto-refresh. Refresh should be manual by default, with narrow action-triggered refresh only where it directly supports the administrator workflow.

This decision is intended to reduce unnecessary database/API/LLM-related cost, especially when a browser tab is left open for long periods.

## MVP behavior

- Provide a visible `Refresh` button in the queue and response workbench.
- Show a `Last refreshed at` timestamp.
- Refresh portal data after an administrator sends a response.
- Refresh portal data after draft generation completes.
- Do not automatically refresh after a message is marked `ignored`.
- Do not automatically refresh after category or priority changes.
- Do not use interval/timer-based auto-refresh in MVP.

## Rationale

- Manual refresh gives administrators control and keeps costs predictable.
- Refresh after send helps the queue reflect the new `responded` status and hide the handled message from the default view.
- Refresh after draft generation helps the workbench show newly available generated content.
- Avoiding refresh after category/priority edits prevents unexpected UI movement while the administrator is still working.
- Avoiding timer-based refresh prevents runaway cost if a portal session is left open overnight.
