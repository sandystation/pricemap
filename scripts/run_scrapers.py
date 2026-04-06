#!/usr/bin/env python3
"""
Run all property scrapers.

Usage:
    python scripts/run_scrapers.py              # Run all scrapers
    python scripts/run_scrapers.py remax        # Run only RE/MAX Malta
    python scripts/run_scrapers.py maltapark    # Run only MaltaPark
    python scripts/run_scrapers.py imot         # Run only Imot.bg
    python scripts/run_scrapers.py remax imot   # Run RE/MAX + Imot.bg
    python scripts/run_scrapers.py --status     # Show collection stats only
"""

import importlib
import logging
import sys
import time

from docstore import DocStore

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("runner")

SCRAPERS = {
    "remax": {
        "module": "scrape_remax_mt",
        "name": "RE/MAX Malta",
        "country": "MT",
        "description": "JSON API, ~32K listings with GPS coordinates",
    },
    "maltapark": {
        "module": "scrape_maltapark",
        "name": "MaltaPark",
        "country": "MT",
        "description": "HTML scraper, ~4K listings with descriptions",
    },
    "imot": {
        "module": "scrape_imot_bg",
        "name": "Imot.bg",
        "country": "BG",
        "description": "HTML+JSON-LD, 35 Bulgarian cities",
    },
}


def show_status():
    store = DocStore()
    print("\n=== PriceMap Collection Status ===\n")
    total = 0
    for name in store.list_collections():
        if name.startswith("_"):
            continue
        coll = store.collection(name)
        n = coll.count()
        total += n
        # Count with prices
        with_price = sum(1 for d in coll.find() if d["current"].get("price_eur"))
        with_imgs = sum(1 for d in coll.find() if d["current"].get("image_urls"))
        print(f"  {name:<20} {n:>6} docs  ({with_price} with price, {with_imgs} with images)")

    # Show recent scrape runs
    runs_coll = store.collection("_scrape_runs")
    runs = runs_coll.find()
    runs.sort(key=lambda r: r.get("started_at", ""), reverse=True)
    if runs:
        print(f"\nRecent scrape runs:")
        for r in runs[:5]:
            status = r.get("status", "?")
            spider = r.get("spider_name", "?")
            scraped = r.get("items_scraped", 0)
            new = r.get("items_new", 0)
            started = (r.get("started_at") or "")[:19]
            print(f"  {started}  {spider:<18} {status:<10} scraped={scraped} new={new}")

    print(f"\nTotal: {total} properties")
    store.close()


def run_scraper(key: str, info: dict):
    logger.info(f"\n{'='*60}")
    logger.info(f"Starting {info['name']} ({info['description']})")
    logger.info(f"{'='*60}")

    start = time.time()
    try:
        mod = importlib.import_module(info["module"])
        mod.main()
        elapsed = time.time() - start
        logger.info(f"{info['name']} finished in {elapsed:.0f}s")
    except KeyboardInterrupt:
        logger.info(f"{info['name']} interrupted by user")
        raise
    except Exception as e:
        elapsed = time.time() - start
        logger.error(f"{info['name']} failed after {elapsed:.0f}s: {e}")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    flags = [a for a in sys.argv[1:] if a.startswith("-")]

    if "--status" in flags or "-s" in flags:
        show_status()
        return

    if "--help" in flags or "-h" in flags:
        print(__doc__)
        return

    # Determine which scrapers to run
    if args:
        to_run = []
        for a in args:
            a_lower = a.lower()
            if a_lower in SCRAPERS:
                to_run.append((a_lower, SCRAPERS[a_lower]))
            else:
                print(f"Unknown scraper: {a}")
                print(f"Available: {', '.join(SCRAPERS.keys())}")
                sys.exit(1)
    else:
        to_run = list(SCRAPERS.items())

    logger.info(f"Running {len(to_run)} scraper(s): {', '.join(k for k, _ in to_run)}")
    total_start = time.time()

    for key, info in to_run:
        run_scraper(key, info)

    total_elapsed = time.time() - total_start
    logger.info(f"\nAll scrapers finished in {total_elapsed:.0f}s")

    # Show final status
    show_status()


if __name__ == "__main__":
    main()
