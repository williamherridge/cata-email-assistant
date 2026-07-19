from datetime import datetime

from src.admin_portal.formatting import format_portal_datetime


def test_format_portal_datetime_converts_utc_to_central_with_12_hour_clock():
    value = datetime(2026, 7, 19, 18, 5, 0)

    formatted = format_portal_datetime(value, "America/Chicago")

    assert formatted == "2026-07-19 01:05 pm cdt"


def test_format_portal_datetime_returns_never_for_missing_values():
    assert format_portal_datetime(None, "America/Chicago") == "Never"
