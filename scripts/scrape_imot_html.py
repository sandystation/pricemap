"""
Parallel HTML scraper for imot.bg. Downloads and caches full listing pages.

Scrapes both sales and rentals across all Bulgarian cities, saves gzipped HTML
to data/html_cache/bg_imot/. Once cached, any field can be extracted offline
without hitting the server again.

Also runs the full scraper pipeline (parse, store in DocStore) for new listings.

Usage (run from scripts/ directory):
    python scrape_imot_html.py                          # scrape sales + rentals
    python scrape_imot_html.py --listing-type sale      # sales only
    python scrape_imot_html.py --listing-type rent      # rentals only
    python scrape_imot_html.py --parallel 5             # 5 parallel fetchers
    python scrape_imot_html.py --html-only              # just cache HTML, don't update DocStore
    python scrape_imot_html.py --stats                  # show cache stats
"""

import argparse
import gzip
import logging
import os
import re
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed

import httpx
from bs4 import BeautifulSoup
from tqdm import tqdm

from scraper_base import get_store, start_scrape_run, finish_scrape_run, download_images

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

BASE = "https://www.imot.bg"
HTML_CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "html_cache", "bg_imot")
MAX_PAGES_PER_CITY = 100
DELAY = 0.3  # per-thread delay

# Import city list and parsers from main scraper
from scrape_imot_bg import (
    CITIES, parse_search_page, parse_detail_page,
    detect_property_type, detect_rooms, LISTING_TYPE_SLUGS,
)

LISTING_TYPES = ["sale", "rent"]

# Property type sub-slugs for breaking the 1000/city pagination limit
# Crawl each type separately to get all listings
PROPERTY_TYPE_SLUGS = [
    "ednostaen",     # 1-room apartment
    "dvustaen",      # 2-room apartment
    "tristaen",      # 3-room apartment
    "mnogostaen",    # 4+ room apartment
    "mezonet",       # maisonette
    "kashta",        # house
    "ofis",          # office
    "magazin",       # shop
]


def _html_cache_path(obiava_id: str) -> str:
    return os.path.join(HTML_CACHE_DIR, f"{obiava_id}.html.gz")


def _save_html(obiava_id: str, html_bytes: bytes):
    path = _html_cache_path(obiava_id)
    with gzip.open(path, "wb") as f:
        f.write(html_bytes)


def _load_html(obiava_id: str) -> str | None:
    path = _html_cache_path(obiava_id)
    if not os.path.exists(path):
        return None
    try:
        with gzip.open(path, "rb") as f:
            return f.read().decode("windows-1251", errors="replace")
    except Exception:
        return None


