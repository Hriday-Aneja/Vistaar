"""Plain-language reason for a bulk-buy quantity. Rule-based: it explains the arithmetic, it is not an ML model."""

FORECAST_METHOD = "rule-based: average daily sales x horizon x festival factor, minus stock (not ML)"


def explain_need(rate: float, stock: int, horizon_days: int, multiplier: float, need: int) -> str:
    parts = [f"Roz ~{rate:g} bikta hai"]
    if rate > 0:
        parts.append(f"stock {stock} bacha hai, ~{stock / rate:.0f} din chalega")
    if multiplier > 1:
        parts.append(f"tyohaar ke liye {round((multiplier - 1) * 100)}% zyada maang maani (demo assumption)")
    parts.append(f"isliye {horizon_days} din ke liye {need} aur chahiye")
    return ", ".join(parts)