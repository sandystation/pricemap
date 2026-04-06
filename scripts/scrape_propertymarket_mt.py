"""
PropertyMarket.com.mt scraper - Malta's largest listing portal.

Strategy:
1. Browse for-sale listings with pagination
2. Collect detail page URLs
3. Parse each detail page for price, description, images, specs
4. Store in SQLite

Notes:
- Site returns 403 for basic requests; needs realistic browser headers + cookies
- Detail URLs: /view/{bedrooms}-bedroom-{type}-for-sale-{location}-{id}
- Data is in HTML (no JSON-LD for properties)
- ~38,000 total listings, ~10 per page
"""

import json
import logging
import re
import time

from bs4 import BeautifulSoup

from scraper_base import (
    get_client,
    get_db,
    save_property,
    download_images,
    start_scrape_run,
    finish_scrape_run,
)

logger = logging.getLogger("propertymarket_mt")

BASE = "https://www.propertymarket.com.mt"

# Property categories to scrape
CATEGORIES = [
    ("/for-sale/apartments/", "apartment"),
    ("/for-sale/penthouses/", "penthouse"),
    ("/for-sale/maisonettes/", "maisonette"),
    ("/for-sale/villas/", "house"),
    ("/for-sale/houses-of-character/", "house"),
    ("/for-sale/bungalows/", "house"),
]

MAX_PAGES_PER_CATEGORY = 3  # ~10 listings per page = ~30 per category
DELAY = 2.5  # Respectful delay


def get_mt_client():
    """Create client with Malta-specific headers to avoid 403."""
    return get_client(
        headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-GB,en;q=0.9,mt;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Sec-Ch-Ua": '"Chromium";v="131", "Not_A Brand";v="24"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"macOS"',
            "Cache-Control": "max-age=0",
            "Upgrade-Insecure-Requests": "1",
            "Referer": "https://www.google.com/",
        }
    )


def parse_listing_page(html: str) -> list[str]:
    """Extract detail page URLs from a listing page."""
    soup = BeautifulSoup(html, "lxml")
    urls = set()

    for link in soup.find_all("a", href=True):
        href = link["href"]
        if "/view/" in href and href not in urls:
            if href.startswith("/"):
                href = BASE + href
            urls.add(href)

    return list(urls)


