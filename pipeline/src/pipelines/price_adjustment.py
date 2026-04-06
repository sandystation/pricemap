import logging

logger = logging.getLogger(__name__)


class PriceAdjustmentPipeline:
    """Apply asking-to-transaction adjustment factors."""

    def open_spider(self, spider):
        self.factors = spider.settings.getdict("ADJUSTMENT_FACTORS", {})

    def process_item(self, item, spider):
        price = item.get("price")
        if not price:
            return item

        country = item.get("country_code", "")
        price_type = item.get("price_type", "asking")

        if price_type == "transaction":
            # Already a transaction price -- no adjustment needed
            item["price_adjusted"] = price
        elif price_type == "asking":
            factor = self.factors.get(country, 0.95)
            item["price_adjusted"] = round(price * factor, 2)
            logger.debug(
                f"Adjusted price for {country}: {price} * {factor} = {item['price_adjusted']}"
            )
        else:
            item["price_adjusted"] = price

        return item
