from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    environment: str = "development"
    database_url: str = "postgresql+asyncpg://pricemap:pricemap_dev@localhost:5432/pricemap"
    redis_url: str = "redis://localhost:6379/0"

    # API
    api_v1_prefix: str = "/api/v1"
    cors_origins: list[str] = ["http://localhost:3000"]
    # Public API host; used for TrustedHost validation in production. Set via the
    # API_DOMAIN env var (also consumed by Caddy).
    api_domain: str = "localhost"
    # Number of trusted reverse-proxy hops in front of the app. The real client
    # IP is read this many entries from the RIGHT of X-Forwarded-For (the hop the
    # trusted proxy actually observed), never the client-supplied left-most token.
    trusted_proxy_count: int = 1

    # Geocoding
    nominatim_user_agent: str = "pricemap/0.1"
    geocode_cache_ttl: int = 86400 * 30  # 30 days

    # Valuation
    default_confidence_threshold: float = 30.0
    comparable_radius_km: float = 2.0
    comparable_max_count: int = 10
    model_artifacts_dir: str = "/app/ml_artifacts"
    enriched_valuation_ttl_seconds: int = 86400
    valuation_upload_dir: str = "/tmp/pricemap-valuation-uploads"
    valuation_max_upload_images: int = 10
    valuation_max_upload_bytes: int = 8 * 1024 * 1024
    valuation_max_upload_total_bytes: int = 40 * 1024 * 1024
    valuation_description_max_chars: int = 6000
    valuation_rate_limit_hour: int = 5
    valuation_rate_limit_day: int = 20
    valuation_max_active_jobs: int = 25
    # Global hard ceiling on accepted enriched valuations per day, independent of
    # client identity. Bounds total paid Gemini/Nominatim spend even if per-client
    # rate limiting is evaded.
    valuation_global_daily_cap: int = 500

    # Runtime LLM enrichment
    llm_provider: str = "google"
    llm_model: str = "gemini-3.1-flash-lite-preview"

    # Asking-to-transaction adjustment defaults
    adjustment_factors: dict[str, float] = {
        "MT": 0.97,  # Malta: PPR data available, small adjustment
        "BG": 0.93,  # Bulgaria: larger gap, asking-price heavy
        "CY": 0.94,  # Cyprus: Phase 2
        "HR": 0.93,  # Croatia: Phase 2
    }

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


settings = Settings()
