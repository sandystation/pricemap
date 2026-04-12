"""
Scrape precise GPS coordinates from imot.bg listings.

Requires login to access the map data. Coordinates are in a hidden
<input name="mapn" value="lat,lon,1"> field on each listing page.

Usage (run from scripts/ directory):
    python scrape_imot_coords.py                    # scrape all without coords
    python scrape_imot_coords.py --max 100          # test on 100 docs
    python scrape_imot_coords.py --parallel 10      # 10 parallel sessions
    python scrape_imot_coords.py --stats             # show coordinate coverage
    python scrape_imot_coords.py --force              # re-scrape even if coords exist
"""

import argparse
import logging
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import httpx
from dotenv import load_dotenv
from tqdm import tqdm

from docstore import DocStore

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

LOGIN_URL = "https://www.imot.bg/pcgi/imot.cgi"
DELAY = 0.3  # seconds between requests per thread


def create_session() -> httpx.Client:
    """Create an authenticated httpx session."""
    username = os.environ.get("IMOT_BG_USERNAME")
    password = os.environ.get("IMOT_BG_PASSWORD")

    if not username or not password:
        raise ValueError("IMOT_BG_USERNAME and IMOT_BG_PASSWORD must be set in .env")

    client = httpx.Client(
        timeout=15,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/131.0.0.0"},
        follow_redirects=True,
    )

    resp = client.post(LOGIN_URL, data={
        "act": "26",
        "logact": "1",
        "login_flag": "5",
        "logtype": "2",
        "usr": username,
        "pwd": password,
        "remember_login": "1",
    })

    if "imot_session" not in dict(client.cookies):
        raise ValueError("Login failed -- no session cookie")

    return client


def extract_coords(html: str) -> tuple[float, float] | None:
    """Extract lat/lon from the mapn hidden field."""
    match = re.search(r'name="mapn"\s+value="([^"]+)"', html)
    if not match:
        return None
    parts = match.group(1).split(",")
    if len(parts) >= 2:
        try:
            lat = float(parts[0])
            lon = float(parts[1])
            if 41.0 < lat < 44.5 and 22.0 < lon < 29.0:
                return (lat, lon)
        except ValueError:
            pass
    return None


def fetch_coords(client: httpx.Client, url: str) -> tuple[str, tuple[float, float] | None, str | None]:
    """Fetch a listing page and extract coordinates. Returns (url, coords, error)."""
    for attempt in range(3):
        try:
            resp = client.get(url)
            resp.encoding = "windows-1251"

            if resp.status_code == 404:
                return (url, None, "404")
            if resp.status_code == 429 or resp.status_code >= 500:
                time.sleep(2 ** attempt + 1)
                continue

            coords = extract_coords(resp.text)
            return (url, coords, None)
        except Exception as e:
            if attempt < 2:
                time.sleep(2 ** attempt)
                continue
            return (url, None, str(e))

    return (url, None, "max retries")


def scrape_coords(max_docs: int | None = None, parallel: int = 5, force: bool = False):
    """Scrape coordinates for all bg_imot docs."""
    store = DocStore()
    coll = store.collection("bg_imot")
    coll._ensure_loaded()

    to_process = []
    for doc_id, doc in coll._docs.items():
        cur = doc.get("current", {})
        url = cur.get("url")
        if not url:
            continue
        if not force and cur.get("map_lat") is not None:
            continue  # already scraped map coords
        to_process.append((doc_id, url))

    if max_docs:
        to_process = to_process[:max_docs]

    if not to_process:
        logger.info("No docs to process.")
        store.close()
        return

    logger.info(f"Scraping coordinates for {len(to_process)} docs with {parallel} threads")

    # Create one session per thread
    sessions = []
    for _ in range(parallel):
        try:
            s = create_session()
            sessions.append(s)
        except Exception as e:
            logger.error(f"Failed to create session: {e}")
            if not sessions:
                store.close()
                return
            break

    logger.info(f"Created {len(sessions)} authenticated sessions")

    found = 0
    not_found = 0
    errors = 0
    session_idx = 0

    def _fetch_one(doc_id_url):
        nonlocal session_idx
        doc_id, url = doc_id_url
        idx = session_idx % len(sessions)
        session_idx += 1
        client = sessions[idx]
        time.sleep(DELAY)
        return (doc_id, *fetch_coords(client, url))

    pbar = tqdm(total=len(to_process), unit="doc", desc="Scraping coords",
                dynamic_ncols=True)

    try:
        with ThreadPoolExecutor(max_workers=parallel) as executor:
            futures = {
                executor.submit(_fetch_one, item): item
                for item in to_process
            }

            for fut in as_completed(futures):
                try:
                    doc_id, url, coords, error = fut.result()
                except Exception as e:
                    errors += 1
                    pbar.update(1)
                    continue

                if error:
                    errors += 1
                elif coords:
                    lat, lon = coords
                    doc = coll._docs[doc_id]
                    doc["current"]["map_lat"] = lat
                    doc["current"]["map_lon"] = lon
                    coll._mark_dirty()
                    found += 1
                else:
                    not_found += 1

                pbar.set_postfix(found=found, none=not_found, err=errors)
                pbar.update(1)

                if (found + not_found + errors) % 500 == 0:
                    coll.flush()

    except KeyboardInterrupt:
        logger.info("Interrupted -- flushing.")
    finally:
        pbar.close()
        coll.flush()
        for s in sessions:
            s.close()
        store.close()

    logger.info(f"Done. Found: {found}, No coords: {not_found}, Errors: {errors}")


def print_stats():
    store = DocStore()
    coll = store.collection("bg_imot")
    coll._ensure_loaded()

    total = len(coll._docs)
    has_map = sum(1 for d in coll._docs.values() if d["current"].get("map_lat"))
    has_geo = sum(1 for d in coll._docs.values() if d["current"].get("lat"))

    print(f"\nbg_imot coordinate coverage ({total} docs):")
    print(f"  Neighborhood geocoding (lat/lon): {has_geo} ({100*has_geo/total:.0f}%)")
    print(f"  Precise map coords (map_lat/map_lon): {has_map} ({100*has_map/total:.0f}%)")

    for lt in ["sale", "rent"]:
        subset = [d for d in coll._docs.values() if d["current"].get("listing_type") == lt]
        geo = sum(1 for d in subset if d["current"].get("lat"))
        mp = sum(1 for d in subset if d["current"].get("map_lat"))
        print(f"  {lt}: geo={geo}/{len(subset)}, map={mp}/{len(subset)}")

    store.close()


def main():
    parser = argparse.ArgumentParser(description="Scrape GPS coordinates from imot.bg")
    parser.add_argument("--max", type=int, help="Max docs to process")
    parser.add_argument("--parallel", type=int, default=5, help="Parallel sessions (default: 5)")
    parser.add_argument("--force", action="store_true", help="Re-scrape even if coords exist")
    parser.add_argument("--stats", action="store_true", help="Show coverage stats")
    args = parser.parse_args()

    if args.stats:
        print_stats()
    else:
        scrape_coords(max_docs=args.max, parallel=args.parallel, force=args.force)


if __name__ == "__main__":
    main()
