"""
Imot.bg scraper - Bulgaria's largest real estate portal.

Strategy:
1. Crawl search results pages at /obiavi/prodazhbi/grad-{city}/p-{N}
2. Extract listing URLs from search results
3. Visit each detail page and parse JSON-LD + HTML for full data
4. Download images, store everything in SQLite

Key details:
- Encoding: windows-1251
- JSON-LD on detail pages has price, currency, images, SKU
- 40 listings per results page
- Clean URL pagination: /p-{N}
"""

import json
import logging
import re
import time

from bs4 import BeautifulSoup

from scraper_base import (
    BGN_EUR_RATE,
    get_client,
    get_store,
    download_images,
    start_scrape_run,
    finish_scrape_run,
)

logger = logging.getLogger("imot_bg")

# Cities to scrape with their URL slugs
CITIES = [
    # Major cities
    ("grad-sofiya", "Sofia"),
    ("grad-plovdiv", "Plovdiv"),
    ("grad-varna", "Varna"),
    ("grad-burgas", "Burgas"),
    ("grad-ruse", "Ruse"),
    ("grad-stara-zagora", "Stara Zagora"),
    # Medium cities
    ("grad-pleven", "Pleven"),
    ("grad-sliven", "Sliven"),
    ("grad-dobrich", "Dobrich"),
    ("grad-shumen", "Shumen"),
    ("grad-blagoevgrad", "Blagoevgrad"),
    ("grad-veliko-tarnovo", "Veliko Tarnovo"),
    ("grad-vratsa", "Vratsa"),
    ("grad-gabrovo", "Gabrovo"),
    ("grad-haskovo", "Haskovo"),
    ("grad-kardzhali", "Kardzhali"),
    ("grad-kyustendil", "Kyustendil"),
    ("grad-lovech", "Lovech"),
    ("grad-montana", "Montana"),
    ("grad-pazardzhik", "Pazardzhik"),
    ("grad-pernik", "Pernik"),
    ("grad-razgrad", "Razgrad"),
    ("grad-silistra", "Silistra"),
    ("grad-smolyan", "Smolyan"),
    ("grad-targovishte", "Targovishte"),
    ("grad-vidin", "Vidin"),
    ("grad-yambol", "Yambol"),
    # Resort / tourist towns
    ("grad-bansko", "Bansko"),
    ("grad-sandanski", "Sandanski"),
    ("grad-pomorie", "Pomorie"),
    ("grad-nesebar", "Nesebar"),
    ("grad-sozopol", "Sozopol"),
    ("grad-sveti-vlas", "Sveti Vlas"),
    ("KK-slanchev-bryag", "Sunny Beach"),
    ("KK-zlatni-pyasatsi", "Golden Sands"),
]

# Property type mapping (Bulgarian -> our types)
TYPE_MAP = {
    "1-стаен": "studio",
    "едностаен": "studio",
    "2-стаен": "apartment",
    "двустаен": "apartment",
    "3-стаен": "apartment",
    "тристаен": "apartment",
    "4-стаен": "apartment",
    "четиристаен": "apartment",
    "многостаен": "apartment",
    "мезонет": "maisonette",
    "ателие": "studio",
    "къща": "house",
    "вила": "villa",
    "етаж от къща": "house",
    "пентхаус": "penthouse",
    "гараж": "parking",
    "паркомясто": "parking",
    "офис": "commercial",
    "магазин": "commercial",
    "склад": "commercial",
    "бизнес имот": "commercial",
    "пром. помещение": "commercial",
    "заведение": "commercial",
    "хотел": "commercial",
    "парцел": "land",
    "земя": "land",
}

BASE = "https://www.imot.bg"
MAX_PAGES_PER_CITY = 50  # Safety cap per city
DELAY = 2.0  # Seconds between requests


