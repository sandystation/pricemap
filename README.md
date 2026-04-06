# PriceMap

Real estate property valuation for EU markets where automated tools don't exist or are severely limited: **Malta**, **Bulgaria**, **Cyprus**, and **Croatia**.

## What It Does

Users input an address and property characteristics (type, area, year built, condition, etc.) and receive an instant price estimate with a confidence range, comparable properties, and an interactive map.

## Current Status

**Data collection is live.** Three scrapers are actively collecting property listings:

| Source | Country | Listings | Data | Method |
|--------|---------|----------|------|--------|
| RE/MAX Malta | MT | 32,000+ available | GPS, area, bedrooms, bathrooms, price, images | JSON API |
| MaltaPark | MT | ~4,000 | descriptions, images, prices, agent info | HTML scraping |
| Imot.bg | BG | thousands across 35 cities | descriptions, images, prices, agent info, amenities | HTML + JSON-LD |

Properties are stored as JSON documents with embedded change history (price changes, description edits tracked automatically across scrape runs).

## Quick Start

### 1. Run scrapers (no Docker needed)

```bash
# Install Python dependencies
cd backend && pip install -e . && cd ..

# Run all scrapers
cd scripts && python run_scrapers.py

# Or run one at a time
python run_scrapers.py remax         # RE/MAX Malta (32K listings, ~12 min)
python run_scrapers.py maltapark     # MaltaPark (~4K listings)
python run_scrapers.py imot          # Imot.bg (35 Bulgarian cities)

# Check status
python run_scrapers.py --status
```

### 2. Browse data with the dev dashboard

```bash
cd scripts && python -m dashboard.app
# Open http://localhost:8500
```

Dashboard features: property grid with images, search, filters (type/price/sort), property detail pages with all parsed fields, change history timeline, market statistics.

### 3. View data from CLI

```bash
cd scripts
python view_data.py                          # Summary stats
python view_data.py --price-drops            # Properties with price decreases
python view_data.py --longest-listed         # Days on market ranking
python view_data.py --property mt_remax:ID   # Full history for one property
```

### 4. Run the full-stack app (Docker)

```bash
docker compose up -d
# Frontend: http://localhost:3000
# API docs: http://localhost:8000/docs
```

## Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Data Store | JSONL document store (`scripts/docstore.py`) | Schema-free property storage with change tracking |
| Scrapers | httpx + BeautifulSoup | RE/MAX API, MaltaPark HTML, Imot.bg HTML+JSON-LD |
| Dev Dashboard | FastAPI + Jinja2 + Tailwind | Browse, search, inspect scraped data at localhost:8500 |
| Frontend | Next.js 15 + TypeScript + Leaflet | Production web app with interactive maps |
| Backend API | Python 3.12 + FastAPI | Valuation API with spatial queries |
| Database (prod) | PostgreSQL 16 + PostGIS 3.4 | Production database with spatial indexing |
| ML | LightGBM + XGBoost | Hedonic pricing model for property valuation |
| Infrastructure | Docker Compose | Single-server VPS deployment |

## Project Structure

```
pricemap/
├── scripts/               # Scrapers, data tools, dev dashboard
│   ├── docstore.py        # JSONL document store engine
│   ├── run_scrapers.py    # Run all/selected scrapers
│   ├── scrape_remax_mt.py # RE/MAX Malta (JSON API, 32K listings)
│   ├── scrape_maltapark.py# MaltaPark (HTML, ~4K listings)
│   ├── scrape_imot_bg.py  # Imot.bg (HTML+JSON-LD, 35 cities)
│   ├── view_data.py       # CLI data viewer + history queries
│   ├── dashboard/         # FastAPI dev dashboard (localhost:8500)
│   └── scraper_base.py    # Shared HTTP client, image downloader
├── data/                  # Generated data (gitignored)
│   ├── collections/       # JSONL document files per source
│   └── images/            # Downloaded property photos
├── frontend/              # Next.js 15 web application
├── backend/               # FastAPI REST API + ML inference
├── pipeline/              # Scrapy spiders (legacy stubs)
├── ml/                    # Model training scripts + notebooks
├── infra/                 # Nginx, PostgreSQL configs
└── docs/                  # Research, architecture, TODOs
```

## Data Sources

| Country | Working Scrapers | Blocked (needs browser) | Official Index |
|---------|-----------------|------------------------|----------------|
| Malta | RE/MAX API (32K), MaltaPark (4K) | PropertyMarket.com.mt (403), Frank Salt, Dhalia | NSO RPPI |
| Bulgaria | Imot.bg (35 cities) | — | NSI HPI |
| Cyprus | — (Phase 2) | Bazaraki, BuySell | CYSTAT HPI |
| Croatia | — (Phase 2) | Nekretnine.hr, Njuskalo | DZS HPI |

## Document Model

Each property is a self-contained JSON document with embedded history:

```json
{
  "_id": "mt_remax:240271042-233",
  "source": "mt_remax",
  "country": "MT",
  "first_seen": "2026-04-06T10:00:00Z",
  "last_seen": "2026-04-06T14:30:00Z",
  "current": {
    "title": "Apartment in Sliema",
    "price_eur": 490000,
    "area_sqm": 103,
    "bedrooms": 3,
    "locality": "Sliema",
    "lat": 35.912, "lon": 14.499,
    "image_urls": ["..."],
    "description": "..."
  },
  "history": [
    {"date": "2026-04-06", "event": "created"},
    {"date": "2026-04-20", "event": "price_change",
     "changes": {"price_eur": {"old": 520000, "new": 490000}}}
  ]
}
```

No schema migrations needed. New fields from scrapers are stored automatically. Price changes, description edits, and deactivations are tracked across runs.

## License

TBD
