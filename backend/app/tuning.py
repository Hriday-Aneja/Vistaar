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
