"""
PropertyMarket.com.mt spider.

Scrapes property listings (asking prices) from Malta's largest listing portal.
"""

from src.spiders.base import BasePropertySpider


class MaltaPropertyMarketSpider(BasePropertySpider):
    name = "mt_propertymarket"
    country_code = "MT"
    source = "mt_propertymarket"
    allowed_domains = ["propertymarket.com.mt"]
    start_urls = ["https://www.propertymarket.com.mt/for-sale/"]

    custom_settings = {
        "DOWNLOAD_DELAY": 2.0,
    }

    # Property type URL segments -> our types
    TYPE_MAP = {
        "apartment": "apartment",
        "flat": "apartment",
        "penthouse": "penthouse",
        "maisonette": "maisonette",
        "house": "house",
        "villa": "villa",
        "bungalow": "house",
        "townhouse": "house",
        "palazzo": "house",
        "farmhouse": "house",
    }

    def parse(self, response):
        """Parse listing index pages."""
        # Extract property listing links
        listings = response.css("a[href*='/listing/']::attr(href)").getall()
        for url in listings:
            yield response.follow(url, callback=self.parse_listing)

        # Follow pagination
        next_page = response.css("a.next-page::attr(href), a[rel='next']::attr(href)").get()
        if next_page:
            yield response.follow(next_page, callback=self.parse)

    def parse_listing(self, response):
        """Parse a single property listing."""
        # TODO: Adapt selectors after inspecting actual page structure
        title = response.css("h1::text").get("").strip()
        price_text = response.css("[class*='price']::text").get("")
        area_text = response.css("[class*='area'], [class*='size']::text").get("")
        location = response.css("[class*='location'], [class*='address']::text").get("")

        price = self.parse_price(price_text)
        area = self.parse_area(area_text)

        if not price:
            return

        # Detect property type from title/URL
        prop_type = "apartment"  # default
        title_lower = title.lower()
        for keyword, mapped_type in self.TYPE_MAP.items():
            if keyword in title_lower:
                prop_type = mapped_type
                break

        yield self.make_item(
            external_id=response.url.split("/")[-1],
            address_raw=location,
            property_type=prop_type,
            area_sqm=area,
            price=price,
            price_type="asking",
            url=response.url,
            raw_description=title,
        )
