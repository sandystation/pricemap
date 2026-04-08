"""
MaltaPark scraper - Malta classifieds with property listings.

Listing page: https://www.maltapark.com/listings/category/248
Detail page: https://www.maltapark.com/item/details/{id}
Server-rendered HTML, easy to parse. ~4000 property-for-sale listings.
"""

import logging
import re
import time

from bs4 import BeautifulSoup

from scraper_base import (
    get_store,
    get_client,
    download_images,
    start_scrape_run,
    finish_scrape_run,
)

logger = logging.getLogger("maltapark")

BASE = "https://www.maltapark.com"
LISTING_URL = f"{BASE}/listings/category/248"  # Property for sale
DELAY = 2.0

TYPE_MAP = {
    "apartment": "apartment",
    "apartment / flat": "apartment",
    "flat": "apartment",
    "penthouse": "penthouse",
    "maisonette": "maisonette",
    "villa": "villa",
    "detached villa": "villa",
    "semi-detached villa": "house",
    "terraced house": "house",
    "townhouse": "house",
    "house of character": "house",
    "bungalow": "house",
    "palazzo": "house",
    "palazzino": "house",
    "farmhouse": "house",
    "cottage": "house",
    "studio": "studio",
    "garage": "parking",
    "car space": "parking",
    "office": "commercial",
    "offices": "commercial",
    "shop": "commercial",
    "business outlet or shop": "commercial",
    "other commercial": "commercial",
    "industrial": "commercial",
    "warehouse": "commercial",
    "restaurant": "commercial",
    "plot": "land",
    "land": "land",
    "land (odz)": "land",
    "site": "land",
}


def parse_listing_page(html: str) -> list[dict]:
    """Extract listings from category page."""
    soup = BeautifulSoup(html, "lxml")
    listings = []

    for item in soup.select("div.item[data-itemid]"):
        item_id = item.get("data-itemid")
        if not item_id:
            continue

        header = item.select_one("a.header")
        title = header.get_text().strip() if header else ""
        link = header.get("href", "") if header else ""
        if link.startswith("/"):
            link = BASE + link

        price_el = item.select_one("span.price span")
        price = None
        if price_el:
            price_text = price_el.get_text().strip()
            price_match = re.search(r"[\d,]+", price_text.replace("EUR", "").strip())
            if price_match:
                try:
                    price = float(price_match.group().replace(",", ""))
                except ValueError:
                    pass

        details = {}
        for detail_item in item.select(".extra .details span.item"):
            icon = detail_item.select_one("i.ouricon")
            value_span = detail_item.select_one("span")
            if icon and value_span:
                classes = icon.get("class", [])
                value = value_span.get_text().strip()
                if "bed" in classes:
                    details["bedrooms"] = value
                elif "locationpin" in classes:
                    details["locality"] = value
                elif "house" in classes:
                    details["property_type"] = value

        img = item.select_one("a.imagelink img")
        thumb = img.get("src", "") if img else ""
        if thumb.startswith("/"):
            thumb = BASE + thumb

        listings.append({
            "item_id": item_id,
            "title": title,
            "url": link,
            "price": price,
            "thumb": thumb,
            **details,
        })

    return listings


