"""
RE/MAX Malta scraper - JSON API, 32K+ listings with GPS coordinates.

Endpoint: https://remax-malta.com/api/properties
Pagination: Take=100&Skip=N
No auth required. Returns structured JSON with all fields.
"""

import logging
import time

import httpx

from scraper_base import (
    get_store,
    download_images,
    start_scrape_run,
    finish_scrape_run,
)

logger = logging.getLogger("remax_mt")

API_BASE = "https://remax-malta.com/api/properties"
BATCH_SIZE = 100
DELAY = 2.0

TYPE_MAP = {
    # Apartments
    "Apartment": "apartment",
    "Apartment Duplex": "apartment",
    "Block Of Apartments": "apartment",
    "FlatLet": "apartment",
    "Serviced Apartment": "apartment",
    # Penthouses
    "Penthouse": "penthouse",
    "Penthouse Duplex": "penthouse",
    "Penthouse Triplex": "penthouse",
    "Sky Villa": "penthouse",
    # Maisonettes
    "Maisonette": "maisonette",
    "Maisonette Duplex": "maisonette",
    "Maisonette Semi-detached": "maisonette",
    "Maisonette Solitary": "maisonette",
    "Maisonette Solitary Duplex": "maisonette",
    "Maisonette Solitary Triplex": "maisonette",
    # Villas
    "Villa": "villa",
    "Villa Semi-detached": "villa",
    "Villa Detached": "villa",
    # Houses
    "Terraced House": "house",
    "Semi-Detached Villa": "house",
    "Townhouse": "house",
    "House of Character": "house",
    "Bungalow": "house",
    "Bungalow Detached": "house",
    "Bungalow Semi-detached": "house",
    "Palazzo": "house",
    "Palazzino": "house",
    "Farmhouse": "house",
    "Cottage": "house",
    "Guest House": "house",
    # Studios
    "Studio": "studio",
    "Studio Flat": "studio",
    "Room": "studio",
    # Parking / garages
    "Garage": "parking",
    "Garage (Residential)": "parking",
    "Garage (Commercial)": "parking",
    "Car Space": "parking",
    "Boathouse": "parking",
    "Parking Lot": "parking",
    # Commercial
    "Office": "commercial",
    "Office Space": "commercial",
    "Office Block": "commercial",
    "Managed Office": "commercial",
    "Shop": "commercial",
    "Showroom": "commercial",
    "Shopping Mall": "commercial",
    "Outlet Mall": "commercial",
    "Restaurant": "commercial",
    "Cafe": "commercial",
    "Bar": "commercial",
    "Pub": "commercial",
    "Take Away": "commercial",
    "Warehouse": "commercial",
    "Warehouse with Office Space": "commercial",
    "Factory": "commercial",
    "Industrial Estate Building": "commercial",
    "Self Storage": "commercial",
    "Salon/Hairdresser/Beautician": "commercial",
    "Sale of Business": "commercial",
    "Gymnasium": "commercial",
    "Fitness Centre": "commercial",
    "Rehabilitation Clinic": "commercial",
    "Pharmacy": "commercial",
    "School": "commercial",
    "Hotel": "commercial",
    "Boutique Hotel": "commercial",
    "Hostel": "commercial",
    "B&B": "commercial",
    "Old people's/Nursing Home": "commercial",
    "Gambling/Entertainment": "commercial",
    "Hall": "commercial",
    "Stables": "commercial",
    "Building": "commercial",
    # Land
    "Plot": "land",
    "Land": "land",
    "Land for Development": "land",
    "Agriculture Land": "land",
    "Site": "land",
    "Site / Plot": "land",
    "Airspace (Residential)": "land",
    "Yard": "land",
}


def fetch_batch(client: httpx.Client, skip: int) -> dict:
    """Fetch a batch of properties from the API."""
    params = {
        "Take": BATCH_SIZE,
        "Skip": skip,
        "TransactionTypeId": 0,  # API ignores this; returns all types
    }
    resp = client.get(API_BASE, params=params)
    resp.raise_for_status()
    wrapper = resp.json()
    inner = wrapper.get("data", wrapper)
    return inner


