import random

from app.services.privacy import bucket_count, k_anonymous, noisy_amount, pool_demand


def test_k_anonymous():
    assert k_anonymous(5, 5) and not k_anonymous(4, 5)


def test_small_groups_not_released():
    assert pool_demand({f"s{i}": {"ghee": 10} for i in range(3)}, k=5, epsilon=1.0) == {}


def test_large_groups_released():
    out = pool_demand({f"s{i}": {"ghee": 10} for i in range(40)}, k=5, epsilon=1.0, rng=random.Random(1))
    assert "ghee" in out


def test_udhaar_noise_is_stable_within_a_day_and_bucketed():
    a = noisy_amount(1234, "hash1", "credit", "2026-10-26")
    assert a == noisy_amount(1234, "hash1", "credit", "2026-10-26") and a % 50 == 0


def test_bucket_count():
    assert bucket_count(2) == "2" and bucket_count(9) == "5+"
