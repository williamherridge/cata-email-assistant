"""Portal display formatting helpers."""

from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


DEFAULT_DISPLAY_TIMEZONE = "America/Chicago"


def resolve_display_timezone(configured_timezone: str | None = None) -> ZoneInfo | datetime.tzinfo:
    """Return the configured or local timezone, with Central fallback."""
    if configured_timezone:
        try:
            return ZoneInfo(configured_timezone)
        except ZoneInfoNotFoundError:
            pass

    local_timezone = datetime.now().astimezone().tzinfo
    if local_timezone is not None:
        return local_timezone

    return ZoneInfo(DEFAULT_DISPLAY_TIMEZONE)


def format_portal_datetime(value: datetime | None, timezone_name: str | None = None) -> str:
    """Format UTC-stored datetimes for human-friendly portal display."""
    if value is None:
        return "Never"

    display_timezone = resolve_display_timezone(timezone_name)
    if value.tzinfo is None:
        normalized = value.replace(tzinfo=UTC)
    else:
        normalized = value.astimezone(UTC)

    local_value = normalized.astimezone(display_timezone)
    return local_value.strftime("%Y-%m-%d %I:%M %p %Z").lower()
