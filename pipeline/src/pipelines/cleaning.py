import re

from scrapy.exceptions import DropItem


class CleaningPipeline:
    """Normalize prices, addresses, and property fields."""

    # BGN to EUR fixed rate
    BGN_EUR_RATE = 1 / 1.95583

    def process_item(self, item, spider):
        # Must have a price
        if not item.get("price"):
            raise DropItem(f"Missing price: {item.get('url', 'unknown')}")

        # Convert BGN to EUR
        if item.get("price_currency") == "BGN":
            item["price"] = round(item["price"] * self.BGN_EUR_RATE, 2)
            item["price_currency"] = "EUR"

        # Normalize address: strip extra whitespace, normalize commas
        if item.get("address_raw"):
            addr = item["address_raw"]
            addr = re.sub(r"\s+", " ", addr).strip()
            addr = re.sub(r"\s*,\s*", ", ", addr)
            item["address_raw"] = addr

        # Normalize property type
        if item.get("property_type"):
            item["property_type"] = item["property_type"].lower().strip()

        # Ensure area is reasonable
        if item.get("area_sqm"):
            area = float(item["area_sqm"])
            if area < 5 or area > 10000:
                item["area_sqm"] = None  # Suspicious, clear it

        # Clamp floor values
        if item.get("floor") is not None:
            floor = int(item["floor"])
            if floor < -5 or floor > 100:
                item["floor"] = None

        return item
