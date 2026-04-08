"""
Flag suspicious documents across all collections.

Adds a `suspicious` list to each doc's `current` with reason strings.
Docs with no issues get an empty list. This enables downstream LLM
post-processing to review and correct flagged entries.

Usage:
    cd scripts
    python flag_suspicious.py              # Flag all collections
    python flag_suspicious.py mt_remax     # Flag one collection
    python flag_suspicious.py --stats      # Show flag distribution only
"""

import argparse
import logging
import re
import statistics

from docstore import DocStore

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("flag_suspicious")


def flag_doc(doc: dict, locality_medians: dict) -> list[str]:
    """Return a list of suspicion reasons for a document."""
    cur = doc.get("current", {})
    flags = []

    price = cur.get("price_eur")
    area = cur.get("area_sqm")
    prop_type = cur.get("property_type", "")
    listing_type = cur.get("listing_type", "sale")
    title = cur.get("title") or ""
    description = cur.get("description") or ""

    # --- Price checks ---
    if price is not None:
        if price > 10_000_000:
            flags.append("price_extreme_high")
        elif price < 1:
            flags.append("price_zero_or_negative")
        elif listing_type == "sale" and price < 100:
            flags.append("price_placeholder")
        elif listing_type == "sale" and price < 1000 and prop_type not in ("parking", "land"):
            flags.append("price_suspiciously_low")

        # Check if title contains a price-like number that differs from stored price
        title_prices = re.findall(r"(\d[\d.,]*\d)\s*(?:€|eur)", title, re.IGNORECASE)
        for tp in title_prices:
            try:
                # Handle European notation: 480.000 = 480000, 1.200.000 = 1200000
                cleaned = tp.replace(" ", "")
                # If has dots but no commas, dots might be thousands separators
                if "." in cleaned and "," not in cleaned:
                    parts = cleaned.split(".")
                    # European: 480.000 → all parts after first are 3 digits
                    if all(len(p) == 3 for p in parts[1:]):
                        title_price = float(cleaned.replace(".", ""))
                    else:
                        title_price = float(cleaned)
                else:
                    title_price = float(cleaned.replace(",", ""))
                ratio = max(title_price, price) / max(min(title_price, price), 1)
                if ratio > 10:
                    flags.append(f"price_title_mismatch:{int(title_price)}vs{int(price)}")
                    break
            except (ValueError, ZeroDivisionError):
                continue

        # Price per sqm outlier
        if area and area > 0:
            ppsqm = price / area
            if listing_type == "sale":
                if ppsqm > 50_000:
                    flags.append("price_per_sqm_extreme_high")
                elif ppsqm < 50 and prop_type not in ("land",):
                    flags.append("price_per_sqm_extreme_low")

        # Locality median comparison
        locality = cur.get("locality", "")
        if locality and locality in locality_medians and listing_type == "sale":
            median = locality_medians[locality]
            if median > 0 and price > 0:
                ratio = price / median
                if ratio > 50:
                    flags.append("price_locality_outlier_high")
                elif ratio < 0.01:
                    flags.append("price_locality_outlier_low")
    else:
        # Check if "price on request" or similar
        price_orig = cur.get("price_original")
        if price_orig and isinstance(price_orig, str):
            flags.append("price_on_request")

    # --- Area checks ---
    if area is not None:
        if area < 5 and prop_type not in ("parking", "land"):
            flags.append("area_too_small")
        elif area > 50_000 and prop_type not in ("land",):
            flags.append("area_too_large")

    # --- Wanted ads ---
    title_lower = title.lower()
    if cur.get("is_wanted"):
        flags.append("wanted_ad")
    elif any(kw in title_lower for kw in
             ["wanted", "looking for", "looking to buy", "searching for",
              "required", "тър[cс]и"]):
        flags.append("wanted_ad")

    # --- Duplicate ---
    if cur.get("duplicate_of"):
        flags.append("duplicate")

    # --- Missing critical fields ---
    if not price and not cur.get("price_original"):
        flags.append("no_price")
    if not title:
        flags.append("no_title")

    # --- Type unknown ---
    if prop_type == "other":
        flags.append("type_unknown")

    return flags


def compute_locality_medians(docs: list[dict], listing_type: str = "sale") -> dict:
    """Compute median price per locality for outlier detection."""
    by_locality = {}
    for doc in docs:
        cur = doc.get("current", {})
        if cur.get("listing_type") != listing_type:
            continue
        price = cur.get("price_eur")
        locality = cur.get("locality")
        if price and locality and price > 100:
            by_locality.setdefault(locality, []).append(price)
    return {
        loc: statistics.median(prices)
        for loc, prices in by_locality.items()
        if len(prices) >= 3
    }


def flag_collection(store: DocStore, name: str, stats_only: bool = False):
    """Flag all docs in a collection."""
    coll = store.collection(name)
    coll._ensure_loaded()
    docs = list(coll._docs.values())

    logger.info(f"Flagging {name}: {len(docs)} docs")
    medians = compute_locality_medians(docs)

    flag_counts = {}
    total_flagged = 0

    for doc in docs:
        flags = flag_doc(doc, medians)

        if not stats_only:
            doc.get("current", {})["suspicious"] = flags
            coll._dirty = True

        if flags:
            total_flagged += 1
        for f in flags:
            # Group by flag type (strip parameters after colon)
            key = f.split(":")[0]
            flag_counts[key] = flag_counts.get(key, 0) + 1

    if not stats_only and coll._dirty:
        coll.flush()

    logger.info(f"  {total_flagged} docs flagged ({100 * total_flagged // len(docs)}%)")
    for flag, count in sorted(flag_counts.items(), key=lambda x: -x[1]):
        logger.info(f"    {count:>5}  {flag}")

    return total_flagged


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("collections", nargs="*", help="Collections to flag (default: all)")
    parser.add_argument("--stats", action="store_true", help="Show stats only, don't modify")
    args = parser.parse_args()

    store = DocStore()
    collections = args.collections or store.list_collections()

    total = 0
    for name in collections:
        total += flag_collection(store, name, stats_only=args.stats)

    logger.info(f"\nTotal flagged across all collections: {total}")
    store.close()


if __name__ == "__main__":
    main()
