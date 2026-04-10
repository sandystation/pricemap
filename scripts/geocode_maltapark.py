"""
Geocode MaltaPark properties using RE/MAX town centroids + Nominatim fallback.

MaltaPark has 0% GPS coordinates. This script maps locality names to coordinates
from RE/MAX (which has town-level GPS for 69 localities) with fuzzy matching
for naming differences (e.g., "Gharb (Gozo)" → "Gozo - Gharb").

Usage (run from scripts/ directory):
    python geocode_maltapark.py             # geocode and save to DocStore
    python geocode_maltapark.py --dry-run   # show mapping without saving
"""

import argparse
import logging
import time

from docstore import DocStore
from geocode_locations import geocode_nominatim, load_cache, save_cache

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# Manual mapping for MaltaPark → RE/MAX locality names
# Handles naming conventions: "(Gozo)" suffix → "Gozo - " prefix, accents, etc.
LOCALITY_MAP = {
    # Gozo localities
    "Rabat (Gozo)": "Gozo - Victoria",
    "Qala (Gozo)": "Gozo - Qala",
    "Xaghra (Gozo)": "Gozo - Xaghra",
    "Nadur (Gozo)": "Gozo - Nadur",
    "Marsalforn (Gozo)": "Gozo - Marsalforn",
    "Ghajnsielem (Gozo)": "Gozo - Ghajnsielem",
    "Xewkija (Gozo)": "Gozo - Xewkija",
    "Sannat": "Gozo - Sannat",
    "Xlendi (Gozo)": "Gozo - Xlendi",
    "Kercem (Gozo)": "Gozo - Kercem",
    "Gharb (Gozo)": "Gozo - Gharb",
    "Zebbug (Gozo)": "Gozo - Zebbug",
    "Ghasri": "Gozo - Ghasri",
    "San Lawrenz (Gozo)": "Gozo - San Lawrenz",
    "Munxar (Gozo)": "Gozo - Munxar",
    "Fontana (Gozo)": "Gozo - Fontana",
    # Malta disambiguation
    "Zebbug (Malta)": "Zebbug",
    "Rabat (Malta)": "Rabat",
    # Spelling/naming differences
    "San Giljan": "St Julian's",
    "San Pawl il-Bahar": "St Paul's Bay",
    "Birzebbugia": "Birzebbuga",
    "Pieta'": "Pieta",
    "G'Mangia": "Gzira",  # G'Mangia is part of Gzira/Msida area
    "Ibragg": "Ta' l-Ibragg",
    "Swatar": "Msida",  # Swatar is part of Msida
    "Birgu": "Birgu",
    "Bugibba": "Bugibba",
    "Qawra": "Qawra",
    "Bahrija": "Rabat",  # Bahrija is a hamlet near Rabat
    # Sub-areas mapped to parent locality
    "Kappara": "San Gwann",
    "San Pawl tat-Targa": "Naxxar",
    "Bormla": "Bormla",
    "Birgu": "Birgu",
    "Isla": "Isla",
    "Santa Lucija": "Santa Lucija",
    "Zebbiegh": "Mgarr",
    "Manikata": "Mellieha",
    "Burmarrad": "St Paul's Bay",
    "Fontana": "Gozo - Fontana",
    "Buskett": "Rabat",
    "Xemxija": "Xemxija",
    "Bidnija": "Mosta",
    "Madliena": "Swieqi",
    "Salina": "Naxxar",
    "Bahar ic-Caghaq": "Naxxar",
    "Birguma": "Naxxar",
    "Hal-Far": "Birzebbuga",
    "Wardija": "Rabat",
    "Paceville": "St Julian's",
    "Maghtab": "Naxxar",
    "Ta' Qali": "Attard",
    "Marsalforn (Gozo)": "Gozo - Marsalforn",
    "Xlendi (Gozo)": "Gozo - Xlendi",
    "Ibragg": "Ta' l-Ibragg",
    "*Outside Malta": None,  # skip
}


def build_remax_coords() -> dict[str, tuple[float, float]]:
    """Build locality → (lat, lon) mapping from RE/MAX data."""
    store = DocStore()
    coll = store.collection("mt_remax")
    coll._ensure_loaded()

    coords = {}
    for doc in coll._docs.values():
        cur = doc.get("current", {})
        loc = cur.get("locality")
        lat = cur.get("lat")
        lon = cur.get("lon")
        if loc and lat and lon:
            coords[loc] = (lat, lon)

    store.close()
    logger.info(f"RE/MAX localities with coords: {len(coords)}")
    return coords


def geocode_maltapark(dry_run: bool = False):
    """Geocode all MaltaPark properties."""
    remax_coords = build_remax_coords()

    store = DocStore()
    coll = store.collection("mt_maltapark")
    coll._ensure_loaded()

    total = 0
    matched = 0
    nominatim_hits = 0
    failed = []
    geocode_cache = load_cache()

    for doc_id, doc in coll._docs.items():
        cur = doc.get("current", {})
        locality = cur.get("locality", "")
        total += 1

        if not locality or locality == "?":
            continue

        # Skip already geocoded
        if cur.get("lat") and not dry_run:
            matched += 1
            continue

        # Try direct match
        coords = remax_coords.get(locality)

        # Try mapped name
        if not coords:
            mapped = LOCALITY_MAP.get(locality)
            if mapped is None and locality in LOCALITY_MAP:
                continue  # explicitly skipped (e.g., *Outside Malta)
            if mapped:
                coords = remax_coords.get(mapped)

        # Try Nominatim for remaining (cached)
        if not coords:
            cache_key = f"{locality.lower()}|"
            if cache_key in geocode_cache:
                result = geocode_cache[cache_key]
                if result:
                    coords = (result["lat"], result["lon"])
            elif not dry_run:
                result = geocode_nominatim(locality, None)
                geocode_cache[cache_key] = result
                if result:
                    coords = (result["lat"], result["lon"])
                    nominatim_hits += 1
                time.sleep(1.1)

        if coords:
            matched += 1
            if not dry_run:
                cur["lat"] = coords[0]
                cur["lon"] = coords[1]
                coll._mark_dirty()
        else:
            if locality not in [f[0] for f in failed]:
                count = sum(1 for d in coll._docs.values() if d.get("current", {}).get("locality") == locality)
                failed.append((locality, count))

    if not dry_run:
        coll.flush()
        save_cache(geocode_cache)

    logger.info(f"Total: {total}, Matched: {matched} ({100*matched/total:.1f}%), "
                f"Nominatim: {nominatim_hits}")

    if failed:
        logger.info(f"Failed to geocode {len(failed)} localities:")
        for loc, cnt in sorted(failed, key=lambda x: -x[1]):
            logger.info(f"  {loc:35s}: {cnt} docs")

    store.close()


def main():
    parser = argparse.ArgumentParser(description="Geocode MaltaPark properties")
    parser.add_argument("--dry-run", action="store_true", help="Show mapping without saving")
    args = parser.parse_args()
    geocode_maltapark(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
