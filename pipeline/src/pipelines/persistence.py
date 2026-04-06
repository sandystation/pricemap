import logging
from datetime import datetime, timezone

from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class PersistencePipeline:
    """Write property items to PostgreSQL."""

    def __init__(self):
        self.engine = None
        self._country_cache: dict[str, int] = {}

    def open_spider(self, spider):
        db_url = spider.settings.get("DATABASE_URL")
        # Convert async URL to sync for Scrapy
        sync_url = db_url.replace("+asyncpg", "").replace("postgresql://", "postgresql://")
        self.engine = create_engine(sync_url)
        logger.info("Database connection established")

    def close_spider(self, spider):
        if self.engine:
            self.engine.dispose()

    def process_item(self, item, spider):
        with Session(self.engine) as session:
            country_id = self._get_country_id(session, item.get("country_code", ""))
            if not country_id:
                logger.warning(f"Unknown country: {item.get('country_code')}")
                return item

            now = datetime.now(timezone.utc)

            # Build geometry point if we have coordinates
            geom_expr = None
            if item.get("lat") and item.get("lon"):
                geom_expr = text(
                    f"ST_SetSRID(ST_MakePoint({item['lon']}, {item['lat']}), 4326)"
                )

            # Check for existing record (upsert by dedup_hash)
            dedup_hash = item.get("dedup_hash")
            if dedup_hash:
                existing = session.execute(
                    text("SELECT id FROM properties WHERE dedup_hash = :hash"),
                    {"hash": dedup_hash},
                ).fetchone()

                if existing:
                    # Update existing
                    session.execute(
                        text("""
                            UPDATE properties SET
                                price_eur = :price,
                                price_adjusted_eur = :price_adjusted,
                                is_active = true,
                                scraped_at = :now,
                                updated_at = :now
                            WHERE dedup_hash = :hash
                        """),
                        {
                            "price": item.get("price"),
                            "price_adjusted": item.get("price_adjusted"),
                            "now": now,
                            "hash": dedup_hash,
                        },
                    )
                    session.commit()
                    return item

            # Insert new record
            insert_sql = """
                INSERT INTO properties (
                    country_id, external_id, source,
                    address_raw, locality, lat, lon, geometry,
                    property_type, area_sqm, floor, total_floors,
                    rooms, bedrooms, bathrooms,
                    year_built, year_renovated, condition,
                    has_parking, has_garden, has_pool, has_elevator, has_balcony,
                    energy_class,
                    price_eur, price_original, price_currency,
                    price_type, price_adjusted_eur,
                    listing_date, transaction_date, scraped_at,
                    is_active, dedup_hash,
                    created_at, updated_at
                ) VALUES (
                    :country_id, :external_id, :source,
                    :address_raw, :locality, :lat, :lon,
                    {geom},
                    :property_type, :area_sqm, :floor, :total_floors,
                    :rooms, :bedrooms, :bathrooms,
                    :year_built, :year_renovated, :condition,
                    :has_parking, :has_garden, :has_pool, :has_elevator, :has_balcony,
                    :energy_class,
                    :price_eur, :price_original, :price_currency,
                    :price_type, :price_adjusted,
                    :listing_date, :transaction_date, :now,
                    true, :dedup_hash,
                    :now, :now
                )
            """.format(
                geom=f"ST_SetSRID(ST_MakePoint({item.get('lon', 0)}, {item.get('lat', 0)}), 4326)"
                if item.get("lat") and item.get("lon")
                else "NULL"
            )

            params = {
                "country_id": country_id,
                "external_id": item.get("external_id"),
                "source": item.get("source"),
                "address_raw": item.get("address_raw"),
                "locality": item.get("locality"),
                "lat": item.get("lat"),
                "lon": item.get("lon"),
                "property_type": item.get("property_type", "apartment"),
                "area_sqm": item.get("area_sqm"),
                "floor": item.get("floor"),
                "total_floors": item.get("total_floors"),
                "rooms": item.get("rooms"),
                "bedrooms": item.get("bedrooms"),
                "bathrooms": item.get("bathrooms"),
                "year_built": item.get("year_built"),
                "year_renovated": item.get("year_renovated"),
                "condition": item.get("condition"),
                "has_parking": item.get("has_parking"),
                "has_garden": item.get("has_garden"),
                "has_pool": item.get("has_pool"),
                "has_elevator": item.get("has_elevator"),
                "has_balcony": item.get("has_balcony"),
                "energy_class": item.get("energy_class"),
                "price_eur": item.get("price"),
                "price_original": item.get("price"),
                "price_currency": item.get("price_currency", "EUR"),
                "price_type": item.get("price_type", "asking"),
                "price_adjusted": item.get("price_adjusted"),
                "listing_date": item.get("listing_date"),
                "transaction_date": item.get("transaction_date"),
                "now": now,
                "dedup_hash": dedup_hash,
            }

            try:
                session.execute(text(insert_sql), params)
                session.commit()
            except Exception as e:
                session.rollback()
                logger.error(f"Insert failed: {e}")

        return item

    def _get_country_id(self, session: Session, country_code: str) -> int | None:
        if country_code in self._country_cache:
            return self._country_cache[country_code]

        result = session.execute(
            text("SELECT id FROM countries WHERE code = :code"),
            {"code": country_code.upper()},
        ).fetchone()

        if result:
            self._country_cache[country_code] = result[0]
            return result[0]
        return None
