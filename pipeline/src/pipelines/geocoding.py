import logging
import time

from geopy.geocoders import Nominatim

logger = logging.getLogger(__name__)

COUNTRY_NAMES = {
    "MT": "Malta",
    "BG": "Bulgaria",
    "CY": "Cyprus",
    "HR": "Croatia",
}


class GeocodingPipeline:
    """Geocode addresses to lat/lon using Nominatim."""

    def __init__(self):
        self.geocoder = None
        self._cache: dict[str, tuple[float, float] | None] = {}
        self._last_request = 0.0

    def open_spider(self, spider):
        user_agent = spider.settings.get("NOMINATIM_USER_AGENT", "pricemap/0.1")
        self.geocoder = Nominatim(user_agent=user_agent)

    def process_item(self, item, spider):
        # Skip if already geocoded
        if item.get("lat") and item.get("lon"):
            return item

        address = item.get("address_raw")
        if not address:
            return item

        country = COUNTRY_NAMES.get(item.get("country_code", ""), "")
        query = f"{address}, {country}" if country else address

        # Check cache
        if query in self._cache:
            coords = self._cache[query]
            if coords:
                item["lat"], item["lon"] = coords
            return item

        # Rate limit: 1 request per second for Nominatim
        elapsed = time.time() - self._last_request
        if elapsed < 1.0:
            time.sleep(1.0 - elapsed)

        try:
            location = self.geocoder.geocode(query, exactly_one=True, timeout=10)
            self._last_request = time.time()

            if location:
                item["lat"] = location.latitude
                item["lon"] = location.longitude
                self._cache[query] = (location.latitude, location.longitude)
                logger.debug(f"Geocoded: {query} -> ({location.latitude}, {location.longitude})")
            else:
                self._cache[query] = None
                logger.warning(f"Could not geocode: {query}")
        except Exception as e:
            logger.error(f"Geocoding error for {query}: {e}")
            self._cache[query] = None

        return item
