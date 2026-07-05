"""Export geo-located, clean RE/MAX Malta listings to a CSV for loading into the
production PostGIS `listings` table (comparables source).

Run from scripts/:  python export_listings_csv.py
Output: ../data/exports/mt_listings.csv  (COPY-ready; geom is derived in-DB)

Filters: has lat/lon, positive price + area, not suspicious, not a duplicate,
still active. Covers all property types + both sale and rent (the /api/comparables
query filters by type + listing_type at request time).
"""

import csv
from pathlib import Path

import orjson

SRC = Path("../data/collections/mt_remax.jsonl")
OUT = Path("../data/exports/mt_listings.csv")
COLS = [
    "external_id", "source", "listing_type", "property_type", "locality",
    "lat", "lon", "area_sqm", "bedrooms", "price_eur", "price_per_sqm",
    "url", "listing_date",
]


def listing_date(doc: dict) -> str | None:
    raw = doc.get("last_seen") or doc.get("first_seen")
    return raw[:10] if isinstance(raw, str) and len(raw) >= 10 else None


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    kept = skipped = 0
    with SRC.open("rb") as f, OUT.open("w", newline="") as out:
        w = csv.writer(out)
        w.writerow(COLS)
        for line in f:
            if not line.strip():
                continue
            doc = orjson.loads(line)
            cur = doc.get("current", {})
            lat, lon = cur.get("lat"), cur.get("lon")
            price, area = cur.get("price_eur"), cur.get("area_sqm")
            if not (lat and lon and price and area):
                skipped += 1
                continue
            if doc.get("suspicious") or doc.get("duplicate_of") or not cur.get("is_active", True):
                skipped += 1
                continue
            pps = cur.get("price_per_sqm") or (round(price / area, 2) if area else None)
            w.writerow([
                doc.get("_id"), doc.get("source"), cur.get("listing_type"),
                cur.get("property_type"), cur.get("locality"), lat, lon,
                area, cur.get("bedrooms"), price, pps,
                cur.get("url"), listing_date(doc),
            ])
            kept += 1
    print(f"kept={kept} skipped={skipped} -> {OUT} ({OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
