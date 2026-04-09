"""
Geocode location_reference values extracted by llm_enrich.py.

Reads unique location references from an enrichment run, geocodes them
via Nominatim (OpenStreetMap), and saves a lookup table for use by
train_valuation.py to refine town-level coordinates.

Usage (run from scripts/ directory):
    python geocode_locations.py --llm-run v3_with_locref          # geocode new refs
    python geocode_locations.py --llm-run v3_with_locref --stats  # show coverage
    python geocode_locations.py --show-cache                      # show all cached geocodes
"""

import argparse
import json
import logging
import os
import time

import httpx

from llm_enrich import load_run, ENRICHMENTS_DIR

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)

CACHE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "data", "geocode_cache.json"
)

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
NOMINATIM_HEADERS = {"User-Agent": "PriceMap/1.0 (real estate research project)"}

# Rate limit: 1 request per second (Nominatim policy)
NOMINATIM_DELAY = 1.1


def load_cache() -> dict[str, dict | None]:
    """Load geocode cache. Maps 'reference|locality' -> {lat, lon} or None."""
    if os.path.exists(CACHE_PATH):
        with open(CACHE_PATH) as f:
            return json.load(f)
    return {}


def save_cache(cache: dict):
    with open(CACHE_PATH, "w") as f:
        json.dump(cache, f, indent=2)


def geocode_nominatim(query: str, locality: str | None = None) -> dict | None:
    """Geocode a location reference via Nominatim. Returns {lat, lon} or None."""
    # Try progressively less specific queries
    queries = []
    if locality:
        queries.append(f"{query}, {locality}, Malta")
    queries.append(f"{query}, Malta")

    for q in queries:
        try:
            resp = httpx.get(
                NOMINATIM_URL,
                params={"q": q, "format": "json", "limit": 1, "countrycodes": "mt"},
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
                        "query_used": q,
                    }
        except Exception as e:
            logger.warning(f"Nominatim error for '{q}': {e}")

    return None


def collect_unique_refs(run_id: str) -> dict[str, set]:
    """Collect unique (location_reference, locality) pairs from a run."""
    data = load_run(run_id)
    refs = {}  # ref -> set of localities it appears with
    for doc_id, features in data.items():
        loc_ref = features.get("location_reference")
        if not loc_ref:
            continue
        ref_lower = loc_ref.strip().lower()
        if ref_lower not in refs:
            refs[ref_lower] = {"original": loc_ref.strip(), "localities": set(), "count": 0}
        refs[ref_lower]["count"] += 1
        # Try to get locality from doc_id prefix (mt_remax:...)
        # We'll pass locality at geocode time from the enrichment data

    # Also load with localities from DocStore
    from docstore import DocStore
    store = DocStore()
    coll = store.collection("mt_remax")
    coll._ensure_loaded()

    for doc_id, features in data.items():
        loc_ref = features.get("location_reference")
        if not loc_ref:
            continue
        ref_lower = loc_ref.strip().lower()
        doc = coll._docs.get(doc_id)
        if doc:
            locality = doc.get("current", {}).get("locality", "")
            refs[ref_lower]["localities"].add(locality)

    store.close()

    # Convert sets to lists for JSON serialization
    for r in refs.values():
        r["localities"] = sorted(r["localities"])

    return refs


def geocode_refs(run_id: str):
    """Geocode all unique location references from an enrichment run."""
    refs = collect_unique_refs(run_id)
    cache = load_cache()

    logger.info(f"Unique location references: {len(refs)}")

    to_geocode = []
    for ref_lower, info in refs.items():
        # Use the most common locality as context
        locality = info["localities"][0] if info["localities"] else None
        cache_key = f"{ref_lower}|{locality or ''}"
        if cache_key not in cache:
            to_geocode.append((ref_lower, info["original"], locality, cache_key))

    logger.info(f"Already cached: {len(refs) - len(to_geocode)}")
    logger.info(f"Need to geocode: {len(to_geocode)}")

    if not to_geocode:
        logger.info("Nothing to geocode.")
        return

    logger.info(f"Estimated time: {len(to_geocode) * NOMINATIM_DELAY / 60:.0f} minutes")

    geocoded = 0
    failed = 0

    try:
        for i, (ref_lower, original, locality, cache_key) in enumerate(to_geocode):
            result = geocode_nominatim(original, locality)
            cache[cache_key] = result

            if result:
                geocoded += 1
                logger.debug(f"  {original} ({locality}) -> ({result['lat']:.4f}, {result['lon']:.4f})")
            else:
                failed += 1
                logger.debug(f"  {original} ({locality}) -> NOT FOUND")

            if (i + 1) % 50 == 0:
                save_cache(cache)
                logger.info(f"Progress: {i+1}/{len(to_geocode)} (found={geocoded}, not_found={failed})")

            time.sleep(NOMINATIM_DELAY)

    except KeyboardInterrupt:
        logger.info("Interrupted -- saving cache.")
    finally:
        save_cache(cache)

    logger.info(f"Done. Geocoded: {geocoded}, Not found: {failed}")


