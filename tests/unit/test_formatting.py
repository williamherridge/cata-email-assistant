from datetime import datetime

from src.admin_portal.formatting import format_portal_datetime, format_queue_received_datetime


def test_format_portal_datetime_converts_utc_to_central_with_12_hour_clock():
    value = datetime(2026, 7, 19, 18, 5, 0)

    formatted = format_portal_datetime(value, "America/Chicago")

    assert formatted == "2026-07-19 1:05 pm cdt"


def test_format_portal_datetime_returns_never_for_missing_values():
    assert format_portal_datetime(None, "America/Chicago") == "Never"


def test_format_queue_received_datetime_uses_time_for_today():
    value = datetime(2026, 7, 19, 18, 5, 0)

    formatted = format_queue_received_datetime(value, "America/Chicago")

    assert formatted == "1:05 pm"


def test_format_queue_received_datetime_uses_yesterday_label():
    value = datetime(2026, 7, 18, 18, 5, 0)

    formatted = format_queue_received_datetime(value, "America/Chicago")

    assert formatted == "Yesterday"


def test_format_queue_received_datetime_uses_short_date_for_older_messages():
    value = datetime(2026, 7, 17, 18, 5, 0)

    formatted = format_queue_received_datetime(value, "America/Chicago")

    assert formatted == "7/17/26"
