from datetime import date, timedelta

from app.services.expiry import assess, effective_expiry

TODAY = date(2026, 10, 26)


def test_high_risk_when_most_stock_wont_sell():
    r = assess(140, 2.0, TODAY, expiry_date=TODAY + timedelta(days=9))
    assert r["level"] == "high" and r["at_risk_qty"] == 122


def test_low_risk_when_it_will_sell():
    assert assess(20, 5.0, TODAY, expiry_date=TODAY + timedelta(days=30))["level"] == "low"


def test_expired():
    assert assess(10, 1.0, TODAY, expiry_date=TODAY - timedelta(days=1))["level"] == "expired"


def test_default_expiry_is_marked_as_estimate():
    exp, source = effective_expiry(None, "entered", TODAY, 120)
    assert exp == TODAY + timedelta(days=120) and source == "default"
