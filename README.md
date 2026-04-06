# PriceMap

Real estate property valuation for EU markets where automated tools don't exist or are severely limited: **Malta**, **Bulgaria**, **Cyprus**, and **Croatia**.

## What It Does

Users input an address and property characteristics (type, area, year built, condition, etc.) and receive an instant price estimate with a confidence range, comparable properties, and an interactive map.

## Tech Stack

- **Frontend**: Next.js 15 + TypeScript, Tailwind CSS, Leaflet maps
- **Backend**: Python 3.12, FastAPI, SQLAlchemy + GeoAlchemy2
- **Database**: PostgreSQL 16 + PostGIS 3.4
- **ML**: LightGBM + XGBoost ensemble (hedonic pricing model)
- **Data Pipeline**: Scrapy for listing scraping, custom importers for official statistics
- **Infrastructure**: Docker Compose, Redis, Celery

## Quick Start

```bash
# 1. Start services
docker compose up -d

# 2. Run database migrations
docker compose exec backend alembic upgrade head

# 3. Seed country data
docker compose exec backend python /app/scripts/seed_countries.py

# 4. Access the app
open http://localhost:3000     # Frontend
open http://localhost:8000/docs # API docs
```

## Project Structure

```
pricemap/
├── frontend/      # Next.js web application
├── backend/       # FastAPI REST API + ML inference
├── pipeline/      # Scrapy spiders + data importers
├── ml/            # Model training scripts + notebooks
├── infra/         # Nginx, PostgreSQL configs
├── scripts/       # Utility scripts (seeding, import)
└── docs/          # Research and architecture docs
```

## Data Sources

| Country | Transaction Data | Listing Data | Official Index |
|---------|-----------------|--------------|----------------|
| Malta | PPR (ppr.propertymalta.org) | PropertyMarket.com.mt | NSO RPPI |
| Bulgaria | - | Imot.bg | NSI HPI |
| Cyprus | - | Bazaraki, BuySell | CYSTAT HPI |
| Croatia | - | Nekretnine.hr, Njuskalo | DZS HPI |

## License

TBD
