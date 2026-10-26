from statistics import mean, pstdev
from typing import Optional

WINDOW_DAYS = 30
RECENT_DAYS = 2
MIN_BASELINE_DAYS = 14
Z_THRESHOLD = 3.0
MIN_UPLIFT = 1.5
MIN_RECENT_UNITS = 2.0


def detect_spike(daily: list[float]) -> Optional[dict]:
    if len(daily) < RECENT_DAYS + MIN_BASELINE_DAYS:
        return None
    baseline, recent = daily[:-RECENT_DAYS], daily[-RECENT_DAYS:]
    base_mean = mean(baseline)
    spread = max(pstdev(baseline), 0.1 * base_mean, 1.0)
    recent_mean = mean(recent)
    z = (recent_mean - base_mean) / spread
    if z < Z_THRESHOLD or recent_mean < MIN_UPLIFT * base_mean or recent_mean < MIN_RECENT_UNITS:
        return None
    return {"baseline": round(base_mean, 1), "recent": round(recent_mean, 1), "z": round(z, 1),
            "uplift": round(recent_mean / max(base_mean, 0.1), 1)}