def parse_detail_page(html: str) -> dict:
    """Parse a MaltaPark detail page for full property data."""
    soup = BeautifulSoup(html, "lxml")
    data = {}

    h1 = soup.select_one("h1.top-title span")
    if h1:
        data["title"] = h1.get_text().strip()

    price_h1 = soup.select_one("h1.top-price")
    if price_h1:
        price_text = price_h1.get_text().strip()
        match = re.search(r"[\d,]+", price_text)
        if match:
            try:
                data["price"] = float(match.group().replace(",", ""))
            except ValueError:
                pass

    desc = soup.select_one("div.readmore-wrapper")
    if desc:
        data["description"] = desc.get_text(separator="\n").strip()

    for item in soup.select("div.item-details span.item, div.details-list span.item"):
        label_el = item.select_one("b, label")
        value_el = item.select_one("span:not(b)")
        if not label_el:
            continue
        label = label_el.get_text().strip().lower().rstrip(":")
        value = value_el.get_text().strip() if value_el else item.get_text().replace(label_el.get_text(), "").strip()

        if "property type" in label or "type" == label:
            data["property_type_raw"] = value
        elif "locality" in label or "location" in label:
            data["locality"] = value
        elif "bedroom" in label:
            try:
                data["bedrooms"] = int(re.search(r"\d+", value).group())
            except (ValueError, AttributeError):
                pass
        elif "bathroom" in label:
            try:
                data["bathrooms"] = int(re.search(r"\d+", value).group())
            except (ValueError, AttributeError):
                pass
        elif "level of finish" in label or "finish" in label:
            data["condition_raw"] = value
        elif "garden" in label or "yard" in label:
            data["has_garden"] = 1 if value.lower() not in ("no", "none", "") else 0
        elif "pool" in label:
            data["has_pool"] = 1 if value.lower() not in ("no", "none", "") else 0
        elif "garage" in label:
            data["has_garage"] = 1 if value.lower() not in ("no", "none", "") else 0
        elif "area" in label or "size" in label or "sqm" in label:
            sqm_match = re.search(r"(\d+)", value)
            if sqm_match:
                data["area_sqm"] = float(sqm_match.group(1))

    # Try extracting area from description if not found in fields
    if not data.get("area_sqm") and data.get("description"):
        sqm_match = re.search(r"(\d+)\s*(?:sq\.?\s*m|m²|sqm)", data["description"], re.IGNORECASE)
        if sqm_match:
            data["area_sqm"] = float(sqm_match.group(1))

    image_urls = []
    for a in soup.select("a.fancybox, a[data-fancybox]"):
        href = a.get("href", "")
        if href and "/asset/" in href:
            if href.startswith("/"):
                href = BASE + href
            image_urls.append(href)
    if not image_urls:
        for img in soup.select("img[src*='/asset/itemphotos/']"):
            src = img.get("src", "")
            if src.startswith("/"):
                src = BASE + src
            image_urls.append(src)
    data["image_urls"] = list(dict.fromkeys(image_urls))

    seller = soup.select_one("div.header.username, span.username")
    if seller:
        data["agent_name"] = seller.get_text().strip()

    page_text = soup.get_text(separator="\n").lower()
    data["has_parking"] = 1 if "parking" in page_text or "garage" in page_text else 0
    data["has_pool"] = data.get("has_pool", 1 if "pool" in page_text else 0)
    data["has_garden"] = data.get("has_garden", 1 if "garden" in page_text else 0)
    data["has_elevator"] = 1 if "lift" in page_text or "elevator" in page_text else 0
    data["has_balcony"] = 1 if "balcony" in page_text or "terrace" in page_text else 0

    return data


def map_condition(raw: str) -> str | None:
    if not raw:
        return None
    raw_lower = raw.lower()
    if "shell" in raw_lower:
        return "shell"
    elif "new" in raw_lower or "plan" in raw_lower:
        return "new"
    elif "excellent" in raw_lower or "finish" in raw_lower:
        return "excellent"
    elif "furnished" in raw_lower:
        return "good"
    elif "good" in raw_lower:
        return "good"
    elif "renovat" in raw_lower:
        return "needs_renovation"
    elif "site" in raw_lower or "land" in raw_lower:
        return None  # not applicable for land
    return None


