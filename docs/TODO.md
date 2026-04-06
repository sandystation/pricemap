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

## Data Quality: Bugs Found in Comprehensive Testing (2026-04-06)

### RE/MAX missing property type mappings

The RE/MAX API returns 70+ distinct property types but only 24 were in the `TYPE_MAP`. Everything unmapped defaulted to `"apartment"`, misclassifying ~3,700 listings (garages, offices, villas, land, etc. all shown as apartments).

**Scraper code fixed** (2026-04-06):
- `scrape_remax_mt.py`: `TYPE_MAP` expanded from 24 → 88 entries. Added `"parking"` category. Default → `"other"` with warning log.
- `scrape_maltapark.py`: Same fixes — expanded TYPE_MAP, default → `"other"`.

**Data not fully fixed** — both scrapers were still running when the code was changed. A partial fix was applied to `mt_remax.jsonl` (3,715 docs corrected), but docs scraped after that by the still-running old-code process will have wrong types again. Run this for **both** collections after their scrapers finish:

```python
# Fix mt_remax
from scrape_remax_mt import TYPE_MAP as REMAX_MAP
from docstore import DocStore
store = DocStore()
c = store.collection("mt_remax")
c._ensure_loaded()
fixed = 0
for doc in c._docs.values():
    raw = doc.get("current", {}).get("raw_type", "")
    old_pt = doc.get("current", {}).get("property_type", "")
    new_pt = REMAX_MAP.get(raw, "other")
    if old_pt != new_pt:
        doc["current"]["property_type"] = new_pt
        fixed += 1
if fixed:
    c._dirty = True
    c.flush()
print(f"mt_remax: fixed {fixed} documents")
store.close()

# Fix mt_maltapark
from scrape_maltapark import TYPE_MAP as MP_MAP
store = DocStore()
c = store.collection("mt_maltapark")
c._ensure_loaded()
fixed = 0
for doc in c._docs.values():
    raw = doc.get("current", {}).get("property_type_raw", "")
    old_pt = doc.get("current", {}).get("property_type", "")
    new_pt = MP_MAP.get(raw.lower(), "other")
    if old_pt != new_pt:
        doc["current"]["property_type"] = new_pt
        fixed += 1
if fixed:
    c._dirty = True
    c.flush()
print(f"mt_maltapark: fixed {fixed} documents")
store.close()
```

### MaltaPark garbage prices (phone numbers parsed as prices)

MaltaPark's price element sometimes contains phone numbers or reference IDs (e.g. €9,988,777,000 for a "Large Garage"). These are clearly not real prices — they're parsed from nearby text that leaks into the price field.

Root cause: `parse_listing_page` uses a broad regex `[\d,]+` on the price span, which can pick up non-price numbers. The detail page parser has the same issue.

**Not capped** — legitimate properties can exceed €50M (e.g. Malta development sites at €65M in RE/MAX). Instead, this needs smarter validation: flag prices where `price / area_sqm` exceeds a threshold (e.g. €100K/sqm), or where the price is 100x the locality median.

### DocStore wasn't storing new field values on re-scrape

When a property was re-scraped with a new field (e.g. `area_sqm` first appearing), the value was silently dropped if no tracked field had changed. This meant fields discovered on later scrapes were lost.

**Fixed** in `docstore.py` — `save_property()` now always writes all non-None incoming values to `current`, regardless of whether tracked changes were detected.

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

Tests exist in `scripts/test_dashboard.py` (35 Playwright e2e tests) and inline in the comprehensive bug hunt script. Summary of current coverage:

- **DocStore engine**: 11 tests (create, reload, change detection, float tolerance, staleness, find, delete, auto-flush, corrupt line handling, diff correctness)
- **Scraper parsers**: 7 tests (RE/MAX property processing, null handling, all type mappings; Imot.bg type/room detection; MaltaPark condition mapping, price validation)
- **Live data integrity**: 7 tests (doc structure, no duplicate IDs, price validation, GPS bounds, image URLs, history events)
- **Dashboard HTTP**: 27 tests (all routes, all filters, all sorts, pagination, XSS, 404s, empty collections, invalid params, Cyrillic search)
- **Dashboard Playwright e2e**: 35 tests (browser-based: clicks, form submits, navigation, image loading)

Still needed:
- Backend API endpoint tests (requires PostgreSQL)
- Scraper parsing tests with saved HTML fixtures (for regression when sites change)

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
| High | Fix property_type in mt_remax + mt_maltapark data (after scrapers finish) | ~5m (script in TODO above) |
| Medium | MaltaPark price validation (phone numbers as prices) | ~1h (smarter validation: price/sqm ratio, locality median comparison) |
| Medium | No export_to_postgres bridge | ~2h (read DocStore, upsert to PostgreSQL) |
| Medium | No Alembic migrations | ~30m (autogenerate from models) |
| Medium | Frontend missing commercial/land types | ~15m |
| Medium | Add `listing_type` field (sale vs rent) to all scrapers | ~30m |
| Low | Phase 2 country scrapers (CY, HR) | ~1 day each |
| Low | PropertyMarket.com.mt (403 blocked) | ~2h with Playwright |
| Low | Legacy pipeline/ cleanup | ~30m |
| Low | Backend API + HTML fixture tests | ~4h |
