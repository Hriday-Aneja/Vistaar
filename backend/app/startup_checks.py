"""Startup checks and config parsing. Stdlib only."""

KNOWN_DEFAULT_SECRETS = {"", "vistaar-demo-secret-change-me", "change-me-too", "change-me"}
RELAXED_ENVS = {"dev", "test"}
MIN_SECRET_LEN = 16
DEFAULT_ORIGIN = "http://localhost:3000"


def secret_problems(env: str, phone_secret: str) -> list[str]:
    """Outside dev/test the app must not run with a known or short secret for the customer-phone hash."""
    if (env or "").strip().lower() in RELAXED_ENVS:
        return []
    if phone_secret in KNOWN_DEFAULT_SECRETS or len(phone_secret) < MIN_SECRET_LEN:
        return [f"VISTAAR_PHONE_SECRET is a default or shorter than {MIN_SECRET_LEN} characters"]
    return []


def parse_origins(raw: str) -> list[str]:
    """CORS_ORIGINS is a comma-separated list. Trailing slashes are dropped (browsers send none)."""
    origins = [o.strip().rstrip("/") for o in (raw or "").split(",") if o.strip()]
    return origins or [DEFAULT_ORIGIN]