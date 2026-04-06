"""
One-time migration: SQLite → DocStore.
Converts existing 499 properties from pricemap.db into JSONL documents.
"""

import json
import logging
import os
import sqlite3

from docstore import DocStore

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
logger = logging.getLogger("migrate")

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "pricemap.db")

# Fields to put into doc["current"]
CURRENT_FIELDS = [
    "title", "description", "url",
    "address_raw", "address_normalized", "locality", "lat", "lon",
    "property_type", "area_sqm", "floor", "total_floors",
    "rooms", "bedrooms", "bathrooms",
    "year_built", "year_renovated", "condition",
    "construction_type", "energy_class",
    "has_parking", "has_garden", "has_pool", "has_elevator",
    "has_balcony", "has_furnishing", "has_garage",
    "price_eur", "price_original", "price_currency",
    "price_type", "price_per_sqm", "price_adjusted_eur",
    "agent_name", "agent_company", "agent_phone", "agent_url",
    "listing_date", "transaction_date",
    "image_urls", "image_local_paths",
    "is_active",
]

# JSON string fields to parse back to native types
JSON_FIELDS = {"image_urls", "image_local_paths", "raw_json"}


def main():
    if not os.path.exists(DB_PATH):
        logger.error(f"SQLite database not found: {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # Load country mapping
    countries = {}
    for row in conn.execute("SELECT id, code FROM countries"):
        countries[row["id"]] = row["code"]

    store = DocStore()
    total = 0

    # Migrate per source
    sources = conn.execute("SELECT DISTINCT source FROM properties").fetchall()
    for (source_row,) in [(r["source"],) for r in sources]:
        coll = store.collection(source_row)
        rows = conn.execute(
            "SELECT * FROM properties WHERE source=? ORDER BY id", (source_row,)
        ).fetchall()

        logger.info(f"Migrating {len(rows)} properties from {source_row}")

        for row in rows:
            ext_id = row["external_id"] or str(row["id"])
            doc_id = f"{source_row}:{ext_id}"
            country = countries.get(row["country_id"], "")

            # Build current dict
            current = {}
            for field in CURRENT_FIELDS:
                val = row[field]
                if val is None:
                    continue
                # Parse JSON strings
                if field in JSON_FIELDS and isinstance(val, str):
                    try:
                        val = json.loads(val)
                    except (json.JSONDecodeError, TypeError):
                        pass
                current[field] = val

            # Parse raw_json too
            raw = row["raw_json"]
            if raw:
                try:
                    raw = json.loads(raw)
                except (json.JSONDecodeError, TypeError):
                    pass

            first_seen = row["created_at"] or row["scraped_at"]
            last_seen = row["scraped_at"] or row["updated_at"] or first_seen

            doc = {
                "_id": doc_id,
                "source": source_row,
                "country": country,
                "first_seen": first_seen,
                "last_seen": last_seen,
                "current": current,
                "history": [
                    {"date": first_seen, "event": "created"},
                    {"date": last_seen, "event": "migrated_from_sqlite",
                     "changes": {"sqlite_id": row["id"]}},
                ],
                "_raw_json": raw,
            }

            coll.put(doc)
            total += 1

        coll.flush()
        logger.info(f"  → {coll.count()} docs written to {coll.path}")

    conn.close()
    store.close()

    # Verify
    logger.info(f"\nMigration complete: {total} properties migrated")
    store2 = DocStore()
    for name in store2.list_collections():
        c = store2.collection(name)
        logger.info(f"  {name}: {c.count()} docs")
    store2.close()


if __name__ == "__main__":
    main()