def collect_listing_urls(listing_type: str, parallel: int = 3) -> list[tuple[str, str]]:
    """Crawl search pages to collect all listing URLs. Returns [(url, city_name)].

    Crawls each city × property type combination to bypass the ~1000
    listings per search pagination limit on imot.bg.
    """
    type_slug = LISTING_TYPE_SLUGS[listing_type]
    all_urls = []

    def _crawl_pages(base_search_url: str, city_name: str) -> list[tuple[str, str]]:
        """Crawl all pages for one search URL."""
        urls = []
        client = httpx.Client(
            timeout=15,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/131.0.0.0"},
            follow_redirects=True,
        )
        try:
            for page in range(1, MAX_PAGES_PER_CITY + 1):
                search_url = base_search_url if page == 1 else f"{base_search_url}/p-{page}"

                resp = None
                for attempt in range(3):
                    try:
                        resp = client.get(search_url)
                        resp.encoding = "windows-1251"
                        if resp.status_code == 200:
                            break
                        if resp.status_code == 429 or resp.status_code >= 500:
                            time.sleep(2 ** attempt + 1)
                            continue
                        break
                    except Exception:
                        if attempt < 2:
                            time.sleep(2 ** attempt)
                        continue

                if not resp or resp.status_code != 200:
                    break

                listings = parse_search_page(resp.text)
                if not listings:
                    break

                for listing in listings:
                    u = listing["url"]
                    if u.startswith("//"):
                        u = "https:" + u
                    elif u.startswith("/"):
                        u = BASE + u
                    urls.append((u, city_name))

                time.sleep(DELAY)
        finally:
            client.close()
        return urls

    # Build all (city, property_type) combinations to crawl
    crawl_tasks = []
    for city_slug, city_name in CITIES:
        for prop_slug in PROPERTY_TYPE_SLUGS:
            base_url = f"{BASE}/obiavi/{type_slug}/{city_slug}/{prop_slug}"
            crawl_tasks.append((base_url, city_name, city_slug, prop_slug))

    logger.info(
        f"Collecting {listing_type} URLs: {len(CITIES)} cities × "
        f"{len(PROPERTY_TYPE_SLUGS)} property types = {len(crawl_tasks)} search combinations"
    )

    city_counts = {}
    with ThreadPoolExecutor(max_workers=parallel) as executor:
        futures = {
            executor.submit(_crawl_pages, base_url, city_name): (city_name, prop_slug)
            for base_url, city_name, city_slug, prop_slug in crawl_tasks
        }
        for fut in tqdm(as_completed(futures), total=len(futures), desc="Collecting URLs", unit="search"):
            city_name, prop_slug = futures[fut]
            try:
                urls = fut.result()
                all_urls.extend(urls)
                city_counts[city_name] = city_counts.get(city_name, 0) + len(urls)
            except Exception as e:
                logger.warning(f"  {city_name}/{prop_slug}: error - {e}")

    # Log per-city totals
    for city, count in sorted(city_counts.items(), key=lambda x: -x[1]):
        logger.info(f"  {city}: {count} listings")

    logger.info(f"Total {listing_type} URLs: {len(all_urls)}")
    return all_urls


def fetch_and_cache(url: str, city_name: str, max_retries: int = 3) -> tuple[str, str | None, str | None]:
    """Fetch a listing page, cache HTML, return (obiava_id, html_text, error)."""
    # Extract obiava ID from URL
    match = re.search(r'obiava-(\w+)', url)
    if not match:
        return ("", None, f"No obiava ID in {url}")

    obiava_id = match.group(1)

    # Check cache first
    cached = _load_html(obiava_id)
    if cached:
        return (obiava_id, cached, None)

    # Fetch with retries
    for attempt in range(max_retries):
        try:
            client = httpx.Client(
                timeout=15,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/131.0.0.0"},
                follow_redirects=True,
            )
            resp = client.get(url)
            client.close()

            if resp.status_code == 404:
                return (obiava_id, None, "404")

            if resp.status_code == 429 or resp.status_code >= 500:
                wait = 2 ** attempt + 1
                time.sleep(wait)
                continue

            resp.encoding = "windows-1251"
            _save_html(obiava_id, resp.content)
            return (obiava_id, resp.text, None)
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
                continue
            return (obiava_id, None, f"Failed after {max_retries} retries: {e}")

    return (obiava_id, None, "Max retries exceeded")


