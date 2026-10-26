from app.services.swap_scoring import WEIGHTS, score_swap


def test_weights_sum_to_100():
    assert sum(WEIGHTS.values()) == 100


def test_closer_and_more_urgent_scores_higher():
    near_urgent, _ = score_swap(0.5, 3, 5, 1.0, 1.0, 0.2)
    far_relaxed, _ = score_swap(2.8, 3, 25, 4.5, 0.3, 0.1)
    assert near_urgent > far_relaxed


def test_breakdown_adds_up():
    total, parts = score_swap(1.0, 3, 9, 2.0, 0.8, 0.2)
    assert round(sum(p["points"] for p in parts), 1) == total