def parse_detail_page(html: str, url: str) -> dict:
    """Parse a PropertyMarket.com.mt detail page."""
    soup = BeautifulSoup(html, "lxml")
    data = {"url": url}

    # Title from h1
    h1 = soup.find("h1")
    if h1:
        data["title"] = h1.get_text().strip()

    # Price from h2 or any element containing €
    for el in soup.find_all(["h2", "span", "div", "p"]):
        text = el.get_text().strip()
        price_match = re.search(r"€\s*([\d,]+(?:\.\d+)?)", text)
        if price_match:
            price_str = price_match.group(1).replace(",", "")
            try:
                data["price_eur"] = float(price_str)
            except ValueError:
                pass
            break

    # Parse title for bedrooms, type, location
    title = data.get("title", "")
    bed_match = re.search(r"(\d+)\s*[Bb]edroom", title)
    if bed_match:
        data["bedrooms"] = int(bed_match.group(1))

    # Location from title: "X Bedroom Type For Sale in Location"
    loc_match = re.search(r"(?:[Ff]or\s+[Ss]ale|[Ff]or\s+[Rr]ent)\s+in\s+(.+?)$", title)
    if loc_match:
        data["locality"] = loc_match.group(1).strip()

    # Type from title
    title_lower = title.lower()
    if "penthouse" in title_lower:
        data["property_type"] = "penthouse"
    elif "maisonette" in title_lower:
        data["property_type"] = "maisonette"
    elif "villa" in title_lower:
        data["property_type"] = "villa"
    elif "house" in title_lower or "townhouse" in title_lower:
        data["property_type"] = "house"
    elif "bungalow" in title_lower:
        data["house"] = "house"
    elif "studio" in title_lower:
        data["property_type"] = "studio"
    elif "apartment" in title_lower or "flat" in title_lower:
        data["property_type"] = "apartment"

    # Parse all text for specs
    page_text = soup.get_text(separator="\n")

    # Size/Area
    size_match = re.search(r"[Ss]ize[:\s]*(\d+)\s*(?:sqm|sq\.?\s*m|m²)", page_text)
    if size_match:
        data["area_sqm"] = float(size_match.group(1))
    else:
        # Try another pattern
        sqm_match = re.search(r"(\d+)\s*(?:sqm|sq\.?\s*m|m²)", page_text)
        if sqm_match:
            data["area_sqm"] = float(sqm_match.group(1))

    # Bathrooms
    bath_match = re.search(r"[Bb]athroom[s]?[:\s]*(\d+)", page_text)
    if bath_match:
        data["bathrooms"] = int(bath_match.group(1))

    # Reference
    ref_match = re.search(r"[Rr]ef[:\s]*([A-Z0-9]+)", page_text)
    if ref_match:
        data["reference"] = ref_match.group(1)

    # Floor
    floor_match = re.search(r"[Ff]loor[:\s]*(\d+)", page_text)
    if floor_match:
        data["floor"] = int(floor_match.group(1))

    # Year
    year_match = re.search(r"[Yy]ear\s*(?:[Bb]uilt)?[:\s]*(\d{4})", page_text)
    if year_match:
        data["year_built"] = int(year_match.group(1))

    # Description - look for substantial text blocks
    desc_candidates = []
    for p in soup.find_all(["p", "div"]):
        text = p.get_text().strip()
        if len(text) > 100 and "€" not in text[:20] and "cookie" not in text.lower():
            desc_candidates.append(text)
    if desc_candidates:
        data["description"] = max(desc_candidates, key=len)

    # Images
    image_urls = []
    for img in soup.find_all("img"):
        src = img.get("src", "")
        if "/wp-content/plugins/property-market/files/" in src and "_thumb" not in src:
            if src.startswith("/"):
                src = BASE + src
            image_urls.append(src)
    # Also try thumbnail URLs and convert to full
    if not image_urls:
        for img in soup.find_all("img"):
            src = img.get("src", "")
            if "/wp-content/plugins/property-market/files/" in src:
                full_src = src.replace("_thumb", "")
                if full_src.startswith("/"):
                    full_src = BASE + full_src
                image_urls.append(full_src)
    data["image_urls"] = list(dict.fromkeys(image_urls))  # dedupe preserving order

    # Agent info
    for strong in soup.find_all("strong"):
        text = strong.get_text().strip()
        if text and "marketed by" not in text.lower() and len(text) < 50:
            # Check if it's near a "marketed by" label
            parent = strong.find_parent()
            if parent:
                parent_text = parent.get_text().lower()
                if "marketed" in parent_text or "agent" in parent_text:
                    data["agent_name"] = text

    # Phone
    for a in soup.find_all("a", href=True):
        if a["href"].startswith("tel:"):
            data["agent_phone"] = a["href"].replace("tel:", "").strip()
            break

    # Amenities from common keywords in text
    text_lower = page_text.lower()
    data["has_parking"] = 1 if "parking" in text_lower or "garage" in text_lower else 0
    data["has_pool"] = 1 if "pool" in text_lower else 0
    data["has_garden"] = 1 if "garden" in text_lower else 0
    data["has_elevator"] = 1 if "lift" in text_lower or "elevator" in text_lower else 0
    data["has_balcony"] = 1 if "balcony" in text_lower or "terrace" in text_lower else 0

    return data


