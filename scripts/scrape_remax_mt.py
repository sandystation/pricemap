"""
RE/MAX Malta scraper - JSON API, 32K+ listings with GPS coordinates.

Endpoint: https://www.remax-malta.com/api/properties
Pagination: Take=100&Skip=N
No auth required. Returns structured JSON with all fields.
"""

import json
import logging
import time

import httpx

from scraper_base import (
    get_db,
    save_property,
    download_images,
    start_scrape_run,
    finish_scrape_run,
)

logger = logging.getLogger("remax_mt")

API_BASE = "https://www.remax-malta.com/api/properties"
BATCH_SIZE = 100
MAX_LISTINGS = 500  # Limit for initial scrape
DELAY = 1.5

TYPE_MAP = {
    "Apartment": "apartment",
    "Penthouse": "penthouse",
    "Maisonette": "maisonette",
    "Villa": "villa",
    "Terraced House": "house",
    "Semi-Detached Villa": "house",
    "Townhouse": "house",
    "House of Character": "house",
    "Bungalow": "house",
    "Palazzo": "house",
    "Farmhouse": "house",
    "Studio": "studio",
    "Duplex": "apartment",
    "Garage": "commercial",
    "Office": "commercial",
    "Shop": "commercial",
    "Plot": "land",
}


def fetch_batch(client: httpx.Client, skip: int) -> dict:
    """Fetch a batch of properties from the API."""
    params = {
        "Take": BATCH_SIZE,
        "Skip": skip,
        "TransactionTypeId": 0,  # For Sale
    }
    resp = client.get(API_BASE, params=params)
    resp.raise_for_status()
    wrapper = resp.json()
    # API returns {"data": {"Properties": [...], "TotalSearchResults": N}, "status_code": 200}
    inner = wrapper.get("data", wrapper)
    return inner


def process_property(item: dict) -> dict:
    """Convert API response item to our property record format."""
    coords = item.get("Coordinates") or {}
    price_raw = item.get("Price")
    try:
        price = float(str(price_raw).replace(",", "")) if price_raw else None
    except (ValueError, TypeError):
        price = None
    area_raw = item.get("TotalSqm") or item.get("TotalIntArea")
    try:
        area = float(str(area_raw)) if area_raw else None
    except (ValueError, TypeError):
        area = None

    # Build image URLs
    image_url = item.get("Image")
    image_urls = []
    if image_url:
        # Convert thumbnail to higher res
        if "width_" in image_url:
            high_res = image_url.replace("width_600", "width_1200")
            image_urls.append(high_res)
        image_urls.append(image_url)

    # Map property type
    raw_type = item.get("PropertyType", "")
    prop_type = TYPE_MAP.get(raw_type, "apartment")

    # Build address
    parts = [p for p in [item.get("Zone"), item.get("Town"), item.get("Province")] if p]
    address = ", ".join(parts)

    return {
        "country_code": "MT",
        "source": "mt_remax",
        "external_id": str(item.get("MLS") or item.get("Id")),
        "url": f"https://www.remax-malta.com/property-details/MLS-{item.get('MLS', '')}",
        "title": f"{raw_type} in {item.get('Town', 'Malta')}",
        "description": item.get("Description", ""),
        "address_raw": address,
        "locality": item.get("Town") or item.get("Zone"),
        "lat": coords.get("lat"),
        "lon": coords.get("lon"),
        "property_type": prop_type,
        "area_sqm": float(area) if area else None,
        "rooms": item.get("TotalRooms"),
        "bedrooms": item.get("TotalBedrooms"),
        "bathrooms": item.get("TotalBathrooms"),
        "price_eur": float(price) if price else None,
        "price_original": float(price) if price else None,
        "price_currency": "EUR",
        "price_type": "asking",
        "price_per_sqm": (
            round(float(price) / float(area), 2)
            if price and area and float(area) > 0
            else None
        ),
        "price_adjusted_eur": round(float(price) * 0.97, 2) if price else None,
        "has_garage": 1 if item.get("PropertyIncludesGarage") else 0,
        "listing_date": item.get("InsertionDate"),
        "agent_name": None,
        "image_urls": image_urls,
        "image_local_paths": [],
        "raw_json": {
            "mls": item.get("MLS"),
            "status": item.get("Status"),
            "availability": item.get("AvailabilityText"),
            "total_int_area": item.get("TotalIntArea"),
            "total_ext_area": item.get("TotalExtArea"),
            "score": item.get("Score"),
            "last_modified": item.get("LastModified"),
            "zone": item.get("Zone"),
            "province": item.get("Province"),
            "garage_type": item.get("GarageType"),
        },
    }


def main():
    conn = get_db()
    client = httpx.Client(
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
            "Referer": "https://www.remax-malta.com/property-for-sale",
        },
        timeout=30.0,
        follow_redirects=True,
    )

    run_id = start_scrape_run(conn, "mt_remax", "MT")
    total_scraped = 0
    total_new = 0
    total_errors = 0

    try:
        skip = 0
        while skip < MAX_LISTINGS:
            logger.info(f"Fetching batch: skip={skip}, take={BATCH_SIZE}")
            try:
                data = fetch_batch(client, skip)
            except Exception as e:
                logger.error(f"API request failed: {e}")
                total_errors += 1
                break

            items = data.get("Properties", data.get("Items", data.get("items", [])))
            if not items:
                logger.info("No more items, stopping")
                break

            total_available = (
                data.get("TotalSearchResults", 0)
                if isinstance(data, dict)
                else len(items)
            )
            logger.info(f"Got {len(items)} items (total available: {total_available})")

            for item in items:
                try:
                    record = process_property(item)

                    # Download images
                    if record["image_urls"]:
                        record["image_local_paths"] = download_images(
                            client,
                            record["image_urls"],
                            "mt_remax",
                            record["external_id"],
                            max_images=3,
                        )

                    prop_id, is_new = save_property(conn, record)
                    total_scraped += 1
                    if is_new:
                        total_new += 1
                        if total_new <= 20 or total_new % 50 == 0:
                            logger.info(
                                f"  NEW #{prop_id}: {record['title'][:50]} | "
                                f"{record.get('price_eur')} EUR | "
                                f"{record.get('locality')}"
                            )
                except Exception as e:
                    logger.error(f"  Failed to process item: {e}")
                    total_errors += 1

            skip += BATCH_SIZE
            time.sleep(DELAY)

    finally:
        finish_scrape_run(conn, run_id, total_scraped, total_new, total_errors)
        client.close()
        conn.close()

    logger.info(f"\nDONE: {total_scraped} total, {total_new} new, {total_errors} errors")


if __name__ == "__main__":
    main()
