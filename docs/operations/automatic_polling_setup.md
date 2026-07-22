# Automatic Polling Setup

## Goal

Enable Gmail ingest without relying on the administrator to press `Poll Now`.

The lean pilot implementation now supports a scheduled polling runner that can be invoked frequently by the host scheduler while the application itself decides whether a mailbox is actually due.

## Runtime behavior

- Use the command below as the scheduled entrypoint:

```bash
./.venv/bin/python3 scripts/run_scheduled_poll.py
```

- The runner checks all active mailboxes.
- It polls only mailboxes that are due according to the configured schedule.
- It uses the configured local timezone for schedule evaluation.
- It continues to the next mailbox if one mailbox poll fails.

## Default schedule

Unless overridden in `config/.env`, the runner uses:

- `7:00 AM` through `7:00 PM` local time: poll every `15` minutes
- outside that window: poll every `2` hours

## Relevant configuration

These settings can be added to `config/.env` if needed:

```env
APP_DISPLAY_TIMEZONE=America/Chicago
GMAIL_POLL_DAY_START_HOUR=7
GMAIL_POLL_DAY_END_HOUR=19
GMAIL_POLL_DAY_INTERVAL_MINUTES=15
GMAIL_POLL_OFFHOURS_INTERVAL_MINUTES=120
```

Notes:

- If `APP_DISPLAY_TIMEZONE` is not set, the app uses the host local timezone.
- If host local timezone cannot be resolved, the fallback is `America/Chicago`.

## Manual verification

Use these commands from the repo root:

```bash
./.venv/bin/python3 scripts/run_scheduled_poll.py --force
./.venv/bin/python3 -m pytest tests/unit/test_polling.py -q
```

`--force` ignores the due-window check and polls every active mailbox immediately.

## macOS host scheduling

For the pilot, the simplest deployment model is:

- run the portal normally
- schedule the polling runner every `15` minutes with `launchd` or `cron`
- let the application skip off-hours invocations that are not due yet

This keeps host setup simple while still honoring the approved day/night cadence.

### Repository artifacts

- LaunchAgent plist:
  - [launchd/com.williamherridge.cata-email-assistant.polling.plist](/Users/williamherridge/Documents/repos/cata-email-assistant/launchd/com.williamherridge.cata-email-assistant.polling.plist)
- Wrapper script:
  - [scripts/run_scheduled_poll.sh](/Users/williamherridge/Documents/repos/cata-email-assistant/scripts/run_scheduled_poll.sh)

### Install on this Mac

```bash
mkdir -p ~/Library/LaunchAgents
cp launchd/com.williamherridge.cata-email-assistant.polling.plist ~/Library/LaunchAgents/com.williamherridge.cata-email-assistant.polling.plist
launchctl bootout "gui/$(id -u)" ~/Library/LaunchAgents/com.williamherridge.cata-email-assistant.polling.plist 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" ~/Library/LaunchAgents/com.williamherridge.cata-email-assistant.polling.plist
launchctl kickstart -k "gui/$(id -u)/com.williamherridge.cata-email-assistant.polling"
```

### Check status

```bash
launchctl print "gui/$(id -u)/com.williamherridge.cata-email-assistant.polling"
tail -n 50 data/processed/logs/scheduled_poll.log
```

## Cron fallback

If `launchd` is temperamental on a specific Mac, use the user crontab instead:

```bash
*/15 * * * * /Users/williamherridge/bin/cata-email-assistant-run-scheduled-poll.sh
```

This is still valid for the lean pilot because:

- the host is invoking one simple command
- the application itself decides whether a mailbox is actually due
- off-hours runs are skipped by schedule logic inside the app

## Next step after automatic polling

After automatic polling is in place, the next planned implementation step is Google Sheets automation for the target ingest workflow:

- extend the existing Google OAuth flow to include Sheets write scope
- append rows during ingest
- only programmatically ignore dependent message types after the sheet write succeeds
