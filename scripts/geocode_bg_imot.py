"""
Geocode bg_imot properties using Nominatim with Bulgarian neighborhood names.

bg_imot has 0% GPS coordinates. Localities are neighborhood names in Cyrillic
(e.g., "Банишора") with city in address_raw (e.g., "Банишора, Sofia").
Nominatim handles Cyrillic well with countrycodes=bg.

Usage (run from scripts/ directory):
    python geocode_bg_imot.py             # geocode and save to DocStore
    python geocode_bg_imot.py --dry-run   # show mapping without saving
"""

import argparse
import json
import logging
import os
import time

import httpx

from docstore import DocStore

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

CACHE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "data", "geocode_cache_bg.json"
)

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
NOMINATIM_HEADERS = {"User-Agent": "PriceMap/1.0 (real estate research project)"}
NOMINATIM_DELAY = 1.1

# City name mapping (address_raw uses English, Nominatim prefers Bulgarian)
CITY_BG = {
    "Sofia": "София",
    "Plovdiv": "Пловдив",
    "Varna": "Варна",
    "Burgas": "Бургас",
    "Ruse": "Русе",
    "Stara Zagora": "Стара Загора",
    "Pleven": "Плевен",
    "Shumen": "Шумен",
    "Dobrich": "Добрич",
    "Blagoevgrad": "Благоевград",
    "Sliven": "Сливен",
}


def load_cache() -> dict:
    if os.path.exists(CACHE_PATH):
        with open(CACHE_PATH) as f:
            return json.load(f)
    return {}


def save_cache(cache: dict):
    with open(CACHE_PATH, "w") as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)


def geocode_neighborhood(neighborhood: str, city_en: str) -> dict | None:
    """Geocode a Bulgarian neighborhood via Nominatim."""
    city_bg = CITY_BG.get(city_en, city_en)

    # Try Cyrillic first (most accurate), then English
    queries = [
        f"{neighborhood}, {city_bg}, България",
        f"{neighborhood}, {city_en}, Bulgaria",
    ]

    for q in queries:
        try:
            resp = httpx.get(
                NOMINATIM_URL,
                params={"q": q, "format": "json", "limit": 1, "countrycodes": "bg"},
                headers=NOMINATIM_HEADERS,
                timeout=10,
            )
            if resp.status_code == 200:
                results = resp.json()
                if results:
                    return {
                        "lat": float(results[0]["lat"]),
                        "lon": float(results[0]["lon"]),
                        "display_name": results[0].get("display_name", ""),
                    }
        except Exception as e:
            logger.warning(f"Nominatim error for '{q}': {e}")

    return None


def geocode_bg_imot(dry_run: bool = False):
    """Geocode all bg_imot properties by neighborhood + city."""
    store = DocStore()
    coll = store.collection("bg_imot")
    coll._ensure_loaded()

    cache = load_cache()

    # Collect unique (neighborhood, city) pairs
    pairs = {}
    for doc_id, doc in coll._docs.items():
        cur = doc.get("current", {})
        locality = cur.get("locality", "")
        addr = cur.get("address_raw", "")
        city = addr.split(",")[-1].strip() if "," in addr else ""

        if not locality or not city:
            continue

        cache_key = f"{locality}|{city}"
        if cache_key not in pairs:
            pairs[cache_key] = {"locality": locality, "city": city, "doc_ids": []}
        pairs[cache_key]["doc_ids"].append(doc_id)

    logger.info(f"Unique neighborhood+city pairs: {len(pairs)}")

    # Geocode uncached pairs
    to_geocode = [k for k in pairs if k not in cache]
    logger.info(f"Already cached: {len(pairs) - len(to_geocode)}")
    logger.info(f"Need to geocode: {len(to_geocode)}")

    if to_geocode:
        if not dry_run:
            logger.info(f"Estimated time: {len(to_geocode) * NOMINATIM_DELAY / 60:.0f} minutes")

        geocoded = 0
        failed = 0
        try:
            for i, cache_key in enumerate(to_geocode):
                info = pairs[cache_key]
                result = geocode_neighborhood(info["locality"], info["city"])
                cache[cache_key] = result

                if result:
                    geocoded += 1
                else:
                    failed += 1

                if (i + 1) % 50 == 0:
                    save_cache(cache)
                    logger.info(f"Progress: {i+1}/{len(to_geocode)} (found={geocoded}, not_found={failed})")

                time.sleep(NOMINATIM_DELAY)
        except KeyboardInterrupt:
            logger.info("Interrupted -- saving cache.")
        finally:
            save_cache(cache)

        logger.info(f"Geocoded: {geocoded}, Not found: {failed}")

    # Apply coordinates to docs
    total = 0
    matched = 0
    for cache_key, info in pairs.items():
        result = cache.get(cache_key)
        for doc_id in info["doc_ids"]:
            total += 1
            if result:
                matched += 1
                if not dry_run:
                    doc = coll._docs[doc_id]
                    doc["current"]["lat"] = result["lat"]
                    doc["current"]["lon"] = result["lon"]
                    coll._mark_dirty()

    if not dry_run:
        coll.flush()

    cached_found = sum(1 for k in pairs if cache.get(k) is not None)
    cached_missing = sum(1 for k in pairs if k in cache and cache[k] is None)

    logger.info(f"Total docs: {total}, Matched: {matched} ({100*matched/total:.1f}%)")
    logger.info(f"Unique pairs: {len(pairs)} (found={cached_found}, not_found={cached_missing})")

    store.close()


def main():
    parser = argparse.ArgumentParser(description="Geocode bg_imot properties")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    geocode_bg_imot(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
