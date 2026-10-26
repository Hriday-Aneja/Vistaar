from app.services.reasons import FORECAST_METHOD, explain_need


def test_reason_mentions_rate_stock_festival_and_need():
    text = explain_need(rate=4.0, stock=20, horizon_days=14, multiplier=1.3, need=53)
    assert "~4" in text and "stock 20" in text and "5 din" in text
    assert "30%" in text and "demo assumption" in text
    assert text.endswith("14 din ke liye 53 aur chahiye")


def test_reason_without_festival_or_sales():
    assert "tyohaar" not in explain_need(2.0, 0, 14, 1.0, 28)
    assert "din chalega" not in explain_need(0.0, 5, 14, 1.0, 0)


def test_method_label_says_not_ml():
    assert "not ML" in FORECAST_METHOD