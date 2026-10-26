"""Pure demand-forecast helper (no DB).

v0: moving average * festival multiplier. TODO: XGBoost + SHAP so each forecast can say *why*
(see requirements-ml.txt). The DB-backed per-shop rate used by bulk-buy lives in services/inventory.py.
"""


def forecast_units(history: list[int], horizon_days: int = 14, festival_multiplier: float = 1.0) -> int:
    if not history:
        return 0
    recent = history[-7:]
    daily = sum(recent) / len(recent)
    return round(daily * horizon_days * festival_multiplier)
