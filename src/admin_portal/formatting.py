"""Portal display formatting helpers."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
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
    return _format_portal_datetime(value, timezone_name, include_timezone_abbreviation=True)


def format_portal_datetime_compact(value: datetime | None, timezone_name: str | None = None) -> str:
    """Format UTC-stored datetimes for compact table display."""
    return _format_portal_datetime(value, timezone_name, include_timezone_abbreviation=False)


def format_queue_received_datetime(value: datetime | None, timezone_name: str | None = None) -> str:
    """Format queue received timestamps similar to an email client list view."""
    if value is None:
        return "Unknown"

    local_value = _normalize_local_datetime(value, timezone_name)
    today = datetime.now(resolve_display_timezone(timezone_name)).date()
    yesterday = today - timedelta(days=1)

    if local_value.date() == today:
        return _format_time(local_value)
    if local_value.date() == yesterday:
        return "Yesterday"
    return _format_short_date(local_value.date())


def _format_portal_datetime(
    value: datetime | None,
    timezone_name: str | None,
    *,
    include_timezone_abbreviation: bool,
) -> str:
    """Format UTC-stored datetimes for human-friendly portal display."""
    if value is None:
        return "Never"

    local_value = _normalize_local_datetime(value, timezone_name)
    formatted = f"{local_value.year:04d}-{local_value.month:02d}-{local_value.day:02d} {_format_time(local_value)}"
    if include_timezone_abbreviation:
        zone_name = local_value.strftime("%Z").lower()
        if zone_name:
            return f"{formatted} {zone_name}"
    return formatted


def _normalize_local_datetime(value: datetime, timezone_name: str | None) -> datetime:
    display_timezone = resolve_display_timezone(timezone_name)
    if value.tzinfo is None:
        normalized = value.replace(tzinfo=UTC)
    else:
        normalized = value.astimezone(UTC)
    return normalized.astimezone(display_timezone)


def _format_time(value: datetime) -> str:
    hour = value.hour % 12 or 12
    minute = value.minute
    meridiem = "am" if value.hour < 12 else "pm"
    return f"{hour}:{minute:02d} {meridiem}"


def _format_short_date(value: date) -> str:
    year = value.year % 100
    return f"{value.month}/{value.day}/{year:02d}"