def parse_search_page(html: str) -> list[dict]:
    """Extract listing URLs and basic info from a search results page."""
    soup = BeautifulSoup(html, "lxml")
    listings = []

    for item in soup.select("div.item"):
        link = item.select_one("a.title.saveSlink, a.saveSlink[href*='obiava']")
        if not link:
            continue

        href = link.get("href", "")
        if "obiava" not in href:
            continue
        if href.startswith("//"):
            href = "https:" + href

        # Extract price from search results
        price_div = item.select_one("div.price div")
        price_eur = None
        price_bgn = None
        if price_div:
            price_text = price_div.get_text(separator="\n").strip()
            # "119 000 €\n232 743.77 лв." or "15 338.76 €\n30 000 лв."
            eur_match = re.search(r"([\d\s]+(?:[.,]\d+)?)\s*€", price_text)
            bgn_match = re.search(r"([\d\s]+(?:[.,]\d+)?)\s*лв", price_text)
            if eur_match:
                price_eur = float(eur_match.group(1).replace(" ", "").replace(",", "."))
            if bgn_match:
                price_bgn = float(bgn_match.group(1).replace(" ", "").replace(",", "."))

        # Extract info line
        info_div = item.select_one("div.info")
        info_text = info_div.get_text(separator=", ").strip() if info_div else ""

        # Main photo
        img = item.select_one("div.big img.pic")
        thumb_url = None
        if img:
            thumb_url = img.get("src", "")
            if thumb_url.startswith("//"):
                thumb_url = "https:" + thumb_url

        # Listing ID from element id
        item_id = item.get("id", "")
        ext_id = item_id.replace("ida", "") if item_id.startswith("ida") else None

        listings.append({
            "url": href,
            "external_id": ext_id,
            "price_eur": price_eur,
            "price_bgn": price_bgn,
            "info_text": info_text,
            "thumb_url": thumb_url,
        })

    return listings


