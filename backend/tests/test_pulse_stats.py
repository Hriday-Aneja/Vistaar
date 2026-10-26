from app.services.pulse_stats import detect_spike


def test_flat_series_no_spike():
    assert detect_spike([5, 6, 5, 4, 5, 6, 5, 5, 4, 6, 5, 5, 6, 5, 5, 5]) is None


def test_clear_spike_detected():
    series = [5, 6, 5, 4, 5, 6, 5, 5, 4, 6, 5, 5, 6, 5, 16, 17]
    spike = detect_spike(series)
    assert spike and spike["uplift"] > 2


def test_too_little_history():
    assert detect_spike([5, 5, 20, 20]) is None
