"""Distributor Fair-Price Radar.

1) Benchmark: the median unit price that *other* pools actually paid recently, released only when
   enough distinct orders exist (k-anonymity), so no single order's price is exposed.
2) Flag: a quote well above that benchmark is marked inflated.
3) Reverse auction: distributors undercut each other in rounds, down to their own floor price.
Pure functions; DB access lives in services/bulk.py.
"""
from statistics import median

MIN_SAMPLES = 5
INFLATED_TOLERANCE = 0.08  # more than 8% above the benchmark


def benchmark(paid_prices: list[float], min_samples: int = MIN_SAMPLES) -> float | None:
    if len(paid_prices) < min_samples:
        return None
    return round(median(paid_prices), 2)


def flag_quote(unit_price: float, bench: float | None, tolerance: float = INFLATED_TOLERANCE) -> dict | None:
    if bench is None or bench <= 0:
        return None
    over = unit_price / bench - 1
    if over > tolerance:
        return {"level": "inflated", "pct_over": round(over * 100, 1), "benchmark": bench}
    return None


def run_reverse_auction(
    offers: dict[str, float],
    floors: dict[str, float],
    step_pct: float = 0.015,
    max_rounds: int = 6,
) -> tuple[dict[str, float], list[dict]]:
    """offers: {distributor_id: price}; floors: {distributor_id: lowest acceptable price}.

    Each round, every distributor that is not currently the cheapest tries to undercut the best
    price by step_pct (never below its floor). Stops when nobody can improve.
    Returns (final_offers, events) where events are {round, distributor_id, price}.
    """
    current = dict(offers)
    events: list[dict] = []
    for rnd in range(1, max_rounds + 1):
        best = min(current.values())
        changed = False
        for dist_id in sorted(current):
            if current[dist_id] <= best:
                continue
            target = max(floors.get(dist_id, current[dist_id]), round(best * (1 - step_pct), 2))
            if target < current[dist_id]:
                current[dist_id] = target
                events.append({"round": rnd, "distributor_id": dist_id, "price": target})
                changed = True
        if not changed:
            break
    return current, events
