# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

PriceMap is a real estate valuation platform for EU markets where automated tools don't exist: Malta, Bulgaria, Cyprus, Croatia. It has two layers:

- **Data collection (working)**: Python scrapers → JSONL document store → dev dashboard at localhost:8500
- **Production app (scaffolded)**: Next.js frontend + FastAPI backend + PostgreSQL/PostGIS (via Docker Compose)

## Common Commands

### Scrapers & Data
```bash
cd scripts
python run_scrapers.py                # Run all scrapers (remax, maltapark, imot)
python run_scrapers.py remax          # Run one scraper
python run_scrapers.py --status       # Show collection stats + recent runs
python view_data.py                   # CLI data summary
python view_data.py --price-drops     # Price change analysis
python view_data.py --property ID     # Full history for one doc
```

### Dev Dashboard
```bash
./dev-dashboard.sh                    # Or: cd scripts && python -m dashboard.app
# Runs at http://localhost:8500
```

### Backend (Python/FastAPI)
```bash
cd backend
pip install -e ".[dev]"               # Install with dev deps (pytest, ruff, mypy)
ruff check src/                       # Lint
mypy src/ --ignore-missing-imports    # Type check
pytest tests/ -v                      # Run tests
pytest tests/test_ml/test_features.py # Single test file
uvicorn src.main:app --reload         # Run API (needs PostgreSQL via Docker)
```

### Frontend (Next.js)
```bash
cd frontend
npm install                           # Install deps
npm run lint                          # ESLint
npm run type-check                    # tsc --noEmit
npm run build                         # Production build
npm run dev                           # Dev server at localhost:3000
```

### Docker (full stack)
```bash
docker compose up -d                  # Start all services
docker compose up -d postgres redis   # Just the databases
```

### Tests
```bash
cd scripts
python test_dashboard.py              # 35 Playwright e2e tests (starts its own server)
python -m pytest ../backend/tests/ -v # Backend unit tests (needs PostgreSQL)
```

## Architecture

### Data Flow
```
Scrapers (httpx) → DocStore (JSONL files) → Dev Dashboard (FastAPI+Jinja2)
                                           → [future] export_to_postgres → Production API
```

### Document Store (`scripts/docstore.py`)
File-based, schema-free storage. Each source is a `.jsonl` file in `data/collections/`. Documents are loaded into memory as `dict[_id, doc]` for O(1) lookups.

Every property is a self-contained document:
```json
{
  "_id": "mt_remax:240271042-233",
  "source": "mt_remax", "country": "MT",
  "first_seen": "...", "last_seen": "...",
  "current": { "price_eur": 490000, "area_sqm": 103, "locality": "Sliema", ... },
  "history": [ {"event": "created", ...}, {"event": "price_change", "changes": {...}} ]
}
```

Key behaviors:
- `Collection.save_property(data)` diffs tracked fields and auto-creates history events
- Auto-flush every 100 ops; atomic writes via `.tmp` + `os.replace()`
- `is_stale(doc_id, hours=20)` for efficient re-scraping
- New field values are always written to `current` even when no tracked change is detected

### Scrapers (`scripts/scrape_*.py`)
Three working scrapers, all using `httpx` + `BeautifulSoup`:

| Script | Source | Method | Scale |
|--------|--------|--------|-------|
| `scrape_remax_mt.py` | RE/MAX Malta | JSON API at `/api/properties` | 32K+ listings with GPS |
| `scrape_maltapark.py` | MaltaPark | Server-rendered HTML | ~4K listings with descriptions |
| `scrape_imot_bg.py` | Imot.bg | HTML + JSON-LD, windows-1251 encoding | 35 Bulgarian cities |

Each scraper: builds a record dict → calls `coll.save_property(record)` → downloads images to `data/images/{source}/`. Shared utilities in `scraper_base.py`.

### Dev Dashboard (`scripts/dashboard/`)
FastAPI + Jinja2 + Tailwind CDN at port 8500. Routes: `/` (home), `/browse/{collection}` (grid+filters), `/property/{collection}/{id}` (detail+history), `/search` (cross-collection), `/stats` (market analytics). Images served via `/image/{path}`.

Uses Starlette 1.0 API: `templates.TemplateResponse(request, "name.html", context)` — request is the first arg, NOT inside the context dict.

### Production Backend (`backend/src/`)
FastAPI app requiring PostgreSQL+PostGIS. SQLAlchemy+GeoAlchemy2 models with spatial queries (`ST_DWithin`, `ST_Distance`). Not connected to DocStore yet — needs an `export_to_postgres` bridge.