def scrape_all(listing_types: list[str], parallel: int = 5, html_only: bool = False):
    """Full scraping pipeline: collect URLs, fetch HTML, parse, store."""
    os.makedirs(HTML_CACHE_DIR, exist_ok=True)

    store = get_store()
    coll = store.collection("bg_imot")

    for listing_type in listing_types:
        logger.info(f"\n{'='*60}")
        logger.info(f"Scraping {listing_type.upper()} listings")
        logger.info(f"{'='*60}")

        # Phase 1: Collect URLs from search pages
        urls = collect_listing_urls(listing_type, parallel=min(parallel, 3))

        # Deduplicate
        seen = set()
        unique_urls = []
        for url, city in urls:
            match = re.search(r'obiava-(\w+)', url)
            if match and match.group(1) not in seen:
                seen.add(match.group(1))
                unique_urls.append((url, city))
        logger.info(f"Unique listings: {len(unique_urls)}")

        # Phase 2: Fetch and cache HTML in parallel
        logger.info(f"Fetching HTML (parallel={parallel})...")
        fetched = 0
        cached = 0
        errors = 0
        failed_urls = []
        results = []  # (obiava_id, html, city_name, url)

        pbar = tqdm(total=len(unique_urls), unit="page", desc=f"Fetching {listing_type}",
                    dynamic_ncols=True)

        with ThreadPoolExecutor(max_workers=parallel) as executor:
            futures = {}
            for url, city in unique_urls:
                fut = executor.submit(fetch_and_cache, url, city)
                futures[fut] = (url, city)

            for fut in as_completed(futures):
                url, city = futures[fut]
                obiava_id, html, error = fut.result()

                if error:
                    errors += 1
                    if error != "404":
                        failed_urls.append((url, error))
                elif html:
                    results.append((obiava_id, html, city, url))
                    if os.path.exists(_html_cache_path(obiava_id)):
                        cached += 1
                    else:
                        fetched += 1

                pbar.set_postfix(fetched=fetched, cached=cached, err=errors)
                pbar.update(1)

        pbar.close()
        logger.info(f"Fetched: {fetched}, From cache: {cached}, Errors: {errors}")

        # Save failed URLs for later retry
        if failed_urls:
            failed_path = os.path.join(HTML_CACHE_DIR, f"_failed_{listing_type}.txt")
            with open(failed_path, "w") as f:
                for fail_url, fail_err in failed_urls:
                    f.write(f"{fail_url}\t{fail_err}\n")
            logger.info(f"Failed URLs saved to {failed_path}")

        if html_only:
            logger.info("HTML-only mode -- skipping DocStore update.")
            continue

        # Phase 3: Parse and store in DocStore
        logger.info(f"Parsing and storing {len(results)} listings...")
        new_docs = 0
        parse_errors = 0

        for obiava_id, html, city_name, url in tqdm(results, desc="Parsing", unit="doc"):
            try:
                detail = parse_detail_page(html, url)

                if not detail:
                    parse_errors += 1
                    continue

                title = detail.get("title", "")
                prop_type = detect_property_type(title)
                rooms = detect_rooms(title)
                locality = detail.get("quarter_name") or city_name
                address = ", ".join([p for p in [detail.get("quarter_name"), city_name] if p])

                # Detect listing type from breadcrumb or use what we're scraping
                lt = detail.get("listing_type", listing_type)

                # Extract VAT status
                vat_status = "unknown"
                if "без ДДС" in html:
                    vat_status = "excluded"
                elif "с включено ДДС" in html:
                    vat_status = "included"

                # Price
                price_eur = detail.get("price_eur")
                price_bgn = detail.get("price_bgn")
                if not price_eur and price_bgn:
                    from scraper_base import BGN_EUR_RATE
                    price_eur = round(price_bgn * BGN_EUR_RATE, 2)

                image_urls = detail.get("image_urls", [])
                local_paths = []
                if image_urls:
                    img_client = httpx.Client(timeout=15, headers={"User-Agent": "Mozilla/5.0"}, follow_redirects=True)
                    try:
                        local_paths = download_images(img_client, image_urls, "bg_imot", obiava_id)
                    finally:
                        img_client.close()

                record = {
                    "country_code": "BG",
                    "source": "bg_imot",
                    "external_id": obiava_id,
                    "url": url,
                    "title": title,
                    "description": detail.get("description", ""),
                    "address_raw": address,
                    "locality": locality,
                    "property_type": prop_type,
                    "listing_type": lt,
                    "rooms": rooms,
                    "area_sqm": detail.get("area_sqm"),
                    "floor": detail.get("floor"),
                    "total_floors": detail.get("total_floors"),
                    "construction_type": detail.get("construction_type"),
                    "price_eur": price_eur,
                    "price_original": detail.get("price_eur") or detail.get("price_bgn"),
                    "price_currency": "EUR" if detail.get("price_eur") else "лв.",
                    "price_adjusted_eur": round(price_eur * 0.97, 2) if price_eur else None,
                    "price_type": "asking",
                    "listing_date": detail.get("listing_date_raw"),
                    "vat_status": vat_status,
                    "has_elevator": detail.get("has_elevator", 0),
                    "has_parking": detail.get("has_parking", 0),
                    "has_garage": detail.get("has_garage", 0),
                    "has_balcony": detail.get("has_balcony", 0),
                    "has_furnishing": detail.get("has_furnishing", 0),
                    "has_garden": detail.get("has_garden", 0),
                    "image_urls": image_urls,
                    "image_local_paths": local_paths,
                }

                doc_id, is_new = coll.save_property(record)
                if is_new:
                    new_docs += 1

            except Exception as e:
                parse_errors += 1
                logger.debug(f"Parse error for {obiava_id}: {e}")

        logger.info(f"Stored: {len(results) - parse_errors}, New: {new_docs}, Parse errors: {parse_errors}")

    coll.close()
    store.close()


