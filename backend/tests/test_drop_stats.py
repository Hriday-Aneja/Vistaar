from app.services.drop_stats import detect_drop

NORMAL = [60, 64, 58, 61, 63, 59, 62, 60, 65, 57, 61, 62, 60, 63, 59, 61, 60]


def test_flat_series_no_drop():
    assert detect_drop(NORMAL) is None


def test_clear_drop_detected():
    drop = detect_drop(NORMAL[:-3] + [18, 20, 17])
    assert drop and drop["drop_pct"] >= 60 and drop["z"] < -3


def test_small_dip_is_ignored():
    assert detect_drop(NORMAL[:-3] + [52, 50, 51]) is None


def test_too_little_history():
    assert detect_drop([60, 60, 10, 10]) is None


def test_tiny_shop_is_ignored():
    assert detect_drop([2, 3, 2, 3, 2, 3, 2, 3, 2, 3, 2, 3, 2, 3, 2, 3, 0, 0, 0]) is None