def parse_detail_page(html: str, url: str) -> dict:
    """Parse a property detail page. Uses JSON-LD + HTML parsing."""
    soup = BeautifulSoup(html, "lxml")
    data = {}

    # 1. Parse JSON-LD
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            ld = json.loads(script.string)
            if ld.get("@type") == "Offer":
                data["price_original"] = ld.get("price")
                data["price_currency"] = ld.get("priceCurrency", "EUR")
                item = ld.get("itemOffered", {})
                # JSON-LD "name" is unreliable (says "for rent" on sale pages)
                data["description_short"] = item.get("description", "")
                data["image_urls"] = item.get("image", [])
                if isinstance(data["image_urls"], str):
                    data["image_urls"] = [data["image_urls"]]
                data["external_id"] = item.get("sku", "")
                seller = ld.get("seller", {})
                data["agent_name"] = seller.get("name", "")
                data["agent_url"] = seller.get("url", "")

            elif ld.get("@type") == "BreadcrumbList":
                items = ld.get("itemListElement", [])
                if len(items) >= 2:
                    # "Продажби" or "Наеми" — detect listing type
                    section = items[1].get("name", "").lower()
                    if "продаж" in section:
                        data["listing_type"] = "sale"
                    elif "наем" in section:
                        data["listing_type"] = "rent"
                if len(items) >= 3:
                    data["city_name"] = items[2].get("name", "")
                if len(items) >= 4:
                    data["quarter_name"] = items[3].get("name", "")
        except (json.JSONDecodeError, TypeError):
            continue

    # Title from H1 (reliable) instead of JSON-LD name
    h1 = soup.select_one("h1")
    if h1:
        # H1 has multiple lines; take the first line as the core title
        h1_text = h1.get_text(separator=" ").strip()
        # Clean up extra whitespace
        data["title"] = " ".join(h1_text.split())

    # 2. Parse HTML for additional fields

    # Price (may have EUR and BGN)
    price_el = soup.select_one("div.adPrice .price .cena, div.cena")
    if price_el:
        price_text = price_el.get_text(separator="\n")
        eur_match = re.search(r"([\d\s]+(?:[.,]\d+)?)\s*€", price_text)
        if eur_match:
            data["price_eur"] = float(eur_match.group(1).replace(" ", "").replace(",", "."))
        # Price per sqm
        per_sqm = soup.select_one("div.adPrice .price span")
        if per_sqm:
            sqm_match = re.search(r"([\d\s,.]+)\s*€/m", per_sqm.get_text())
            if sqm_match:
                data["price_per_sqm"] = float(
                    sqm_match.group(1).replace(" ", "").replace(",", ".")
                )

    # VAT status
    price_section = soup.select_one("div.adPrice")
    if price_section:
        price_text_full = price_section.get_text()
        if "без ДДС" in price_text_full:
            data["vat_status"] = "excluded"
        elif "с включено ДДС" in price_text_full:
            data["vat_status"] = "included"
        else:
            data["vat_status"] = "unknown"

    # Publication date and view count
    info_el = soup.select_one("div.adPrice .info")
    if info_el:
        info_text = info_el.get_text()
        date_match = re.search(
            r"(\d{1,2})\s+(\w+),?\s+(\d{4})", info_text
        )
        if date_match:
            data["listing_date_raw"] = date_match.group(0)
        views = re.search(r"посетена\s+(\d+)", info_text)
        if views:
            data["view_count"] = int(views.group(1))

    # Property parameters (area, floor, construction, utilities)
    params = soup.select("div.adParams div")
    for param in params:
        text = param.get_text(separator=" ").strip()
        # Area (only "Площ:", not "Двор:"); format is "Площ: 60 m 2"
        if "Площ" in text:
            area_match = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:m\s*2|m²|кв\.?\s*м)", text)
            if area_match:
                data["area_sqm"] = float(area_match.group(1).replace(",", "."))
        # Floor: ordinal format "8-ми от 8", "2-ри от 7", "Партер от 1"
        if "Етаж" in text or "Партер" in text:
            fl = re.search(r"(\d+)\s*[-–]?\s*(?:ти|ри|ви|ми|ет)", text)
            if fl:
                data["floor"] = int(fl.group(1))
            elif "Партер" in text:
                data["floor"] = 0
            total_match = re.search(r"от\s*(\d+)", text)
            if total_match:
                data["total_floors"] = int(total_match.group(1))
        # Construction type + year built + completion status
        if "Строителство" in text:
            if "Тух" in text or "тухл" in text.lower():
                data["construction_type"] = "brick"
            elif "Панел" in text or "панел" in text.lower():
                data["construction_type"] = "panel"
            elif "ЕПК" in text:
                data["construction_type"] = "epk"
            yr = re.search(r"(\d{4})\s*(?:[-–]\s*(\d{4}))?\s*г\.", text)
            if yr:
                data["year_built"] = int(yr.group(2) or yr.group(1))
            if "Ще бъде въведен" in text:
                data["completion_status"] = "planned"
            elif "Въведен в експлоатация" in text:
                data["completion_status"] = "completed"
        # Gas and central heating
        if "Газ:" in text:
            data["has_gas"] = 1 if "ДА" in text else 0
        if "ТEЦ:" in text or "ТЕЦ:" in text:
            data["has_central_heating"] = 1 if "ДА" in text else 0

    # Full description
    desc_el = soup.select_one("div.moreInfo .text, div.moreInfo")
    if desc_el:
        data["description"] = desc_el.get_text(separator="\n").strip()

    # Amenities
    amenity_items = soup.select("div.carExtri .items div, div.carExtri div")
    amenities = [a.get_text().strip() for a in amenity_items if a.get_text().strip()]
    if amenities:
        data["amenities_raw"] = amenities
        amenities_lower = " ".join(amenities).lower()
        data["has_furnishing"] = 1 if "мебел" in amenities_lower else 0
        data["has_parking"] = 1 if "паркомясто" in amenities_lower or "паркинг" in amenities_lower else 0
        data["has_garage"] = 1 if "гараж" in amenities_lower else 0
        data["has_elevator"] = 1 if "асансьор" in amenities_lower else 0
        data["has_balcony"] = 1 if "балкон" in amenities_lower or "тераса" in amenities_lower else 0
        data["has_garden"] = 1 if "градин" in amenities_lower or "двор" in amenities_lower else 0
        data["has_ac"] = 1 if "климатик" in amenities_lower else 0
        data["has_access_control"] = 1 if "контрол на достъпа" in amenities_lower else 0
        data["has_cctv"] = 1 if "видео наблюдение" in amenities_lower or "видеонаблюдение" in amenities_lower else 0
        data["is_insulated"] = 1 if "саниран" in amenities_lower else 0
        data["has_internet"] = 1 if "интернет" in amenities_lower else 0

    # Phone
    phone_el = soup.select_one("div.phone, div.dealer2023 .phone")
    if phone_el:
        data["agent_phone"] = phone_el.get_text().strip()

    # Agent company name from dealer section
    dealer_name = soup.select_one("div.dealer2023 .infoBox .name, div.dealer .info .name")
    if dealer_name:
        data["agent_company"] = dealer_name.get_text().strip()

    # Images from carousel (full size)
    carousel_imgs = soup.select(".owl-carousel img.carouselimg, img[data-src*='cdn3.focus.bg']")
    if carousel_imgs and not data.get("image_urls"):
        data["image_urls"] = []
    for img in carousel_imgs:
        src = img.get("data-src") or img.get("src", "")
        if src and "cdn3.focus.bg" in src:
            if src.startswith("//"):
                src = "https:" + src
            if src not in data.get("image_urls", []):
                data.setdefault("image_urls", []).append(src)

    return data


