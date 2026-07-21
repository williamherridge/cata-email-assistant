# Message Status Model

## Decision

Use message status only for administrator disposition. Use a separate draft state for proposed reply generation.

This avoids making a message look processed simply because the system is still drafting or has finished drafting. A message remains `new` until an administrator sends a response, marks it ignored, or a future Gmail sync detects that it was responded to externally.

## Message statuses

- `new`: the message has not been dispositioned by an administrator
- `responded`: a response was sent through the application or detected from Gmail in a later phase
- `ignored`: an administrator reviewed the message and chose not to respond

## Draft states

- `not_required`: no reply draft is expected
- `pending`: draft generation is planned or running
- `ready`: a proposed draft is available
- `failed`: draft generation failed or needs administrator intervention

## Queue behavior

- The default queue shows `new` incoming messages.
- The default queue hides sent replies.
- The default queue hides messages with status `responded`.
- The default queue hides messages with status `ignored`.
- Historical review happens on a separate `History` screen instead of overloading the active queue.

## UI implications

- The work queue should display draft state as a separate indicator, not as the message status.
- A message can be `new` and have draft state `pending`.
- A message can be `new` and have draft state `ready`.
- The administrator should have a clear `Ignore` action.
- Sending a reply through the application should set status to `responded`.
- Reopening a responded message should return it to `new` without losing prior sent-reply history.
- Reopened previously responded messages should also have a `Return to Responded` path when the administrator decides no additional follow-up is needed.
