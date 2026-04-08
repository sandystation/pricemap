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

### Data Quality & Enrichment
```bash
cd scripts
python enrich_remax_mt.py              # Fetch descriptions from RE/MAX detail API
python dedup_remax.py --apply          # Mark duplicate RE/MAX listings
python flag_suspicious.py              # Flag suspicious docs (for LLM review)
python flag_suspicious.py --stats      # Show flag distribution only
```

### Valuation Models
```bash
cd scripts
python train_valuation.py --listing-type sale          # Train apartment sales model
python train_valuation.py --listing-type rent           # Train apartment rent model
python train_valuation.py --listing-type sale --dry-run  # Show data stats only
python train_valuation.py --listing-type sale --property-type penthouse  # Other types
# Artifacts saved to ml/artifacts/
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
                                           → train_valuation.py → ml/artifacts/ (LGB+XGB models)
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
| `scrape_remax_mt.py` | RE/MAX Malta | JSON API at `/api/properties` | 32K+ listings (sales + rentals) with GPS |
| `scrape_maltapark.py` | MaltaPark | Server-rendered HTML | ~4K sales listings with descriptions |
| `scrape_imot_bg.py` | Imot.bg | HTML + JSON-LD, windows-1251 encoding | 35 Bulgarian cities |

Each scraper: builds a record dict → calls `coll.save_property(record)` → downloads images to `data/images/{source}/`. Shared utilities in `scraper_base.py`.

All scrapers store the raw source data in a `raw_data` field (API response for RE/MAX, parsed listing+detail dicts for HTML scrapers). RE/MAX also has `raw_data_detail` from the enrichment script's detail API call.

### Data Quality Pipeline (`scripts/flag_suspicious.py`, `scripts/dedup_remax.py`, `scripts/enrich_remax_mt.py`)

**Enrichment**: `enrich_remax_mt.py` fetches the RE/MAX detail API (`/api/properties/{MLS}`) to add descriptions, features, room dimensions, agent info, and all photos. Safe to Ctrl+C; re-run skips already-enriched docs.

**Deduplication**: `dedup_remax.py` groups listings by price + area + description (first 100 chars). Marks duplicates with `duplicate_of` pointing to the canonical doc. Dashboard hides duplicates by default.

**Suspicion flagging**: `flag_suspicious.py` adds a `suspicious` list field to every doc. Empty list = clean; non-empty = reasons for review. Intended for downstream LLM post-processing. Flag types:

| Flag | Meaning |
|------|---------|
| `price_extreme_high` | Price > €10M (possibly phone number) |
| `price_placeholder` | Sale price < €100 |
| `price_suspiciously_low` | Sale < €1K for non-parking/land |
| `price_title_mismatch:XvsY` | Title contains a different price than stored |
| `price_locality_outlier_high/low` | Price >50x or <1% of locality median |
| `price_per_sqm_extreme_high/low` | Price/sqm outside reasonable range |
| `price_on_request` | Text instead of number in price field |
| `price_zero_or_negative` | Price ≤ 0 |
| `area_too_small` | < 5 sqm for non-parking |
| `area_too_large` | > 50K sqm for non-land |
| `wanted_ad` | Buyer-wanted listing, not a property |
| `duplicate` | Marked as duplicate of another listing |
| `type_unknown` | Property type classified as "other" |
| `no_price` | No price data at all |
| `no_title` | Missing title |

### Dev Dashboard (`scripts/dashboard/`)
FastAPI + Jinja2 + Tailwind CDN at port 8500. Routes: `/` (home), `/browse/{collection}` (grid+filters), `/property/{collection}/{id}` (detail+history), `/search` (cross-collection), `/stats` (market analytics). Images served via `/image/{path}`.

Uses Starlette 1.0 API: `templates.TemplateResponse(request, "name.html", context)` — request is the first arg, NOT inside the context dict.

### Production Backend (`backend/src/`)
FastAPI app requiring PostgreSQL+PostGIS. SQLAlchemy+GeoAlchemy2 models with spatial queries (`ST_DWithin`, `ST_Distance`). Not connected to DocStore yet — needs an `export_to_postgres` bridge.

API: `POST /api/v1/valuations/estimate`, `GET /api/v1/properties/search`, `GET /api/v1/geocode`, `GET /api/v1/stats/{country}/heatmap`.

### Frontend (`frontend/src/`)
Next.js 15 App Router. Pages: `/` (country selector), `/[country]` (heatmap), `/[country]/valuation` (form+results). Leaflet maps loaded via `dynamic()` import (no SSR). Uses Tailwind v4 with `@tailwindcss/postcss`.

### ML — Valuation Models (`scripts/train_valuation.py`, `ml/`)

Two model pipelines exist:

- **Working**: `scripts/train_valuation.py` trains from DocStore JSONL directly. LightGBM + XGBoost ensemble (0.7/0.3 weights), spatial cross-validation (5 geographic folds by latitude), log-transformed target. Separate models for sales vs rents. Excludes docs with `suspicious` flags or `duplicate_of`. Artifacts saved to `ml/artifacts/`.
- **Scaffolded**: `ml/src/train.py` trains from PostgreSQL (not yet connected to DocStore). Same ensemble approach but different feature set.

**Features used** (19 total): lat, lon, area_sqm, bedrooms, bathrooms, rooms, total_int_area, total_ext_area, 8 boolean amenities (extracted from RE/MAX `features` list), locality (target-encoded), province (target-encoded). Missing values passed as NaN — LightGBM/XGBoost handle them natively. Rental area_sqm is only 19% populated but still ranks as a top feature.

**Artifacts per model** (in `ml/artifacts/`): `{prefix}_lgb_v{date}.joblib`, `{prefix}_xgb_v{date}.joblib`, `{prefix}_encoders_v{date}.joblib` (locality/province target encoding maps), `{prefix}_meta_v{date}.json` (metrics, feature importance, config).

## Important Gotchas

- **Scripts must run from `scripts/` directory** — all scraper modules use relative imports (`from docstore import ...`, `from scraper_base import ...`). Always `cd scripts` before running any script.
- **`save_property()` contract** — the data dict passed to `Collection.save_property()` must have `source` and `external_id` keys. The `country_code` key is popped from the dict and stored at the document level, not inside `current`.
- **Backend tests need PostgreSQL** — `pytest tests/` fails without a running database. The ML feature tests (`tests/test_ml/test_features.py`) work standalone without any database. Run just those with `pytest tests/test_ml/ -v` for quick validation.
- **`orjson` is required** — DocStore uses `orjson` (not stdlib `json`) for JSONL serialization. It's installed globally but not declared in any requirements file. If setting up a fresh env: `pip install orjson`.
- **Alembic migrations don't exist yet** — `backend/alembic/versions/` is empty. The schema is defined in SQLAlchemy models but no migration has been generated.

## Key Technical Details

- **Imot.bg encoding**: `windows-1251`, not UTF-8. Always set `resp.encoding = "windows-1251"`.
- **RE/MAX API**: List endpoint wraps response in `{"data": {"Properties": [...], "TotalSearchResults": N}}`. Price is a string. `TransactionTypeId` param is ignored — always returns all listings (sales + rentals). Use `TransactionType` string field to distinguish. Detail endpoint at `/api/properties/{MLS}` returns descriptions, features, rooms, agent info. Base URL is `remax-malta.com` (no `www` — redirects to non-www).
- **RE/MAX listing URLs**: `https://remax-malta.com/listings/{MLS}` (not `/property-details/`).
- **Imot.bg JSON-LD bug**: The `itemOffered.name` field in JSON-LD says "Дава под Наем" (for rent) even on sales pages. Use the HTML `<h1>` tag for the title instead.
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
