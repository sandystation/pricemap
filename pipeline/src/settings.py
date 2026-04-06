import os

BOT_NAME = "pricemap"
SPIDER_MODULES = ["src.spiders"]
NEWSPIDER_MODULE = "src.spiders"

# Crawl responsibly
ROBOTSTXT_OBEY = True
CONCURRENT_REQUESTS = 8
DOWNLOAD_DELAY = 1.5  # Be respectful to target sites

# Retry
RETRY_TIMES = 3
RETRY_HTTP_CODES = [500, 502, 503, 504, 408, 429]

# User agent
USER_AGENT = "PriceMap Research Bot (+https://github.com/sandystation/pricemap)"

# Pipelines
ITEM_PIPELINES = {
    "src.pipelines.cleaning.CleaningPipeline": 100,
    "src.pipelines.geocoding.GeocodingPipeline": 200,
    "src.pipelines.deduplication.DeduplicationPipeline": 300,
    "src.pipelines.price_adjustment.PriceAdjustmentPipeline": 400,
    "src.pipelines.persistence.PersistencePipeline": 500,
}

# Database
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://pricemap:pricemap_dev@localhost:5432/pricemap",
)

# Geocoding
NOMINATIM_USER_AGENT = "pricemap/0.1"

# Asking-to-transaction adjustment factors
ADJUSTMENT_FACTORS = {
    "MT": 0.97,
    "BG": 0.93,
    "CY": 0.94,
    "HR": 0.93,
}

# BGN to EUR fixed rate (Bulgaria joining eurozone)
BGN_EUR_RATE = 1 / 1.95583

# Logging
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s [%(name)s] %(levelname)s: %(message)s"

# Auto-throttle
AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 1
AUTOTHROTTLE_MAX_DELAY = 10
AUTOTHROTTLE_TARGET_CONCURRENCY = 2.0
