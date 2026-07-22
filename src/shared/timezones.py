"""Shared timezone helpers for portal display and scheduled workflows."""

from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


DEFAULT_LOCAL_TIMEZONE = "America/Chicago"


def resolve_local_timezone(configured_timezone: str | None = None) -> ZoneInfo | datetime.tzinfo:
    """Return the configured or local timezone, with Central fallback."""
    if configured_timezone:
        try:
            return ZoneInfo(configured_timezone)
        except ZoneInfoNotFoundError:
            pass

    local_timezone = datetime.now().astimezone().tzinfo
    if local_timezone is not None:
        return local_timezone

    return ZoneInfo(DEFAULT_LOCAL_TIMEZONE)


def normalize_utc_to_local(value: datetime, configured_timezone: str | None = None) -> datetime:
    """Convert a stored UTC timestamp to the configured local timezone."""
    local_timezone = resolve_local_timezone(configured_timezone)
    if value.tzinfo is None:
        normalized = value.replace(tzinfo=UTC)
    else:
        normalized = value.astimezone(UTC)
    return normalized.astimezone(local_timezone)
