"""
Imot.bg spider.

Scrapes property listings from Bulgaria's largest real estate portal.
Listings are in Bulgarian (Cyrillic); prices may be in BGN or EUR.
"""

from src.spiders.base import BasePropertySpider


class BulgariaImotSpider(BasePropertySpider):
    name = "bg_imot"
    country_code = "BG"
    source = "bg_imot"
    allowed_domains = ["imot.bg"]
    start_urls = ["https://www.imot.bg/pcgi/imot.cgi?act=3&session_id=&f1=1&f2=1&f3=1&f4="]

    custom_settings = {
        "DOWNLOAD_DELAY": 2.5,  # Respectful crawling
        "DEFAULT_REQUEST_HEADERS": {
            "Accept-Language": "bg,en;q=0.9",
        },
    }

    # Bulgarian property types -> our types
    TYPE_MAP = {
        "1-стаен": "studio",
        "2-стаен": "apartment",
        "3-стаен": "apartment",
        "4-стаен": "apartment",
        "многостаен": "apartment",
        "мезонет": "maisonette",
        "ателие": "studio",
        "къща": "house",
        "вила": "villa",
        "етаж от къща": "house",
    }

    def parse(self, response):
        """Parse search results page."""
        # Extract listing links
        listings = response.css("a.lnk1::attr(href), a.lnk2::attr(href)").getall()
        for url in listings:
            if url and "adv" in url:
                yield response.follow(url, callback=self.parse_listing)

        # Follow pagination
        next_page = response.css("a.pageNumbers::attr(href)").getall()
        for page_url in next_page:
            yield response.follow(page_url, callback=self.parse)

    def parse_listing(self, response):
        """Parse a single Imot.bg listing."""
        # TODO: Adapt selectors after inspecting actual page structure
        title = response.css("h1::text").get("").strip()
        price_text = response.css("#cena::text, [class*='price']::text").get("")
        location = response.css("[class*='location']::text").get("")

        # Detect currency
        currency = "BGN"
        if "EUR" in price_text or "eur" in price_text.lower():
            currency = "EUR"

        price = self.parse_price(price_text)
        if not price:
            return

        # Extract area from details
        details = response.css("div.adParams::text, div.adParams *::text").getall()
        area = None
        for detail in details:
            area = self.parse_area(detail)
            if area:
                break

        # Detect property type
        prop_type = "apartment"
        for bg_type, mapped_type in self.TYPE_MAP.items():
            if bg_type in title:
                prop_type = mapped_type
                break

        # Extract room count from type description
        rooms = None
        import re

        rooms_match = re.search(r"(\d)-стаен", title)
        if rooms_match:
            rooms = int(rooms_match.group(1))

        yield self.make_item(
            external_id=response.url.split("=")[-1] if "=" in response.url else None,
            address_raw=location,
            property_type=prop_type,
            area_sqm=area,
            rooms=rooms,
            price=price,
            price_currency=currency,
            price_type="asking",
            url=response.url,
            raw_description=title,
        )