API: `POST /api/v1/valuations/estimate`, `GET /api/v1/properties/search`, `GET /api/v1/geocode`, `GET /api/v1/stats/{country}/heatmap`.

### Frontend (`frontend/src/`)
Next.js 15 App Router. Pages: `/` (country selector), `/[country]` (heatmap), `/[country]/valuation` (form+results). Leaflet maps loaded via `dynamic()` import (no SSR). Uses Tailwind v4 with `@tailwindcss/postcss`.

### ML (`ml/src/`)
LightGBM + XGBoost ensemble trained per country. `python -m src.train --country MT`. Spatial cross-validation (geographic folds). Model artifacts saved as `.joblib`.

## Important Gotchas

- **Scripts must run from `scripts/` directory** — all scraper modules use relative imports (`from docstore import ...`, `from scraper_base import ...`). Always `cd scripts` before running any script.
- **`save_property()` contract** — the data dict passed to `Collection.save_property()` must have `source` and `external_id` keys. The `country_code` key is popped from the dict and stored at the document level, not inside `current`.
- **Backend tests need PostgreSQL** — `pytest tests/` fails without a running database. The ML feature tests (`tests/test_ml/test_features.py`) work standalone without any database. Run just those with `pytest tests/test_ml/ -v` for quick validation.
- **`orjson` is required** — DocStore uses `orjson` (not stdlib `json`) for JSONL serialization. It's installed globally but not declared in any requirements file. If setting up a fresh env: `pip install orjson`.
- **Alembic migrations don't exist yet** — `backend/alembic/versions/` is empty. The schema is defined in SQLAlchemy models but no migration has been generated.

## Key Technical Details

- **Imot.bg encoding**: `windows-1251`, not UTF-8. Always set `resp.encoding = "windows-1251"`.
- **RE/MAX API**: Wraps response in `{"data": {"Properties": [...], "TotalSearchResults": N}}`. Price is a string.
- **Jinja2 filters**: `format_eur` and `format_sqm` must handle Jinja2 `Undefined` objects (not just `None`) since some docs lack price/area.
- **FastAPI query params**: Use `str` type for optional numeric params (min_price, max_price) that HTML forms send as empty strings — `float` type rejects `""`.
- **DocStore tracked fields**: `price_eur`, `price_per_sqm`, `area_sqm`, `bedrooms`, `bathrooms`, `rooms`, `title`, `description`, `locality`, `condition`, `is_active`, and more. Changes to these create history events; changes to other fields are stored silently.
- **BGN→EUR**: Fixed rate `1 / 1.95583` (Bulgaria eurozone accession).

## Data on Disk

```
data/
  collections/          # JSONL document files (gitignored)
    mt_remax.jsonl      # ~32K docs
    mt_maltapark.jsonl  # ~4K docs
    bg_imot.jsonl       # grows with city count
    _scrape_runs.jsonl  # scrape run metadata
  images/               # Downloaded property photos (gitignored)
    mt_remax/           # {external_id}_{n}.jpg
    mt_maltapark/
    bg_imot/
```

## Documentation

The `docs/` folder contains detailed documentation beyond this file:

- `docs/architecture.md` — System architecture diagrams, tech stack rationale, design decisions
- `docs/TODO.md` — Active issues, bugs found in testing, remaining work with effort estimates
- `docs/scraping-lessons.md` — Anti-scraping defenses, JSON API discovery tips, encoding gotchas, price parsing pitfalls, pagination patterns, data completeness matrix by source
- `docs/research/data-sources-malta.md` — Malta: tested API endpoints, HTML selectors, blocked sites, what each source provides
- `docs/research/data-sources-bulgaria.md` — Bulgaria: Imot.bg selectors, JSON-LD structure, 35 city slugs, encoding details
- `docs/research/data-sources-cyprus.md` — Cyprus data sources (Phase 2, not yet scraped)
- `docs/research/data-sources-croatia.md` — Croatia data sources (Phase 2, not yet scraped)
- `docs/research/market-overview.md` — EU-wide AVM landscape, why these 4 countries are underserved

## Blocked Data Sources

PropertyMarket.com.mt (403), Frank Salt (Cloudflare WAF), Dhalia (Cloudflare challenge), Malta PPR (paid auth with MFA). See `docs/scraping-lessons.md` for details.

## Legacy Code

`pipeline/` contains Scrapy spider stubs written before actual site inspection — they don't work. The working scrapers are in `scripts/`. `scripts/setup_db.py` and `data/pricemap.db` are from the original SQLite approach, now superseded by DocStore.
