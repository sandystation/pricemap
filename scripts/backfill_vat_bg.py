"""
Backfill VAT status for bg_imot listings and cache full HTML.

Fetches each listing page, extracts VAT status, and saves the full HTML
(gzipped) for future re-scraping without hitting the server again.

Usage (run from scripts/ directory):
    python backfill_vat_bg.py              # backfill all unprocessed
    python backfill_vat_bg.py --max 100    # process 100 docs
    python backfill_vat_bg.py --stats      # show VAT distribution
    python backfill_vat_bg.py --force-html  # re-download HTML even if vat_status set
"""

import argparse
import gzip
import logging
import os
import time
from collections import Counter

import httpx

from docstore import DocStore

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

HTML_CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "html_cache", "bg_imot")
VAT_RATE = 0.20


def _html_cache_path(doc_id: str) -> str:
    """Get cache path for a doc's HTML. E.g., bg_imot:1b176839... -> 1b176839....html.gz"""
    short_id = doc_id.split(":")[-1] if ":" in doc_id else doc_id
    return os.path.join(HTML_CACHE_DIR, f"{short_id}.html.gz")


def extract_vat_status(html: str) -> str:
    """Extract VAT status from imot.bg listing HTML."""
    if "без ДДС" in html:
        return "excluded"
    if "с включено ДДС" in html:
        return "included"
    return "unknown"


def backfill(max_docs: int | None = None, force_html: bool = False):
    os.makedirs(HTML_CACHE_DIR, exist_ok=True)

    store = DocStore()
    coll = store.collection("bg_imot")
    coll._ensure_loaded()

    to_process = []
    for doc_id, doc in coll._docs.items():
        cur = doc.get("current", {})
        url = cur.get("url")
        if not url:
            continue

        has_vat = cur.get("vat_status") is not None
        has_html = os.path.exists(_html_cache_path(doc_id))

        # Skip if both VAT and HTML are done (unless force_html)
        if has_vat and has_html and not force_html:
            continue
        # Skip if VAT is set and we don't need HTML
        if has_vat and not force_html and has_html:
            continue

        to_process.append((doc_id, url, has_vat, has_html))

    if max_docs:
        to_process = to_process[:max_docs]

    if not to_process:
        logger.info("All docs already processed.")
        return

    need_fetch = sum(1 for _, _, _, has_html in to_process if not has_html)
    need_vat = sum(1 for _, _, has_vat, _ in to_process if not has_vat)
    logger.info(f"Processing {len(to_process)} docs (need_fetch={need_fetch}, need_vat={need_vat})")
    logger.info(f"HTML cache: {HTML_CACHE_DIR}")

    client = httpx.Client(
        timeout=15,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/131.0.0.0"},
        follow_redirects=True,
    )

    processed = 0
    errors = 0
    html_saved = 0
    stats = {"excluded": 0, "included": 0, "unknown": 0}

    try:
        for i, (doc_id, url, has_vat, has_html) in enumerate(to_process):
            html_text = None

            # Read from cache if HTML exists
            if has_html and has_vat:
                processed += 1
                continue

            cache_path = _html_cache_path(doc_id)

            if has_html and not has_vat:
                # HTML cached, just need VAT extraction
                try:
                    with gzip.open(cache_path, "rt", encoding="windows-1251") as f:
                        html_text = f.read()
                except Exception:
                    has_html = False  # corrupt cache, re-fetch

            if not has_html:
                # Fetch from server
                try:
                    resp = client.get(url)
                    resp.encoding = "windows-1251"
                    html_text = resp.text

                    # Save HTML
                    with gzip.open(cache_path, "wt", encoding="windows-1251") as f:
                        f.write(html_text)
                    html_saved += 1
                except Exception as e:
                    logger.warning(f"Error fetching {doc_id}: {e}")
                    errors += 1
                    continue

                time.sleep(1.0)

            # Extract VAT
            if html_text and not has_vat:
                vat_status = extract_vat_status(html_text)
                doc = coll._docs[doc_id]
                doc["current"]["vat_status"] = vat_status
                coll._mark_dirty()
                stats[vat_status] += 1

            processed += 1

            if (i + 1) % 100 == 0:
                coll.flush()
                logger.info(
                    f"Progress: {i+1}/{len(to_process)} "
                    f"(excluded={stats['excluded']}, included={stats['included']}, "
                    f"unknown={stats['unknown']}, html_saved={html_saved}, errors={errors})"
                )

    except KeyboardInterrupt:
        logger.info("Interrupted -- flushing.")
    finally:
        coll.flush()
        client.close()
        store.close()

    logger.info(
        f"Done. Processed: {processed}, HTML saved: {html_saved}, Errors: {errors}, "
        f"excluded={stats['excluded']}, included={stats['included']}, unknown={stats['unknown']}"
    )


def print_stats():
    store = DocStore()
    coll = store.collection("bg_imot")
    coll._ensure_loaded()

    vat = Counter()
    total = 0
    for doc in coll._docs.values():
        cur = doc.get("current", {})
        if cur.get("property_type") == "apartment":
            total += 1
            vat[cur.get("vat_status", "NOT SET")] += 1

    print(f"\nVAT status for bg_imot apartments ({total} total):")
    for k, v in vat.most_common():
        print(f"  {k:15s}: {v:>5d} ({100*v/total:.1f}%)")

    # HTML cache stats
    if os.path.exists(HTML_CACHE_DIR):
        html_count = len([f for f in os.listdir(HTML_CACHE_DIR) if f.endswith(".html.gz")])
        total_docs = len(coll._docs)
        print(f"\nHTML cache: {html_count}/{total_docs} docs ({100*html_count/total_docs:.1f}%)")

    # Cross-tab with construction status from LLM
    from llm_enrich import load_run
    try:
        llm_data = load_run("bg_imot_v1_images")
        print(f"\nVAT by construction status (LLM):")
        for status in ["completed", "under_construction", "off_plan"]:
            docs_with_status = [
                d for d in coll._docs.values()
                if d.get("current", {}).get("property_type") == "apartment"
                and llm_data.get(d["_id"], {}).get("construction_status") == status
                and d["current"].get("vat_status") is not None
            ]
            if docs_with_status:
                excluded = sum(1 for d in docs_with_status if d["current"]["vat_status"] == "excluded")
                included = sum(1 for d in docs_with_status if d["current"]["vat_status"] == "included")
                unknown = sum(1 for d in docs_with_status if d["current"]["vat_status"] == "unknown")
                total_s = len(docs_with_status)
                print(f"  {status:20s}: excluded={excluded} ({100*excluded/total_s:.0f}%), "
                      f"included={included} ({100*included/total_s:.0f}%), "
                      f"unknown={unknown} ({100*unknown/total_s:.0f}%)")
    except FileNotFoundError:
        pass

    store.close()


def main():
    parser = argparse.ArgumentParser(description="Backfill VAT status + cache HTML for bg_imot")
    parser.add_argument("--max", type=int, help="Max docs to process")
    parser.add_argument("--stats", action="store_true", help="Show VAT distribution")
    parser.add_argument("--force-html", action="store_true", help="Re-download HTML even if cached")
    args = parser.parse_args()

    if args.stats:
        print_stats()
    else:
        backfill(max_docs=args.max, force_html=args.force_html)


if __name__ == "__main__":
    main()
