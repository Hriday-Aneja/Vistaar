"""Plain, dependency-free tuning constants (env-overridable).

Kept separate from config.py (pydantic Settings for infra/secrets) so the pure
business-logic modules and their unit tests never need pydantic or a database.
"""
import os


def _flag(name: str, default: str = "0") -> bool:
    return os.getenv(name, default).strip().lower() in ("1", "true", "yes", "on")


OCR_ENABLED = _flag("VISTAAR_OCR")
WHATSAPP_ENABLED = _flag("VISTAAR_WHATSAPP")
SESSION_HOURS = int(os.getenv("VISTAAR_SESSION_HOURS", "72"))
NEARBY_RADIUS_KM = float(os.getenv("VISTAAR_NEARBY_KM", "3"))
FORECAST_WINDOW_DAYS = int(os.getenv("VISTAAR_FORECAST_DAYS", "14"))
INFERENCE_HORIZON_DAYS = int(os.getenv("VISTAAR_INFERENCE_HORIZON", "30"))
PHONE_SECRET = os.getenv("VISTAAR_PHONE_SECRET", "vistaar-demo-secret-change-me")

# Bulk-buy
BULK_HORIZON_DAYS = int(os.getenv("VISTAAR_BULK_HORIZON", "14"))
SOLO_PRICE_RATIO = 0.92  # ASSUMPTION used only for the savings estimate: a lone kirana pays ~92% of MRP


# Login and registration limits (per process, see services/rate_limit.py)
LOGIN_MAX_FAILURES = int(os.getenv("VISTAAR_LOGIN_MAX_FAILURES", "5"))  # wrong passwords per phone in the window
LOGIN_MAX_FAILURES_PER_IP = int(os.getenv("VISTAAR_LOGIN_MAX_FAILURES_PER_IP", "100"))  # generous: proxies share one IP
LOGIN_WINDOW_S = int(os.getenv("VISTAAR_LOGIN_WINDOW_S", "900"))
REGISTER_MAX_PER_IP = int(os.getenv("VISTAAR_REGISTER_MAX_PER_IP", "20"))
REGISTER_WINDOW_S = int(os.getenv("VISTAAR_REGISTER_WINDOW_S", "3600"))

# ML forecast (services/ml_forecast.py). The model only suggests; shop_needs clamps it to this band around the
# rule-based horizon demand and still subtracts stock on hand.
ML_FORECAST_ENABLED = _flag("VISTAAR_ML_FORECAST", "1")
ML_MIN_HISTORY_DAYS = int(os.getenv("VISTAAR_ML_MIN_HISTORY", "30"))
ML_MIN_RATIO = 0.4
ML_MAX_RATIO = 2.5
ML_SEED = 42

# Live alerts over Redis Pub/Sub (services/alert_bus.py). Off = nothing is published; the frontend polls instead.
ALERTS_REDIS_ENABLED = _flag("VISTAAR_ALERTS_REDIS", "1")

# LLM router use (services/llm.py). The LLM only classifies chat messages and words khata reminder drafts.
LLM_TIMEOUT_S = float(os.getenv("VISTAAR_LLM_TIMEOUT", "5"))
LLM_INTENT_PER_MIN = int(os.getenv("VISTAAR_LLM_INTENT_PER_MIN", "20"))  # per user; above this the keyword router answers
