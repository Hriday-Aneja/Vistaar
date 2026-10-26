"""Privacy layer.

1) Cohort pooling (bulk-buy): k-anonymity gate + Laplace differential privacy.
   A SKU's pooled demand is only released if >= k shops contributed, and the number carries noise.
2) Udhaar trust network: deterministic, bucketed noise on cross-shop numbers, seeded per customer
   and day so repeating the query cannot average the noise away.

Prototype-level. Production would use private set intersection / federated scoring.
"""
import math
import random

PRIVACY_LABEL = "prototype: keyed hash + noise, production: private set intersection"


# ---------- shared ----------
def k_anonymous(contributors: int, k: int) -> bool:
    return contributors >= k


def laplace_noise(scale: float, rng: random.Random | None = None) -> float:
    r = rng or random
    u = r.random() - 0.5
    return -scale * math.copysign(1.0, u) * math.log(1 - 2 * abs(u))


# ---------- bulk-buy pooling ----------
def pool_demand(
    per_shop: dict[str, dict[str, int]],
    k: int,
    epsilon: float,
    clip: int = 50,
    rng: random.Random | None = None,
) -> dict[str, int]:
    """per_shop: {shop_id: {sku: qty}} -> {sku: noisy_total}, only for SKUs with >= k shops.

    Each shop's quantity is clipped to `clip`, so sensitivity = clip.
    """
    skus: dict[str, list[int]] = {}
    for items in per_shop.values():
        for sku, qty in items.items():
            if qty > 0:
                skus.setdefault(sku, []).append(min(qty, clip))

    released: dict[str, int] = {}
    for sku, qtys in skus.items():
        if not k_anonymous(len(qtys), k):
            continue
        noisy = sum(qtys) + laplace_noise(clip / epsilon, rng)
        released[sku] = max(0, round(noisy))
    return released


# ---------- udhaar network ----------
def _noisy(value: float, scale: float, step: int, seed: str) -> int:
    rng = random.Random(seed)
    return int(round(max(0.0, value + laplace_noise(scale, rng)) / step) * step)


def noisy_amount(value: float, phone_hash: str, field: str, day: str) -> int:
    return _noisy(value, 150, 50, f"{phone_hash}:{field}:{day}")


def noisy_days(value: float, phone_hash: str, field: str, day: str) -> int:
    return _noisy(value, 3, 5, f"{phone_hash}:{field}:{day}")


def bucket_count(count: int, cap: int = 5) -> str:
    return f"{cap}+" if count >= cap else str(count)
