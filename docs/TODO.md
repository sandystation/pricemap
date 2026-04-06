# PriceMap - Issues & Remaining Work

Audit performed 2026-04-06 after initial scaffolding and first scraping run.

---

## Critical: Data Quality Gaps

### BG_IMOT: 0% area and 0% coordinates

121 Bulgarian properties scraped with prices, descriptions, images, and agent info
-- but **area_sqm and lat/lon are all NULL**.

**Area**: The HTML parser in `scripts/scrape_imot_bg.py` (`parse_detail_page`, ~line 198)
looks for `(\d+)\s*(?:m²|кв\.\s*м)` in `div.adParams` blocks. This regex doesn't match
the common format where area is embedded in the description text
(e.g. "З.П 47м2" or "65 кв.м" inside `div.info` on search results).
The search results page `div.info` text already contains area -- parse it there as a
fallback. Also try extracting from the JSON-LD `description` field which often has
"65 кв.м" in it.

**Coordinates**: Imot.bg detail pages don't expose lat/lon in HTML or JSON-LD.
Two options:
1. Geocode the address string (quarter + city) via Nominatim. The geocoding pipeline
   (`scripts/scraper_base.py`) doesn't do this currently -- add a batch geocoding step
   after scraping.
2. Some listings have a map section (`a[name="map"]`). Inspect whether clicking it
   loads coordinates via AJAX that could be intercepted.

### MT_REMAX: 0% descriptions

296 Malta properties from the RE/MAX JSON API have structured data (GPS, area,
bedrooms, bathrooms) but the `Description` field comes back as an empty string from
the list endpoint (`/api/properties?Take=100&Skip=N`).

**Fix**: Fetch individual property detail pages at
`https://www.remax-malta.com/property-details/MLS-{mls}` to get full descriptions.
The API likely has a single-property endpoint too -- check `/api/properties/{id}`
or `/api/property/{mls}`.

### MT_MALTAPARK: 0% area

82 Malta properties from MaltaPark have descriptions, images, and prices but no
area_sqm. The detail page parser (`scripts/scrape_maltapark.py`, `parse_detail_page`)
looks for "area", "size", or "sqm" labels in the property details list, but MaltaPark
likely uses a different label or puts sqm info in the description text only.

**Fix**: Also search the description text for patterns like `(\d+)\s*sq\.?\s*m` or
`(\d+)\s*m²` as a fallback.

---

## High: Pipeline vs Scripts Mismatch

The Scrapy spiders in `pipeline/src/spiders/` are **placeholder stubs** written before
we inspected the real websites. They do not match the actual site structures discovered
during research. Meanwhile, the working scrapers live in `scripts/`.

| Spider | Status | Issue |
|--------|--------|-------|
| `pipeline/src/spiders/mt_ppr.py` | Dead code | PPR is behind paid auth (React SPA). Spider yields nothing. |
| `pipeline/src/spiders/mt_propertymarket.py` | Dead code | PropertyMarket returns 403. Selectors are placeholders. |
| `pipeline/src/spiders/bg_imot.py` | Wrong selectors | Uses `a.lnk1`, `a.lnk2` -- real selectors are `div.item a.title.saveSlink`. |

**Decision needed**: Either update the Scrapy spiders to match reality (good for
production scheduling with Celery/Airflow), or consolidate on the `scripts/` scrapers
and remove the pipeline stubs.

Working scrapers that should be the source of truth:
- `scripts/scrape_remax_mt.py` -- RE/MAX JSON API, best Malta source
- `scripts/scrape_maltapark.py` -- MaltaPark HTML, good Malta backup
- `scripts/scrape_imot_bg.py` -- Imot.bg HTML + JSON-LD, Bulgaria source

---

## High: Scrape Run Tracking Bug

The `scrape_runs` table shows incorrect counts. Runs that scraped hundreds of
properties report `items_scraped=0, items_new=0`:

```
mt_remax     running   scraped=0 new=0   (actual: 296 properties in DB)
mt_maltapark running   scraped=0 new=0   (actual: 82 properties in DB)
```

**Root cause**: The RE/MAX and MaltaPark scrapers were killed by `timeout 300` before
they could call `finish_scrape_run()` in their `finally` block. The scrape_run row was
created at start but never updated with final counts.

**Fixes**:
1. Flush counts incrementally during scraping (e.g. update every 50 items) instead of
   only at the end.
2. Add a signal handler so `timeout`/SIGTERM triggers the finalize step.
3. Mark orphaned "running" runs as "interrupted" on startup.

---

## Medium: Backend PostGIS Dependency

