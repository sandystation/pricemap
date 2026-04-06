# PriceMap -- System Architecture

## Overview

PriceMap has two operational layers:

1. **Data collection layer** (working now): Python scrapers that collect property listings into a file-based document store, with a dev dashboard for browsing.
2. **Production app layer** (scaffolded): Next.js frontend + FastAPI backend + PostgreSQL/PostGIS for the public-facing valuation tool.

```
 DATA COLLECTION (working)              PRODUCTION APP (scaffolded)
 ─────────────────────────              ──────────────────────────

 ┌──────────────────────┐               ┌──────────────┐
 │  run_scrapers.py     │               │  Next.js 15  │
 │  ├─ remax (API)      │               │  Frontend    │
 │  ├─ maltapark (HTML) │               │  (Leaflet)   │
 │  └─ imot_bg (HTML)   │               └──────┬───────┘
 └──────────┬───────────┘                      │ REST
            │                                  ▼
            ▼                            ┌──────────────┐
 ┌──────────────────────┐               │  FastAPI API  │
 │  DocStore            │               │  (PostGIS)    │
 │  (JSONL per source)  │               └──────┬───────┘
 │  ├─ mt_remax.jsonl   │                      │
 │  ├─ mt_maltapark.jsonl│              ┌──────┴───────┐
 │  └─ bg_imot.jsonl    │              │ PostgreSQL   │
 └──────────┬───────────┘              │ + PostGIS    │
            │                           └──────────────┘
            ▼
 ┌──────────────────────┐
 │  Dev Dashboard       │
 │  (FastAPI+Jinja2)    │
 │  localhost:8500      │
 └──────────────────────┘
```

## Data Collection Layer

### Document Store (`scripts/docstore.py`)

File-based, schema-free document database. Each source is a JSONL file (one JSON document per line).

**Key properties:**
- Lazy-loaded into memory as a `dict[_id, doc]` for O(1) lookups
- Automatic change detection: diffs tracked fields on re-scrape, appends history events
- Atomic writes via `.tmp` + `os.replace()` to prevent corruption
- Auto-flush every 100 operations
- Staleness check: `is_stale(doc_id, hours=20)` to avoid redundant re-scraping

**Tracked fields** (changes trigger history events):
`price_eur`, `price_per_sqm`, `area_sqm`, `bedrooms`, `bathrooms`, `rooms`, `property_type`, `locality`, `title`, `description`, `condition`, `is_active`, `price_original`, `address_raw`, `floor`, `total_floors`

**File layout:**
```
data/
  collections/
    mt_remax.jsonl          # ~32K docs (one per line)
    mt_maltapark.jsonl      # ~4K docs
    bg_imot.jsonl           # grows with city coverage
    _scrape_runs.jsonl      # scrape run metadata
  images/
    mt_remax/               # {external_id}_{n}.jpg
    mt_maltapark/
    bg_imot/
```

### Scrapers

| Script | Source | Method | Coverage | Key Fields |
|--------|--------|--------|----------|------------|
| `scrape_remax_mt.py` | RE/MAX Malta API | JSON API (`/api/properties`) | All Malta (32K+) | GPS, area, bedrooms, bathrooms, price, images |
| `scrape_maltapark.py` | MaltaPark | HTML scraping | Malta classifieds (~4K) | Description, images, price, agent, condition |
| `scrape_imot_bg.py` | Imot.bg | HTML + JSON-LD | 35 Bulgarian cities | Description, images, price, amenities, construction type, agent |

All scrapers:
- Use `httpx` for HTTP requests with browser-like headers
- Store results via `DocStore.save_property()` (handles dedup + history)
- Download property images to `data/images/{source}/`
- Respect rate limits (`DELAY = 2.0s` between requests)
- Are coordinated via `run_scrapers.py`

### Dev Dashboard (`scripts/dashboard/`)

FastAPI + Jinja2 + Tailwind CSS (via CDN). No build step.