def scrape_category(client, conn, category_path: str, default_type: str, run_id: int):
    """Scrape a single property category."""
    items_scraped = 0
    items_new = 0
    errors = 0

    for page in range(1, MAX_PAGES_PER_CATEGORY + 1):
        url = f"{BASE}{category_path}?pp={page}"
        logger.info(f"Fetching listing page: {url}")

        try:
            resp = client.get(url)
            if resp.status_code == 403:
                logger.warning(f"403 Forbidden - site blocking requests. Trying with cookies...")
                # Try getting homepage first to get cookies
                client.get(BASE)
                time.sleep(1)
                resp = client.get(url)

            if resp.status_code != 200:
                logger.warning(f"Got {resp.status_code} for {url}")
                errors += 1
                continue
        except Exception as e:
            logger.error(f"Failed to fetch {url}: {e}")
            errors += 1
            continue

        detail_urls = parse_listing_page(resp.text)
        if not detail_urls:
            logger.info(f"No listings on page {page}, stopping")
            break

        logger.info(f"Found {len(detail_urls)} detail URLs on page {page}")
        time.sleep(DELAY)

        for detail_url in detail_urls:
            # Extract ID from URL
            ext_id = detail_url.rstrip("/").split("-")[-1]

            # Check if already scraped
            existing = conn.execute(
                "SELECT id FROM properties WHERE source='mt_propertymarket' AND external_id=?",
                (ext_id,),
            ).fetchone()
            if existing:
                items_scraped += 1
                continue

            logger.info(f"  Scraping: {detail_url}")
            try:
                resp = client.get(detail_url)
                if resp.status_code != 200:
                    logger.warning(f"  Got {resp.status_code}")
                    errors += 1
                    time.sleep(DELAY)
                    continue
            except Exception as e:
                logger.error(f"  Failed: {e}")
                errors += 1
                time.sleep(DELAY)
                continue

            detail = parse_detail_page(resp.text, detail_url)

            # Build record
            record = {
                "country_code": "MT",
                "source": "mt_propertymarket",
                "external_id": ext_id,
                "url": detail_url,
                "title": detail.get("title", ""),
                "description": detail.get("description", ""),
                "address_raw": detail.get("locality", ""),
                "locality": detail.get("locality", ""),
                "property_type": detail.get("property_type", default_type),
                "area_sqm": detail.get("area_sqm"),
                "floor": detail.get("floor"),
                "rooms": detail.get("bedrooms"),  # Malta uses bedrooms as room count
                "bedrooms": detail.get("bedrooms"),
                "bathrooms": detail.get("bathrooms"),
                "year_built": detail.get("year_built"),
                "price_eur": detail.get("price_eur"),
                "price_original": detail.get("price_eur"),
                "price_currency": "EUR",
                "price_type": "asking",
                "price_per_sqm": (
                    round(detail["price_eur"] / detail["area_sqm"], 2)
                    if detail.get("price_eur") and detail.get("area_sqm")
                    else None
                ),
                "price_adjusted_eur": (
                    round(detail["price_eur"] * 0.97, 2)
                    if detail.get("price_eur") else None
                ),
                "has_parking": detail.get("has_parking"),
                "has_pool": detail.get("has_pool"),
                "has_garden": detail.get("has_garden"),
                "has_elevator": detail.get("has_elevator"),
                "has_balcony": detail.get("has_balcony"),
                "agent_name": detail.get("agent_name"),
                "agent_phone": detail.get("agent_phone"),
                "image_urls": detail.get("image_urls", []),
                "image_local_paths": [],
                "raw_json": {
                    "reference": detail.get("reference"),
                    "original_title": detail.get("title"),
                },
            }

            # Download images
            if record["image_urls"]:
                record["image_local_paths"] = download_images(
                    client, record["image_urls"], "mt_propertymarket", ext_id
                )

            prop_id, is_new = save_property(conn, record)
            items_scraped += 1
            if is_new:
                items_new += 1
                logger.info(
                    f"  NEW #{prop_id}: {record['title'][:60]} | {record.get('price_eur')} EUR"
                )

            time.sleep(DELAY)

    return items_scraped, items_new, errors


def main():
    conn = get_db()
    client = get_mt_client()
    run_id = start_scrape_run(conn, "mt_propertymarket", "MT")

    total_scraped = 0
    total_new = 0
    total_errors = 0

    try:
        for cat_path, cat_type in CATEGORIES:
            logger.info(f"\n{'='*60}")
            logger.info(f"Scraping category: {cat_path}")
            logger.info(f"{'='*60}")
            scraped, new, errors = scrape_category(
                client, conn, cat_path, cat_type, run_id
            )
            total_scraped += scraped
            total_new += new
            total_errors += errors
    finally:
        finish_scrape_run(conn, run_id, total_scraped, total_new, total_errors)
        client.close()
        conn.close()

    logger.info(f"\nDONE: {total_scraped} total, {total_new} new, {total_errors} errors")


if __name__ == "__main__":
    main()