The backend code **requires PostgreSQL + PostGIS** for spatial queries but the current
dev workflow uses **SQLite** (via `scripts/setup_db.py`). These two worlds are
disconnected.

### Files with PostGIS-only code

| File | Functions used |
|------|---------------|
| `backend/src/models/property.py` | `Geometry("POINT")`, `postgresql_using="gist"` |
| `backend/src/models/country.py` | `Geometry("MULTIPOLYGON")` |
| `backend/src/models/valuation.py` | `JSONB` (PostgreSQL dialect) |
| `backend/src/ml/comparables.py` | `ST_Distance`, `ST_MakePoint`, `ST_SetSRID`, `ST_DWithin` |
| `backend/src/ml/confidence.py` | `ST_DWithin`, `ST_MakePoint`, `ST_SetSRID` |
| `backend/src/services/property_service.py` | `ST_MakeEnvelope`, `ST_Within` |
| `backend/src/services/stats_service.py` | `ST_AsGeoJSON` |

**Decision needed**: The backend is designed for production with PostGIS (correct for
deployment). But to run the API locally against the SQLite data, either:
1. Add a SQLite-compatible code path using plain lat/lon math instead of PostGIS
   functions (e.g. Haversine distance, bounding box with `WHERE lat BETWEEN ? AND ?`).
2. Or require Docker Compose for local API development (PostgreSQL is already in
   docker-compose.yml) and write a migration to load SQLite data into PostgreSQL.

Option 2 is cleaner long-term. Option 1 is faster for dev iteration.

---

## Medium: Missing Alembic Migrations

`backend/alembic/versions/` is empty -- no migration files exist. The database schema
is defined in SQLAlchemy models but never materialized via Alembic.

**Fix**: Generate the initial migration:
```bash
cd backend
alembic revision --autogenerate -m "initial schema"
```

This requires a running PostgreSQL instance (Alembic connects to the DB to diff).
Run `docker compose up postgres` first.

---

## Medium: Frontend Type Gaps

### Missing property types in TypeScript

`frontend/src/lib/types.ts` line 73-79 defines `PropertyType` as:
```
apartment | house | villa | studio | maisonette | penthouse
```

The backend model (`backend/src/models/property.py`) also has `commercial` and `land`.
The scrapers produce both types (20 commercial, 4 land in current data). If the API
returns these, the frontend will accept them at runtime but TypeScript won't catch
type errors.

**Fix**: Add `"commercial" | "land"` to the frontend `PropertyType` union, and add
them to `PROPERTY_TYPES` in `constants.ts` and the Zod schema in `PropertyForm.tsx`.

---

## Low: PropertyMarket.com.mt Blocked

The biggest Malta portal (38K listings) returns **403 Forbidden** for all HTTP
requests to listing/search pages. The homepage returns 200 but property pages are
blocked.

Same for **Frank Salt** (403) and **Dhalia** (Cloudflare challenge).

**Options**:
1. Use `scrapy-playwright` or `playwright` to render pages with a real browser.
2. Rotate residential proxies.
3. Accept that RE/MAX API (32K listings) + MaltaPark (4K listings) cover most of the
   Malta market.

Option 3 is pragmatic for MVP. Option 1 for completeness later.

---

## Low: No Integration Tests

Only 3 unit tests exist (`backend/tests/test_ml/test_features.py`). No tests for:
- API endpoints (FastAPI TestClient)
- Database operations (SQLAlchemy with test DB)
- Scraper parsing (feed sample HTML, verify output)
- Frontend components (React Testing Library)

**Minimum useful additions**:
- Test `parse_detail_page()` in each scraper with saved HTML fixtures.
- Test `/api/v1/health` endpoint.
- Test `ValuationRequest` schema validation.

---

## Summary

| Priority | Issue | Effort |
|----------|-------|--------|
| Critical | BG_IMOT missing area + coordinates | ~2h (improve parsing + add geocoding) |
| Critical | MT_REMAX missing descriptions | ~1h (fetch detail pages or single-property API) |
| High | Pipeline spiders are dead code | ~1h (delete or update) |
| High | Scrape run tracking bug | ~30m (incremental flush) |
| Medium | Backend requires PostGIS, dev uses SQLite | ~3h (add SQLite code path or Docker workflow) |
| Medium | No Alembic migrations | ~30m (autogenerate from models) |
| Medium | Frontend missing commercial/land types | ~15m |
| Low | PropertyMarket.com.mt blocked | Deferred (RE/MAX covers market) |
| Low | No integration tests | ~4h |
