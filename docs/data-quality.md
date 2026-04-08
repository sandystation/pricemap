# Data Quality Pipeline

Scripts for enriching, deduplicating, and flagging suspicious property data.

## Commands

```bash
cd scripts
python enrich_remax_mt.py              # Fetch descriptions/features from RE/MAX detail API
python enrich_remax_mt.py --delay 0.5  # Faster (default 1.0s between requests)
python dedup_remax.py                  # Dry run: find duplicate RE/MAX listings
python dedup_remax.py --apply          # Mark duplicates with duplicate_of field
python flag_suspicious.py              # Flag suspicious docs across all collections
python flag_suspicious.py --stats      # Show flag distribution without modifying data
python flag_suspicious.py mt_remax     # Flag one collection only
```

## Raw Data Preservation

All scrapers store the raw source data so fields can be re-extracted later without re-scraping:

- **RE/MAX**: `raw_data` = full list API JSON response per property. `raw_data_detail` = full detail API response (from enrichment script).
- **MaltaPark**: `raw_data` = `{"listing": {...}, "detail": {...}}` — parsed search-page and detail-page dicts.
- **Imot.bg**: `raw_data` = `{"listing": {...}, "detail": {...}}` — same structure.

## Enrichment (`enrich_remax_mt.py`)

The RE/MAX list API returns empty `Description` fields. The enrichment script fetches the detail API at `/api/properties/{MLS}` for each listing and adds:

- Full text descriptions (99% coverage)
- Structured features (balcony, lift, en suite, etc.)
- Room dimensions (type, width, length, size in sqm)
- Agent name, email, phone, office
- Energy rating
- All photos in high resolution
- Plot size, roof area

Safe to Ctrl+C — flushes progress on interrupt. Re-running skips docs that already have descriptions (use `--all` to re-enrich everything).

## Deduplication (`dedup_remax.py`)

RE/MAX often creates multiple MLS numbers for the same property (same agent re-listing, or multiple agents listing the same unit). The dedup script groups listings by:

- Same price
- Same area
- Same description (first 100 chars, lowercased)

The earliest-inserted doc becomes canonical; others get a `duplicate_of` field pointing to it. The dashboard hides duplicates by default.

Current stats: ~3,072 duplicates across ~1,527 groups. Mostly pairs (same agent, consecutive MLS numbers), with some large groups (same rental listed 50+ times by one agent).

## Suspicion Flagging (`flag_suspicious.py`)

Adds a `suspicious` list field to every doc's `current`:
- Empty list `[]` = clean doc
- Non-empty = list of reason strings for review

Intended for downstream LLM post-processing: a dedicated script can query all docs where `suspicious` is non-empty and use an LLM to review/correct them.

### Flag Types

| Flag | Meaning | Typical Cause |
|------|---------|---------------|
| `price_extreme_high` | Price > 10M | Phone numbers parsed as prices (MaltaPark) |
| `price_placeholder` | Sale price < 100 | "Price on request" with placeholder value (1) |
| `price_suspiciously_low` | Sale < 1K for non-parking/land | Data entry error or wrong currency |
| `price_title_mismatch:XvsY` | Title contains different price | European notation (480.000) vs parsed (480) |
| `price_locality_outlier_high` | Price > 50x locality median | Likely garbage data |
| `price_locality_outlier_low` | Price < 1% of locality median | Likely placeholder or wrong currency |
| `price_per_sqm_extreme_high` | Price/sqm > 50K | Bad price or bad area |
| `price_per_sqm_extreme_low` | Price/sqm < 50 for non-land | Bad price or bad area |
| `price_on_request` | Text in price field | Imot.bg "При запитване" |
| `price_zero_or_negative` | Price <= 0 | Bad data |
| `area_too_small` | < 5 sqm for non-parking | RE/MAX uses 1 sqm as "not specified" |
| `area_too_large` | > 50K sqm for non-land | Parsing error |
| `wanted_ad` | Buyer-wanted listing | MaltaPark "WANTED" listings with 1 price |
| `duplicate` | Marked duplicate of another listing | RE/MAX multi-MLS |
| `type_unknown` | Property type = "other" | Raw type not in TYPE_MAP |
| `no_price` | No price data at all | Missing from source |
| `no_title` | Missing title | Parsing failure |

### Current Flag Distribution (2026-04-08)

**mt_remax** (32,079 docs): 4,707 flagged (14%)
- 3,072 duplicate, 1,205 area_too_small, 438 no_price, 28 price_extreme_high

**mt_maltapark** (4,109 docs): 566 flagged (13%)
- 295 wanted_ad, 252 type_unknown, 112 price_locality_outlier_low, 55 price_placeholder, 22 price_extreme_high

**bg_imot** (9,805 docs): 311 flagged (3%)
- 301 price_on_request, 8 price_per_sqm_extreme_low, 4 area_too_large

## Known Source Data Issues

### RE/MAX Malta
- `TransactionTypeId` API parameter is ignored — always returns all listings (sales + rentals + short-term). Use `TransactionType` string field to distinguish.
- Base URL is `remax-malta.com` (no `www` — redirects to non-www).
- Listing URLs: `https://remax-malta.com/listings/{MLS}` (not `/property-details/`).
- Rental `Period` field (Daily/Monthly) exists in API but not yet extracted to a `price_period` field.
- Many listings have `area_sqm=1` meaning "not specified".

### MaltaPark
- Raw type `"Apartment / Flat"` (with slash) must match exactly in TYPE_MAP.
- Phone numbers sometimes appear in the price field (Maltese numbers starting with 7 or 9).
- Category 248 is "Property for sale" but contains buyer-wanted ads (~7%).
- No structured bathroom field — only extractable from free text.
- Area coverage is low (~23%) — depends on seller input.

### Imot.bg
- JSON-LD `itemOffered.name` says "Дава под Наем" (for rent) on sales pages. Use HTML `<h1>` for title.
- EUR prices with decimals (`15 338.76 €`) need regex `([\d\s]+(?:[.,]\d+)?)\s*€` — without the decimal part, only `76` gets captured.
- Room count regex must be case-insensitive (`2-СТАЕН` in titles, not `2-стаен`).
- No coordinates exposed in HTML or JSON-LD — needs external geocoding.
- `encoding = "windows-1251"` required on all responses.
