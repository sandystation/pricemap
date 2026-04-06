from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    environment: str = "development"
    database_url: str = "postgresql+asyncpg://pricemap:pricemap_dev@localhost:5432/pricemap"
    redis_url: str = "redis://localhost:6379/0"

    # API
    api_v1_prefix: str = "/api/v1"
    cors_origins: list[str] = ["http://localhost:3000"]

    # Geocoding
    nominatim_user_agent: str = "pricemap/0.1"
    geocode_cache_ttl: int = 86400 * 30  # 30 days

    # Valuation
    default_confidence_threshold: float = 30.0
    comparable_radius_km: float = 2.0
    comparable_max_count: int = 10

    # Asking-to-transaction adjustment defaults
    adjustment_factors: dict[str, float] = {
        "MT": 0.97,  # Malta: PPR data available, small adjustment
        "BG": 0.93,  # Bulgaria: larger gap, asking-price heavy
        "CY": 0.94,  # Cyprus: Phase 2
        "HR": 0.93,  # Croatia: Phase 2
    }

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