def _parse_one_file(args):
    """Parse one cached HTML file. Runs in worker process.

    Returns (record_dict, error_string) -- record is None on error.
    """
    path, obiava_id = args
    try:
        with gzip.open(path, "rb") as f:
            html = f.read().decode("windows-1251", errors="replace")

        url = f"https://www.imot.bg/obiava-{obiava_id}"
        detail = parse_detail_page(html, url)

        if not detail:
            return (None, "empty parse result")

        title = detail.get("title", "")
        prop_type = detect_property_type(title)
        rooms = detect_rooms(title)
        listing_type = detail.get("listing_type", "sale")

        city_name = ""
        city_match = re.search(r'град\s+(\S+)', title)
        if city_match:
            city_name = city_match.group(1).rstrip(",")

        locality = detail.get("quarter_name") or city_name
        address = ", ".join([p for p in [detail.get("quarter_name"), city_name] if p])

        vat_status = "unknown"
        if "без ДДС" in html:
            vat_status = "excluded"
        elif "с включено ДДС" in html:
            vat_status = "included"

        price_eur = detail.get("price_eur")
        price_bgn = detail.get("price_bgn")
        if not price_eur and price_bgn:
            price_eur = round(price_bgn * (1 / 1.95583), 2)

        record = {
            "country_code": "BG",
            "source": "bg_imot",
            "external_id": obiava_id,
            "url": url,
            "title": title,
            "description": detail.get("description", ""),
            "address_raw": address,
            "locality": locality,
            "property_type": prop_type,
            "listing_type": listing_type,
            "rooms": rooms,
            "area_sqm": detail.get("area_sqm"),
            "floor": detail.get("floor"),
            "total_floors": detail.get("total_floors"),
            "construction_type": detail.get("construction_type"),
            "price_eur": price_eur,
            "price_original": detail.get("price_eur") or detail.get("price_bgn"),
            "price_currency": "EUR" if detail.get("price_eur") else "лв.",
            "price_adjusted_eur": round(price_eur * 0.97, 2) if price_eur else None,
            "price_type": "asking",
            "listing_date": detail.get("listing_date_raw"),
            "vat_status": vat_status,
            "has_elevator": detail.get("has_elevator", 0),
            "has_parking": detail.get("has_parking", 0),
            "has_garage": detail.get("has_garage", 0),
            "has_balcony": detail.get("has_balcony", 0),
            "has_furnishing": detail.get("has_furnishing", 0),
            "has_garden": detail.get("has_garden", 0),
            "image_urls": detail.get("image_urls", []),
        }

        return (record, None)
    except Exception as e:
        return (None, str(e))


