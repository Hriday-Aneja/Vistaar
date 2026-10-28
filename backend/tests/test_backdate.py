"""Rules for backdated sales and udhaar entries. Pure: no DB, no web stack."""
from datetime import date, datetime, timedelta

import pytest

from app.services.backdate import MAX_BACKDATE_DAYS, check_backdate, noon_of

TODAY = date(2026, 10, 28)


def test_today_and_the_last_allowed_day_pass():
    check_backdate(TODAY, TODAY)
    check_backdate(TODAY - timedelta(days=1), TODAY)
    check_backdate(TODAY - timedelta(days=MAX_BACKDATE_DAYS), TODAY)


def test_the_limit_is_60_days():
    assert MAX_BACKDATE_DAYS == 60


def test_future_dates_are_rejected_in_hinglish():
    with pytest.raises(ValueError, match="Aane wali date"):
        check_backdate(TODAY + timedelta(days=1), TODAY)


def test_dates_older_than_60_days_are_rejected_in_hinglish():
    with pytest.raises(ValueError, match="60 din se purani"):
        check_backdate(TODAY - timedelta(days=MAX_BACKDATE_DAYS + 1), TODAY)


def test_backdated_rows_are_stamped_at_noon_like_the_seed_data():
    assert noon_of(TODAY) == datetime(2026, 10, 28, 12, 0)