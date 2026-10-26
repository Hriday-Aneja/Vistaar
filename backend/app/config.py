from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Vistaar"
    env: str = "dev"

    # Postgres in Docker. For quick local runs: DATABASE_URL=sqlite:///./vistaar.db
    database_url: str = "postgresql+psycopg://vistaar:vistaar@db:5432/vistaar"
    redis_url: str = "redis://redis:6379/0"
    jwt_secret: str = "change-me"

    gemini_api_key: str = ""
    groq_api_key: str = ""
    sarvam_api_key: str = ""

    # Deterministic guardrails: the LLM never overrides these.
    k_anonymity_min: int = 5
    dp_epsilon: float = 1.0
    min_margin_pct: float = 8.0
    max_discount_pct: float = 15.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
