import scrapy


class PropertyItem(scrapy.Item):
    """Unified property item across all spiders."""

    # Source identification
    source = scrapy.Field()  # DataSource enum value
    external_id = scrapy.Field()
    country_code = scrapy.Field()  # MT, BG, CY, HR

    # Address
    address_raw = scrapy.Field()
    locality = scrapy.Field()
    lat = scrapy.Field()
    lon = scrapy.Field()

    # Property characteristics
    property_type = scrapy.Field()  # apartment, house, villa, etc.
    area_sqm = scrapy.Field()
    floor = scrapy.Field()
    total_floors = scrapy.Field()
    rooms = scrapy.Field()
    bedrooms = scrapy.Field()
    bathrooms = scrapy.Field()
    year_built = scrapy.Field()
    year_renovated = scrapy.Field()
    condition = scrapy.Field()

    # Amenities
    has_parking = scrapy.Field()
    has_garden = scrapy.Field()
    has_pool = scrapy.Field()
    has_elevator = scrapy.Field()
    has_balcony = scrapy.Field()
    energy_class = scrapy.Field()

    # Pricing
    price = scrapy.Field()  # Original price value
    price_currency = scrapy.Field()  # EUR, BGN, etc.
    price_type = scrapy.Field()  # asking, transaction, assessed

    # Dates
    listing_date = scrapy.Field()
    transaction_date = scrapy.Field()

    # Raw data for debugging
    url = scrapy.Field()
    raw_description = scrapy.Field()