def parse_all_cached(parallel: int | None = None):
    """Parse all cached HTML files into DocStore using multiple processes."""
    from concurrent.futures import ProcessPoolExecutor

    if not os.path.exists(HTML_CACHE_DIR):
        logger.error(f"No HTML cache at {HTML_CACHE_DIR}")
        return

    if parallel is None:
        parallel = os.cpu_count() or 4

    file_list = [f for f in os.listdir(HTML_CACHE_DIR) if f.endswith(".html.gz")]
    tasks = [
        (os.path.join(HTML_CACHE_DIR, f), f.replace(".html.gz", ""))
        for f in file_list
    ]

    logger.info(f"Parsing {len(tasks)} cached HTML files with {parallel} workers")

    store = get_store()
    coll = store.collection("bg_imot")

    new_docs = 0
    updated_docs = 0
    parse_errors = 0

    try:
        with ProcessPoolExecutor(max_workers=parallel) as executor:
            results = executor.map(_parse_one_file, tasks, chunksize=50)

            for record, error in tqdm(results, total=len(tasks), desc="Parsing", unit="doc",
                                      dynamic_ncols=True):
                if error:
                    parse_errors += 1
                    continue

                if record:
                    doc_id, is_new = coll.save_property(record)
                    if is_new:
                        new_docs += 1
                    else:
                        updated_docs += 1
    except KeyboardInterrupt:
        logger.info("Interrupted -- flushing.")
    finally:
        coll.close()
        store.close()

    logger.info(f"Done. New: {new_docs}, Updated: {updated_docs}, Parse errors: {parse_errors}")


def print_stats():
    if not os.path.exists(HTML_CACHE_DIR):
        print("No HTML cache directory.")
        return

    files = [f for f in os.listdir(HTML_CACHE_DIR) if f.endswith(".html.gz")]
    total_size = sum(os.path.getsize(os.path.join(HTML_CACHE_DIR, f)) for f in files)

    print(f"\nHTML cache: {HTML_CACHE_DIR}")
    print(f"  Files: {len(files)}")
    print(f"  Size: {total_size / 1024 / 1024:.0f} MB")

    # Check DocStore coverage
    store = get_store()
    coll = store.collection("bg_imot")
    coll._ensure_loaded()

    cached_ids = {f.replace(".html.gz", "") for f in files}
    doc_ids = {doc_id.split(":")[-1] for doc_id in coll._docs}
    overlap = cached_ids & doc_ids

    print(f"  DocStore docs: {len(coll._docs)}")
    print(f"  Cached & in DocStore: {len(overlap)}")
    print(f"  Cached but not in DocStore: {len(cached_ids - doc_ids)} (may be rentals)")

    # Listing type distribution
    lt = Counter(d.get("current", {}).get("listing_type", "?") for d in coll._docs.values())
    print(f"  Listing types: {dict(lt)}")

    # VAT coverage
    vat = Counter(d.get("current", {}).get("vat_status", "NOT SET") for d in coll._docs.values())
    print(f"  VAT status: {dict(vat)}")

    store.close()


def main():
    parser = argparse.ArgumentParser(description="Parallel imot.bg HTML scraper")
    parser.add_argument("--listing-type", choices=["sale", "rent"],
                        help="Scrape only this type (default: both)")
    parser.add_argument("--parallel", type=int, default=5,
                        help="Number of parallel fetchers (default: 5)")
    parser.add_argument("--html-only", action="store_true",
                        help="Only cache HTML, don't update DocStore")
    parser.add_argument("--parse-cached", action="store_true",
                        help="Skip URL collection, parse all cached HTML files into DocStore")
    parser.add_argument("--stats", action="store_true",
                        help="Show cache stats")
    args = parser.parse_args()

    if args.stats:
        print_stats()
        return

    if args.parse_cached:
        parse_all_cached(parallel=args.parallel)
        return

    listing_types = [args.listing_type] if args.listing_type else LISTING_TYPES

    scrape_all(listing_types, parallel=args.parallel, html_only=args.html_only)


if __name__ == "__main__":
    main()
