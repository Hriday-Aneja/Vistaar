SHORTAGE_COVER_DAYS = 5
WEIGHTS = {"distance": 25, "expiry": 30, "demand": 25, "margin": 20}


def clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def score_swap(distance_km: float, radius_km: float, days_left: int, cover_days: float,
               fill: float, margin_pct: float) -> tuple[float, list[dict]]:
    shortage = clamp(1 - cover_days / SHORTAGE_COVER_DAYS)
    parts = {
        "distance": (clamp(1 - distance_km / radius_km), "Doori", f"{distance_km:.2f} km door"),
        "expiry": (clamp(1 - min(days_left, 30) / 30), "Expiry ka dabaav", f"{days_left} din bache"),
        "demand": (clamp(0.6 * shortage + 0.4 * fill), "Maang",
                   f"{cover_days:.1f} din ka stock, zaroorat ka {fill * 100:.0f}% poora hoga"),
        "margin": (clamp(margin_pct / 0.3), "Margin", f"{margin_pct * 100:.0f}% margin"),
    }
    breakdown = []
    for key, (value, label, detail) in parts.items():
        weight = WEIGHTS[key]
        breakdown.append({"factor": key, "label": label, "detail": detail, "score": round(value, 2),
                          "weight": weight, "points": round(value * weight, 1)})
    return round(sum(item["points"] for item in breakdown), 1), breakdown