def main():
    store = get_store()
    coll = store.collection("mt_maltapark")
    client = get_client()
    run_id = start_scrape_run(store, "mt_maltapark", "MT")

    total_scraped = 0
    total_new = 0
    total_errors = 0

    try:
        page = 1
        while True:
            url = f"{LISTING_URL}?page={page}"
            logger.info(f"Fetching listing page {page}: {url}")

            try:
                resp = client.get(url)
                if resp.status_code != 200:
                    logger.warning(f"Got {resp.status_code}")
                    total_errors += 1
                    break
            except Exception as e:
                logger.error(f"Failed: {e}")
                total_errors += 1
                break

            listings = parse_listing_page(resp.text)
            if not listings:
                logger.info("No listings found, stopping")
                break

            logger.info(f"Found {len(listings)} listings on page {page}")
            time.sleep(DELAY)

            for listing in listings:
                item_id = listing["item_id"]
                doc_id = f"mt_maltapark:{item_id}"

                # Staleness check: skip if seen within 20 hours
                if not coll.is_stale(doc_id, hours=20):
                    total_scraped += 1
                    continue

                detail_url = listing.get("url") or f"{BASE}/item/details/{item_id}"
                logger.info(f"  Scraping detail: {detail_url}")

                try:
                    resp = client.get(detail_url)
                    if resp.status_code != 200:
                        logger.warning(f"  Got {resp.status_code}")
                        total_errors += 1
                        time.sleep(DELAY)
                        continue
                except Exception as e:
                    logger.error(f"  Failed: {e}")
                    total_errors += 1
                    time.sleep(DELAY)
                    continue

                detail = parse_detail_page(resp.text)

                price = detail.get("price") or listing.get("price")

                # Detect wanted ads
                title_text = (detail.get("title") or listing.get("title", "")).lower()
                is_wanted = any(kw in title_text for kw in
                    ["wanted", "looking for", "looking to buy", "searching for", "required"])

                locality = detail.get("locality") or listing.get("locality")
                raw_type = detail.get("property_type_raw") or listing.get("property_type", "")
                prop_type = TYPE_MAP.get(raw_type.lower(), "other")
                if prop_type == "other":
                    logger.warning(f"Unknown property type: {raw_type!r}")
                bedrooms = detail.get("bedrooms")
                if not bedrooms and listing.get("bedrooms"):
                    try:
                        bedrooms = int(listing["bedrooms"])
                    except (ValueError, TypeError):
                        pass
                area = detail.get("area_sqm")

                record = {
                    "country_code": "MT",
                    "source": "mt_maltapark",
                    "external_id": item_id,
                    "url": detail_url,
                    "title": detail.get("title") or listing.get("title", ""),
                    "description": detail.get("description", ""),
                    "address_raw": locality or "",
                    "locality": locality,
                    "property_type": prop_type,
                    "listing_type": "sale",
                    "area_sqm": area,
                    "bedrooms": bedrooms,
                    "bathrooms": detail.get("bathrooms"),
                    "condition": map_condition(detail.get("condition_raw")),
                    "price_eur": price,
                    "price_original": price,
                    "price_currency": "EUR",
                    "price_type": "asking",
                    "price_per_sqm": (
                        round(price / area, 2) if price and area and area > 0 else None
                    ),
                    "price_adjusted_eur": round(price * 0.97, 2) if price else None,
                    "has_parking": detail.get("has_parking", 0),
                    "has_pool": detail.get("has_pool", 0),
                    "has_garden": detail.get("has_garden", 0),
                    "has_elevator": detail.get("has_elevator", 0),
                    "has_balcony": detail.get("has_balcony", 0),
                    "agent_name": detail.get("agent_name"),
                    "image_urls": detail.get("image_urls", []),
                    "image_local_paths": [],
                    "property_type_raw": raw_type,
                    "condition_raw": detail.get("condition_raw"),
                    "is_wanted": 1 if is_wanted else 0,
                    "raw_data": {"listing": listing, "detail": detail},
                }

                if record["image_urls"]:
                    record["image_local_paths"] = download_images(
                        client, record["image_urls"], "mt_maltapark", item_id
                    )

                doc_id, is_new = coll.save_property(record)
                total_scraped += 1
                if is_new:
                    total_new += 1
                    if total_new <= 20 or total_new % 50 == 0:
                        logger.info(
                            f"  NEW {doc_id}: {record['title'][:50]} | "
                            f"{price} EUR | {locality}"
                        )

                time.sleep(DELAY)

            page += 1

    finally:
        finish_scrape_run(store, run_id, total_scraped, total_new, total_errors)
        coll.close()
        client.close()
        store.close()

    logger.info(f"\nDONE: {total_scraped} total, {total_new} new, {total_errors} errors")


if __name__ == "__main__":
    main()