def print_stats(run_id: str):
    """Show geocoding coverage stats."""
    refs = collect_unique_refs(run_id)
    cache = load_cache()

    total_docs = sum(r["count"] for r in refs.values())
    total_refs = len(refs)

    cached = 0
    found = 0
    not_found = 0
    uncached = 0

    for ref_lower, info in refs.items():
        locality = info["localities"][0] if info["localities"] else None
        cache_key = f"{ref_lower}|{locality or ''}"
        if cache_key in cache:
            cached += 1
            if cache[cache_key] is not None:
                found += 1
            else:
                not_found += 1
        else:
            uncached += 1

    print(f"\n=== Geocoding stats for run '{run_id}' ===")
    print(f"Documents with location_reference: {total_docs}")
    print(f"Unique references: {total_refs}")
    print(f"  Geocoded (found):    {found}")
    print(f"  Geocoded (not found): {not_found}")
    print(f"  Not yet geocoded:    {uncached}")

    if found:
        print(f"\n--- Top references by frequency ---")
        sorted_refs = sorted(refs.items(), key=lambda x: -x[1]["count"])
        for ref_lower, info in sorted_refs[:20]:
            locality = info["localities"][0] if info["localities"] else ""
            cache_key = f"{ref_lower}|{locality}"
            result = cache.get(cache_key)
            status = f"({result['lat']:.4f}, {result['lon']:.4f})" if result else "NOT FOUND"
            print(f"  {info['original']:30s} (n={info['count']:>4d}) {status}")


def show_cache():
    """Show all cached geocodes."""
    cache = load_cache()
    print(f"Cached entries: {len(cache)}")
    found = {k: v for k, v in cache.items() if v is not None}
    not_found = {k: v for k, v in cache.items() if v is None}
    print(f"  Found: {len(found)}")
    print(f"  Not found: {len(not_found)}")

    if found:
        print(f"\n--- Found ---")
        for key, result in sorted(found.items()):
            print(f"  {key:50s} -> ({result['lat']:.4f}, {result['lon']:.4f})")


# ---------------------------------------------------------------------------
# Public API for train_valuation.py
# ---------------------------------------------------------------------------

def build_coordinate_overrides(run_id: str) -> dict[str, tuple[float, float]]:
    """Build doc_id -> (lat, lon) mapping from geocoded location references.

    Returns a dict mapping doc_id to refined coordinates for properties
    whose location_reference was successfully geocoded.
    """
    data = load_run(run_id)
    cache = load_cache()

    from docstore import DocStore
    store = DocStore()
    coll = store.collection("mt_remax")
    coll._ensure_loaded()

    overrides = {}
    for doc_id, features in data.items():
        loc_ref = features.get("location_reference")
        if not loc_ref:
            continue

        ref_lower = loc_ref.strip().lower()
        doc = coll._docs.get(doc_id)
        locality = doc.get("current", {}).get("locality", "") if doc else ""
        cache_key = f"{ref_lower}|{locality}"

        result = cache.get(cache_key)
        if result and result.get("lat"):
            overrides[doc_id] = (result["lat"], result["lon"])

    store.close()
    return overrides


def main():
    parser = argparse.ArgumentParser(description="Geocode location references from LLM enrichment")
    parser.add_argument("--llm-run", help="Enrichment run ID to geocode")
    parser.add_argument("--stats", action="store_true", help="Show geocoding coverage stats")
    parser.add_argument("--show-cache", action="store_true", help="Show all cached geocodes")
    args = parser.parse_args()

    if args.show_cache:
        show_cache()
        return

    if not args.llm_run:
        parser.error("--llm-run is required (unless using --show-cache)")

    if args.stats:
        print_stats(args.llm_run)
    else:
        geocode_refs(args.llm_run)


if __name__ == "__main__":
    main()
