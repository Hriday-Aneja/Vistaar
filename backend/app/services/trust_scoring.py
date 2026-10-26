def clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def score_risk(repay_ratio: float, overdue_days: float, other_pending: float) -> tuple[float, str, list[str]]:
    score = 0.45 * (1 - clamp(repay_ratio)) + 0.30 * clamp(overdue_days / 60) + 0.25 * clamp(other_pending / 3000)
    level = "High" if score >= 0.55 else "Medium" if score >= 0.30 else "Low"
    reasons = [
        f"Doosri dukaanon me udhaar ka lagbhag {repay_ratio * 100:.0f}% wapas aaya hai.",
        f"Sabse purana baaki lagbhag {overdue_days:.0f} din se pending hai.",
        f"Doosri dukaanon me lagbhag Rs {other_pending:.0f} baaki hai.",
    ]
    return round(score, 2), level, reasons


def suggested_limit(score: float, other_pending: float, own_pending: float) -> tuple[int, int]:
    ceiling = max(0.0, 3000 * (1 - score) - 0.5 * other_pending)
    limit = int(ceiling // 100 * 100)
    return limit, max(0, limit - int(own_pending))
