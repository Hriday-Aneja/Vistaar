"""Sales-drop detection on a shop's total daily units. Pure: no DB, so it is unit-tested directly."""
from statistics import mean, pstdev
from typing import Optional

RECENT_DAYS = 3
MIN_BASELINE_DAYS = 14
Z_THRESHOLD = -3.0
MAX_RATIO = 0.6          # recent average must be at most 60% of the normal average
MIN_BASELINE_UNITS = 5.0  # very small shops are too noisy to judge


def detect_drop(daily: list[float]) -> Optional[dict]:
    if len(daily) < RECENT_DAYS + MIN_BASELINE_DAYS:
        return None
    baseline, recent = daily[:-RECENT_DAYS], daily[-RECENT_DAYS:]
    base_mean = mean(baseline)
    if base_mean < MIN_BASELINE_UNITS:
        return None
    spread = max(pstdev(baseline), 0.1 * base_mean, 1.0)
    recent_mean = mean(recent)
    z = (recent_mean - base_mean) / spread
    if z > Z_THRESHOLD or recent_mean > MAX_RATIO * base_mean:
        return None
    return {"baseline": round(base_mean, 1), "recent": round(recent_mean, 1),
            "drop_pct": round((1 - recent_mean / base_mean) * 100), "z": round(z, 1), "recent_days": RECENT_DAYS}