| Route | Purpose |
|-------|---------|
| `/` | Collection stats, property counts, recent scrape runs |
| `/browse/{collection}` | Property grid with images, search, type/price filters, pagination |
| `/property/{collection}/{id}` | Full detail: image gallery, all parsed fields, history timeline, GPS link |
| `/search?q=...` | Cross-collection text search (title, locality, description, address) |
| `/stats` | Market stats by country, type, locality with distribution bars |
| `/image/{path}` | Local image file serving |

## Production App Layer

### Frontend (Next.js 15)

TypeScript, Tailwind CSS, shadcn/ui, react-leaflet.

| Route | Purpose |
|-------|---------|
| `/` | Landing page with country selector |
| `/[country]` | Interactive price heatmap |
| `/[country]/valuation` | Property form -> price estimate with comparables |

### Backend API (FastAPI)

| Endpoint | Purpose |
|----------|---------|
| `POST /api/v1/valuations/estimate` | ML-based property valuation |
| `GET /api/v1/properties/search` | Spatial bounding box search |
| `GET /api/v1/geocode` | Address -> coordinates (Nominatim, Redis-cached) |
| `GET /api/v1/stats/{country}` | Aggregate market statistics |
| `GET /api/v1/heatmap/{country}` | GeoJSON price heatmap data |

Uses SQLAlchemy + GeoAlchemy2 for PostGIS spatial queries. Requires PostgreSQL (via Docker Compose).

### ML Valuation Engine

- **Primary**: LightGBM hedonic pricing model (one per country)
- **Ensemble**: 70% LightGBM + 30% XGBoost
- **Confidence intervals**: Quantile regression (10th/90th percentiles)
- **Training**: 5-fold spatial cross-validation
- **Features**: structural (area, rooms, floor) + spatial (distance to coast/center, POI density) + temporal (HPI trend)
- **Fallback**: Comparable sales (inverse-distance weighted) when model confidence is low

### Confidence Scoring (0-100)

- Data density within 2km/12mo (40%)
- Feature completeness from user input (20%)
- Prediction interval width (25%)
- Data freshness (15%)

## Tech Stack

| Layer | Technology | Rationale |
|-------|-----------|-----------|
| Document Store | JSONL + orjson | Schema-free, file-based, 180ms load for 32K docs, no server needed |
| Scrapers | httpx + BeautifulSoup | Simple, async-capable, handles cookies/redirects |
| Dev Dashboard | FastAPI + Jinja2 + Tailwind CDN | Zero build step, hot reload |
| Frontend | Next.js 15 + TypeScript | SSR, App Router |
| Maps | react-leaflet + Leaflet.js | Free OSM tiles (no Mapbox billing) |
| Backend | Python 3.12 + FastAPI | Async, OpenAPI docs, ML ecosystem |
| Prod Database | PostgreSQL 16 + PostGIS 3.4 | Spatial indexing, geography types |
| ML | LightGBM + scikit-learn + SHAP | Best for tabular data, explainable |
| Infrastructure | Docker Compose | Single-server VPS deployment |

## Key Design Decisions

### Document store over relational DB for scraping

Property data is inherently semi-structured: each source has different fields, new fields appear as scrapers improve, and the schema should never block data collection. JSONL files are inspectable with any text editor, trivially portable, and need no server process. The production API still uses PostgreSQL -- a future `export_to_postgres.py` script bridges the two.

### Embedded history over separate changelog table

Each document carries its own history array. This means a single read gives the full picture of a property (current state + all changes). No joins needed. Storage cost is minimal: only changed fields are recorded, and most properties don't change between runs.

### httpx over Scrapy for scrapers

The Scrapy framework was initially planned but the working scrapers use plain httpx+BeautifulSoup. Reasons: simpler code (one file per scraper vs spider+pipeline+middleware), easier to debug, and the three target sites don't need Scrapy's concurrency -- they require polite delays anyway. The `pipeline/` directory contains legacy Scrapy stubs.

### Staleness checks over skip-existing

When a scraper encounters a property it has seen before, it checks `last_seen` instead of skipping. If the property was seen within 20 hours, it's skipped (no wasted HTTP request). Otherwise, the detail page is re-fetched and diffed against the stored version. This enables change detection on re-runs without re-scraping everything every time.