def detect_property_type(title: str) -> str:
    """Detect property type from Bulgarian title."""
    title_lower = title.lower()
    for bg_type, our_type in TYPE_MAP.items():
        if bg_type in title_lower:
            return our_type
    logger.warning(f"Unknown property type in title: {title[:60]!r}")
    return "other"


def detect_rooms(title: str) -> int | None:
    """Extract room count from title like '2-СТАЕН' or 'Двустаен'."""
    match = re.search(r"(\d)-стаен", title, re.IGNORECASE)
    if match:
        return int(match.group(1))
    words = {"едностаен": 1, "двустаен": 2, "тристаен": 3, "четиристаен": 4, "многостаен": 5}
    title_lower = title.lower()
    for word, count in words.items():
        if word in title_lower:
            return count
    return None


LISTING_TYPE_SLUGS = {
    "sale": "prodazhbi",
    "rent": "naemi",
}


def scrape_city(client, coll, city_slug: str, city_name: str, listing_type: str = "sale"):
    """Scrape listings for a single city."""
    type_slug = LISTING_TYPE_SLUGS[listing_type]
    items_scraped = 0
    items_new = 0
    errors = 0

    page = 1
    while page <= MAX_PAGES_PER_CITY:
        if page == 1:
            url = f"{BASE}/obiavi/{type_slug}/{city_slug}"
        else:
            url = f"{BASE}/obiavi/{type_slug}/{city_slug}/p-{page}"

        logger.info(f"Fetching search page: {url}")
        try:
            resp = client.get(url)
            resp.encoding = "windows-1251"
            if resp.status_code != 200:
                logger.warning(f"Got {resp.status_code} for {url}")
                errors += 1
                break
        except Exception as e:
            logger.error(f"Failed to fetch {url}: {e}")
            errors += 1
            break

        listings = parse_search_page(resp.text)
        if not listings:
            logger.info(f"No listings on page {page}, stopping")
            break

        logger.info(f"Found {len(listings)} listings on page {page}")
        time.sleep(DELAY)

        for listing in listings:
            detail_url = listing["url"]
            ext_id = listing.get("external_id") or detail_url.split("obiava-")[-1].split("-")[0]
            doc_id = f"bg_imot:{ext_id}"

            # Staleness check: skip if seen within 20 hours
            if not coll.is_stale(doc_id, hours=20):
                items_scraped += 1
                continue

            logger.info(f"  Scraping detail: {detail_url}")
            try:
                resp = client.get(detail_url)
                resp.encoding = "windows-1251"
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

            # Merge search page data
            if listing.get("price_eur") and not detail.get("price_eur"):
                detail["price_eur"] = listing["price_eur"]

            # Also try extracting area from search info text
            if not detail.get("area_sqm") and listing.get("info_text"):
                area_match = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:кв\.?\s*м|m\s*2|m²)", listing["info_text"])
                if area_match:
                    detail["area_sqm"] = float(area_match.group(1).replace(",", "."))

            # Compute EUR price
            price_eur = detail.get("price_eur")
            if not price_eur and detail.get("price_original"):
                try:
                    orig = float(detail["price_original"])
                    if detail.get("price_currency") == "EUR":
                        price_eur = orig
                    elif detail.get("price_currency") == "BGN":
                        price_eur = orig * BGN_EUR_RATE
                except (ValueError, TypeError):
                    price_eur = None
            if price_eur is not None:
                try:
                    price_eur = float(price_eur)
                except (ValueError, TypeError):
                    price_eur = None

            # Extract floor/heating from JSON-LD description_short
            # e.g. "65 кв.м, Партер от 5, Лок.отопл., Тухла"
            desc_short = detail.get("description_short", "")
            if desc_short and not detail.get("floor"):
                floor_match = re.search(r"(\d+)\s*[-–]?\s*(?:ти|ри|ви|ми|ет)\s*(?:ет\.?)?\s*от\s*(\d+)", desc_short)
                if floor_match:
                    detail["floor"] = int(floor_match.group(1))
                    detail["total_floors"] = int(floor_match.group(2))
                elif "Партер" in desc_short or "партер" in desc_short:
                    detail["floor"] = 0
                    of_match = re.search(r"от\s*(\d+)", desc_short)
                    if of_match:
                        detail["total_floors"] = int(of_match.group(1))

            if desc_short and not detail.get("heating_type"):
                heating_map = {
                    "ТЕЦ": "central", "Газ": "gas", "Ток": "electric",
                    "Лок.отопл": "local", "Печка": "stove",
                }
                for bg, en in heating_map.items():
                    if bg in desc_short:
                        detail["heating_type"] = en
                        break

            # Use listing_type from breadcrumb, or fall back to what we're scraping
            listing_type = detail.get("listing_type", listing_type)

            # Build property record
            title = detail.get("title", "")
            prop_type = detect_property_type(title)
            rooms = detect_rooms(title)
            locality = detail.get("quarter_name") or detail.get("city_name") or city_name

            address_parts = [p for p in [detail.get("quarter_name"), city_name] if p]
            address = ", ".join(address_parts)

            image_urls = detail.get("image_urls", [])
            local_paths = []
            if image_urls:
                local_paths = download_images(client, image_urls, "bg_imot", ext_id)

            record = {
                "country_code": "BG",
                "source": "bg_imot",
                "external_id": ext_id,
                "url": detail_url,
                "title": title,
                "description": detail.get("description", ""),
                "address_raw": address,
                "locality": locality,
                "city": city_name,
                "property_type": prop_type,
                "listing_type": listing_type,
                "area_sqm": detail.get("area_sqm"),
                "floor": detail.get("floor"),
                "total_floors": detail.get("total_floors"),
                "rooms": rooms,
                "construction_type": detail.get("construction_type"),
                "heating_type": detail.get("heating_type"),
                "price_eur": price_eur,
                "price_original": detail.get("price_original"),
                "price_currency": detail.get("price_currency", "EUR"),
                "price_type": "asking",
                "price_per_sqm": detail.get("price_per_sqm") or (
                    round(price_eur / detail["area_sqm"], 2)
                    if price_eur and detail.get("area_sqm") and detail["area_sqm"] > 0
                    else None
                ),
                "price_adjusted_eur": round(price_eur * 0.93, 2) if price_eur else None,
                "has_furnishing": detail.get("has_furnishing"),
                "has_parking": detail.get("has_parking"),
                "has_garage": detail.get("has_garage"),
                "has_elevator": detail.get("has_elevator"),
                "has_balcony": detail.get("has_balcony"),
                "has_garden": detail.get("has_garden"),
                "agent_name": detail.get("agent_name"),
                "agent_company": detail.get("agent_company"),
                "agent_phone": detail.get("agent_phone"),
                "agent_url": detail.get("agent_url"),
                "image_urls": image_urls,
                "image_local_paths": local_paths,
                "listing_date": detail.get("listing_date_raw"),
                "search_info": listing.get("info_text"),
                "amenities": detail.get("amenities_raw"),
                "description_short": detail.get("description_short"),
                "raw_data": {"listing": listing, "detail": detail},
            }

            doc_id, is_new = coll.save_property(record)
            items_scraped += 1
            if is_new:
                items_new += 1
                logger.info(f"  NEW {doc_id}: {title[:60]} | {price_eur} EUR")

            time.sleep(DELAY)

        page += 1

    return items_scraped, items_new, errors


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Scrape imot.bg listings")
    parser.add_argument(
        "--listing-type", default="sale", choices=["sale", "rent"],
        help="Listing type to scrape (default: sale)",
    )
    args = parser.parse_args()

    store = get_store()
    coll = store.collection("bg_imot")
    client = get_client()
    run_id = start_scrape_run(store, "bg_imot", "BG")

    total_scraped = 0
    total_new = 0
    total_errors = 0

    try:
        for city_slug, city_name in CITIES:
            logger.info(f"\n{'='*60}")
            logger.info(f"Scraping {city_name} ({city_slug}) [{args.listing_type}]")
            logger.info(f"{'='*60}")
            scraped, new, errors = scrape_city(
                client, coll, city_slug, city_name, listing_type=args.listing_type,
            )
            total_scraped += scraped
            total_new += new
            total_errors += errors
            logger.info(f"{city_name}: {scraped} scraped, {new} new, {errors} errors")
    finally:
        finish_scrape_run(store, run_id, total_scraped, total_new, total_errors)
        coll.close()
        client.close()
        store.close()

    logger.info(f"\nDONE: {total_scraped} total, {total_new} new, {total_errors} errors")


if __name__ == "__main__":
    main()
