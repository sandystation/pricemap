# PriceMap -- Issues & Remaining Work

Updated 2026-04-06 after document store migration and scraper expansion.

---

## Resolved Since Last Audit

- ~~Scrape run tracking bug~~ -- Replaced SQLite with DocStore; auto-flush every 100 ops prevents data loss on kill.
- ~~Pipeline vs scripts mismatch~~ -- Decision made: `scripts/` scrapers are the source of truth. `pipeline/` contains legacy stubs (can be removed).
- ~~Too few properties (499)~~ -- Scraper caps removed. RE/MAX uncapped (32K available), MaltaPark paginates all pages, Imot.bg expanded to 35 cities.
- ~~No history tracking~~ -- DocStore diffs tracked fields on every re-scrape. Price changes, description edits, deactivations recorded in embedded `history` array.
- ~~SQLite schema rigidity~~ -- Migrated to schema-free JSONL document store. No ALTER TABLE ever needed.

---

## Data Quality Gaps

### BG_IMOT: 0% area and 0% coordinates

121 Bulgarian properties have prices, descriptions, images, agent info -- but **area_sqm and lat/lon are all NULL**.

**Area** (partially addressed): The Imot.bg scraper now tries to extract area from the search results `div.info` text as a fallback (`scrape_imot_bg.py`, `scrape_city` function). However, the regex may still miss some formats. Needs validation on a fresh scrape to see if area coverage improves.

**Coordinates**: Imot.bg doesn't expose lat/lon in HTML or JSON-LD. Fix options:
1. Batch geocode via Nominatim after scraping (address = quarter + city). Need to respect Nominatim's 1 req/sec limit.
2. Inspect whether Imot.bg's map section loads coordinates via AJAX.

### MT_REMAX: 0% descriptions

The RE/MAX list API endpoint returns empty `Description` fields. Fix: fetch individual property detail pages at `https://www.remax-malta.com/property-details/MLS-{mls}` or check if there's a `/api/properties/{id}` endpoint with full details.

### MT_MALTAPARK: Low area coverage

MaltaPark's property detail pages don't consistently expose area in structured fields. The scraper now also searches the description text for sqm patterns, but coverage depends on sellers including it in free text.

---

## Backend PostGIS Dependency

The production backend (`backend/src/`) requires PostgreSQL + PostGIS for spatial queries. Files affected:

| File | PostGIS functions |
|------|-------------------|
| `models/property.py` | `Geometry("POINT")`, `postgresql_using="gist"` |
| `models/country.py` | `Geometry("MULTIPOLYGON")` |
| `models/valuation.py` | `JSONB` |
| `ml/comparables.py` | `ST_Distance`, `ST_MakePoint`, `ST_DWithin` |
| `ml/confidence.py` | `ST_DWithin`, `ST_MakePoint` |
| `services/property_service.py` | `ST_MakeEnvelope`, `ST_Within` |
| `services/stats_service.py` | `ST_AsGeoJSON` |

**Current workaround**: The dev dashboard (`scripts/dashboard/`) reads directly from DocStore and doesn't use the backend at all. The backend is for the production deployment with Docker Compose (PostgreSQL included).

**To connect them**: Write `scripts/export_to_postgres.py` that reads from DocStore and upserts into PostgreSQL. This bridges scraping (file-based) and the production API (PostGIS).

---

## Missing Alembic Migrations

`backend/alembic/versions/` is empty. To generate:
```bash
docker compose up -d postgres
cd backend && alembic revision --autogenerate -m "initial schema"
```

---

## Frontend Type Gaps

`frontend/src/lib/types.ts` `PropertyType` union is missing `"commercial"` and `"land"` which the scrapers produce. Add them to the union, `PROPERTY_TYPES` constant, and the Zod schema.

---

## Blocked Data Sources

| Site | Status | Fix |
|------|--------|-----|
| PropertyMarket.com.mt | 403 on all listing pages | Needs Playwright or residential proxies |
| Frank Salt | 403 (Cloudflare WAF) | Needs Playwright with stealth |
| Dhalia | Cloudflare managed challenge | Needs Playwright with stealth |
| Malta PPR | Behind paid auth (React SPA) | Requires subscription account |

**Pragmatic stance**: RE/MAX API (32K) + MaltaPark (4K) cover most of the Malta market. PropertyMarket can be added later with Playwright.

---

## Phase 2 Countries

Cyprus and Croatia scrapers not yet built. Research complete in `docs/research/`.

| Country | Primary Target | Notes |
|---------|---------------|-------|
| Cyprus | Bazaraki.com | Apify scraper exists; Greek address transliteration needed |
| Croatia | Nekretnine.hr | Has price data page; anti-scraping on Njuskalo |

---

## Testing

Only 3 unit tests exist (`backend/tests/test_ml/test_features.py`). Needed:

- Scraper parsing tests with saved HTML fixtures
- DocStore unit tests (save, diff, history, flush/reload)
- Dashboard route tests
- Backend API endpoint tests (requires PostgreSQL)

---

## Legacy Code to Clean Up

The `pipeline/` directory contains Scrapy spider stubs that were written before we inspected the actual websites. They don't work and aren't used. Options:
1. Delete the directory entirely (scrapers live in `scripts/`)
2. Port the working `scripts/` scrapers to Scrapy format (useful if we want Celery/Airflow scheduling later)

The `scripts/setup_db.py` and `scripts/scrape_propertymarket_mt.py` are legacy SQLite-era code. The SQLite DB (`data/pricemap.db`) is kept as an archive but isn't used by anything.

---

## Summary

| Priority | Issue | Effort |
|----------|-------|--------|
| High | BG_IMOT missing area + coordinates | ~2h (improve area regex, add batch geocoding) |
| High | MT_REMAX missing descriptions | ~1h (fetch detail pages or single-property API) |
| Medium | No export_to_postgres bridge | ~2h (read DocStore, upsert to PostgreSQL) |
| Medium | No Alembic migrations | ~30m (autogenerate from models) |
| Medium | Frontend missing commercial/land types | ~15m |
| Low | Phase 2 country scrapers (CY, HR) | ~1 day each |
| Low | PropertyMarket.com.mt (403 blocked) | ~2h with Playwright |
| Low | Legacy pipeline/ cleanup | ~30m |
| Low | Integration tests | ~4h |
