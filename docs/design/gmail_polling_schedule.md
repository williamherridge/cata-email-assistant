# Gmail polling schedule

## Decision

Gmail polling should use a low-cost scheduled model with an administrator-triggered immediate poll option.

This is an operational default, not an architecture blocker. The schedule should remain configurable so it can be tuned after production usage is observed.

## MVP schedule

- Poll every 15 minutes from 7:00 AM through 7:00 PM every day.
- Poll every 2 hours outside 7:00 AM through 7:00 PM.
- Use the deployment's configured local timezone for schedule evaluation.
- Make newly ingested messages visible even if classification, prework, or draft generation is still pending.

## Portal control

- Provide a visible `Poll now` button.
- Prioritize usability on mobile screens.
- Trigger an immediate Gmail ingest attempt when selected.
- Keep `Poll now` separate from regular portal data refresh; polling contacts Gmail, while refresh reloads already-ingested application data.

## Rationale

- Daytime polling keeps the queue reasonably current during active admin hours.
- Off-hours polling reduces idle cost and unnecessary API activity.
- The immediate poll button gives administrators a way to check for urgent new messages without increasing background frequency.
