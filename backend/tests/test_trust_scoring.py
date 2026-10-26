from app.services.trust_scoring import score_risk, suggested_limit


def test_good_payer_is_low_risk():
    score, level, _ = score_risk(repay_ratio=1.0, overdue_days=0, other_pending=0)
    assert level == "Low" and score == 0.0


def test_bad_payer_is_high_risk():
    _, level, _ = score_risk(repay_ratio=0.1, overdue_days=70, other_pending=3500)
    assert level == "High"


def test_limit_shrinks_with_risk_and_is_in_hundreds():
    low, _ = suggested_limit(0.1, 0, 0)
    high, _ = suggested_limit(0.7, 0, 0)
    assert low > high and low % 100 == 0


def test_room_left_never_negative():
    _, room = suggested_limit(0.5, 0, own_pending=99999)
    assert room == 0