def process_property(item: dict, raw_item: dict) -> dict:
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

    image_url = item.get("Image")
    image_urls = []
    if image_url:
        if "width_" in image_url:
            high_res = image_url.replace("width_600", "width_1200")
            image_urls.append(high_res)
        image_urls.append(image_url)

    raw_type = item.get("PropertyType", "")
    prop_type = TYPE_MAP.get(raw_type)
    if prop_type is None:
        logger.warning(f"Unknown property type: {raw_type!r}")
        prop_type = "other"

    tx_type = item.get("TransactionType", "")
    if "rent" in tx_type.lower() or "short" in tx_type.lower():
        listing_type = "rent"
    else:
        listing_type = "sale"

    parts = [p for p in [item.get("Zone"), item.get("Town"), item.get("Province")] if p]
    address = ", ".join(parts)

    mls = item.get("MLS", "")

    return {
        "country_code": "MT",
        "source": "mt_remax",
        "external_id": str(mls or item.get("Id")),
        "url": f"https://remax-malta.com/listings/{mls}",
        "title": f"{raw_type} in {item.get('Town', 'Malta')}",
        "description": item.get("Description", ""),
        "address_raw": address,
        "locality": item.get("Town") or item.get("Zone"),
        "lat": coords.get("lat"),
        "lon": coords.get("lon"),
        "property_type": prop_type,
        "listing_type": listing_type,
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
        "image_urls": image_urls,
        "image_local_paths": [],
        "raw_type": raw_type,
        "status": item.get("Status"),
        "availability": item.get("AvailabilityText"),
        "total_int_area": item.get("TotalIntArea"),
        "total_ext_area": item.get("TotalExtArea"),
        "zone": item.get("Zone"),
        "province": item.get("Province"),
        "last_modified": item.get("LastModified"),
        "raw_data": raw_item,
    }


def main():
    store = get_store()
    coll = store.collection("mt_remax")
    client = httpx.Client(
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
            "Referer": "https://remax-malta.com/property-for-sale",
        },
        timeout=30.0,
        follow_redirects=True,
    )

    run_id = start_scrape_run(store, "mt_remax", "MT")
    total_scraped = 0
    total_new = 0
    total_errors = 0
    total_available = None

    try:
        skip = 0
        while True:
            logger.info(f"Fetching batch: skip={skip}, take={BATCH_SIZE}")
            try:
                data = fetch_batch(client, skip)
            except Exception as e:
                logger.error(f"API request failed: {e}")
                total_errors += 1
                break

            items = data.get("Properties", [])
            if not items:
                logger.info("No more items, stopping")
                break

            if total_available is None:
                total_available = data.get("TotalSearchResults", 0)
                logger.info(f"Total available from API: {total_available}")

            logger.info(f"Got {len(items)} items (skip={skip}/{total_available})")

            for item in items:
                try:
                    record = process_property(item, raw_item=item)

                    if record["image_urls"]:
                        record["image_local_paths"] = download_images(
                            client,
                            record["image_urls"],
                            "mt_remax",
                            record["external_id"],
                            max_images=2,
                        )

                    doc_id, is_new = coll.save_property(record)
                    total_scraped += 1
                    if is_new:
                        total_new += 1
                        if total_new <= 20 or total_new % 100 == 0:
                            logger.info(
                                f"  NEW {doc_id}: {record['title'][:50]} | "
                                f"{record.get('price_eur')} EUR | "
                                f"{record.get('locality')}"
                            )
                except Exception as e:
                    logger.error(f"  Failed to process item: {e}")
                    total_errors += 1

            skip += BATCH_SIZE
            if total_available and skip >= total_available:
                logger.info(f"Reached end: {skip} >= {total_available}")
                break
            time.sleep(DELAY)

    finally:
        finish_scrape_run(store, run_id, total_scraped, total_new, total_errors)
        coll.close()
        client.close()
        store.close()

    logger.info(f"\nDONE: {total_scraped} total, {total_new} new, {total_errors} errors")


if __name__ == "__main__":
    main()
