import scrapy

from src.items import PropertyItem


class BasePropertySpider(scrapy.Spider):
    """Base spider with common property parsing logic."""

    country_code: str = ""
    source: str = ""

    def make_item(self, **kwargs) -> PropertyItem:
        """Create a PropertyItem with common fields pre-filled."""
        item = PropertyItem()
        item["source"] = self.source
        item["country_code"] = self.country_code
        item["price_currency"] = "EUR"
        item["price_type"] = "asking"

        for key, value in kwargs.items():
            if value is not None:
                item[key] = value

        return item

    def parse_price(self, text: str) -> float | None:
        """Extract numeric price from text like '€250,000' or '250 000 EUR'."""
        if not text:
            return None
        import re

        cleaned = re.sub(r"[^\d.,]", "", text.strip())
        cleaned = cleaned.replace(",", "").replace(" ", "")
        # Handle European format: 250.000 -> 250000
        if cleaned.count(".") > 1:
            cleaned = cleaned.replace(".", "")
        elif cleaned.count(".") == 1 and len(cleaned.split(".")[-1]) == 3:
            cleaned = cleaned.replace(".", "")

        try:
            return float(cleaned)
        except ValueError:
            return None

    def parse_area(self, text: str) -> float | None:
        """Extract area in sqm from text like '85 m²' or '85m2'."""
        if not text:
            return None
        import re

        match = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:m²|m2|sq\.?\s*m)", text, re.IGNORECASE)
        if match:
            return float(match.group(1).replace(",", "."))
        return None
