"""
Deduplicate RE/MAX Malta listings.

RE/MAX often creates multiple MLS numbers for the same physical property
(same agent, same coords, same price, same description). This script finds
duplicates and marks them with a `duplicate_of` field pointing to the
canonical doc (the one with the earliest insertion date).

Matching criteria (all must match):
  - Same coordinates (lat/lon)
  - Same price
  - Same area
  - Same property type

Usage:
    cd scripts
    python dedup_remax.py              # Dry run (report only)
    python dedup_remax.py --apply      # Mark duplicates in the data
"""

import argparse
import logging
from collections import defaultdict

from docstore import DocStore

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("dedup_remax")


def build_dedup_key(doc: dict) -> tuple | None:
    """Build a key for grouping potential duplicates.
    Returns None if essential fields are missing.

    Uses price + area + first 100 chars of description.
    Many RE/MAX listings use town-center coords, so coordinates
    alone are not reliable for deduplication. The description
    is the strongest signal that two MLS numbers are the same property."""
    cur = doc.get("current", {})
    price = cur.get("price_eur")
    area = cur.get("area_sqm")
    desc = (cur.get("description") or "").strip()

    # Need price + description to deduplicate reliably
    if price is None or len(desc) < 20:
        return None

    # Normalize: first 100 chars, lowercased
    desc_key = desc[:100].lower()

    return (price, area, desc_key)


def pick_canonical(group: list[dict]) -> dict:
    """Pick the canonical doc from a group of duplicates.
    Prefer: earliest insertion date, then earliest doc_id."""
    def sort_key(doc):
        cur = doc.get("current", {})
        raw = cur.get("raw_data", {})
        insertion = raw.get("InsertionDate", "") or ""
        return (insertion, doc["_id"])

    return sorted(group, key=sort_key)[0]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Apply changes (default is dry run)")
    args = parser.parse_args()

    store = DocStore()
    coll = store.collection("mt_remax")
    coll._ensure_loaded()

    # Group by dedup key
    groups = defaultdict(list)
    skipped = 0
    for doc in coll._docs.values():
        key = build_dedup_key(doc)
        if key is None:
            skipped += 1
            continue
        groups[key].append(doc)

    # Find groups with duplicates
    dup_groups = {k: v for k, v in groups.items() if len(v) > 1}

    total_dups = sum(len(v) - 1 for v in dup_groups.values())
    logger.info(f"Total docs: {len(coll._docs)}")
    logger.info(f"Skipped (missing key fields): {skipped}")
    logger.info(f"Duplicate groups: {len(dup_groups)}")
    logger.info(f"Docs to mark as duplicate: {total_dups}")

    if not dup_groups:
        logger.info("No duplicates found.")
        store.close()
        return

    # Show sample groups
    shown = 0
    for key, group in list(dup_groups.items()):
        if shown >= 5:
            break
        canonical = pick_canonical(group)
        others = [d for d in group if d["_id"] != canonical["_id"]]
        logger.info(
            f"  Group: {canonical['current'].get('title')} | "
            f"{key[2]} EUR | {canonical['current'].get('locality')}"
        )
        logger.info(f"    canonical: {canonical['_id']}")
        for d in others:
            logger.info(f"    duplicate: {d['_id']}")
        shown += 1

    if not args.apply:
        logger.info("Dry run — use --apply to mark duplicates")
        store.close()
        return

    # Apply: mark duplicates
    marked = 0
    # First, clear any stale duplicate_of flags
    for doc in coll._docs.values():
        if "duplicate_of" in doc.get("current", {}):
            del doc["current"]["duplicate_of"]
            coll._dirty = True

    for key, group in dup_groups.items():
        canonical = pick_canonical(group)
        for doc in group:
            if doc["_id"] != canonical["_id"]:
                doc["current"]["duplicate_of"] = canonical["_id"]
                marked += 1

    coll._dirty = True
    coll.flush()
    logger.info(f"Marked {marked} docs as duplicates")
    store.close()


if __name__ == "__main__":
    main()
