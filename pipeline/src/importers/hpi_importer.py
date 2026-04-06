"""
Import House Price Index data from national statistical offices.

Sources:
- Malta: NSO RPPI (nso.gov.mt)
- Bulgaria: NSI HPI (nsi.bg)
- Can also pull from Eurostat or FRED for standardized data
"""

import logging

import httpx
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# FRED series IDs for residential property prices (BIS data)
FRED_SERIES = {
    "MT": None,  # Malta not in BIS/FRED -- use NSO directly
    "BG": "QBGN628BIS",
    "CY": None,
    "HR": "QHRR628BIS",
}


def import_hpi(database_url: str, country_code: str):
    """Import HPI data for a given country."""
    sync_url = database_url.replace("+asyncpg", "")
    engine = create_engine(sync_url)

    with Session(engine) as session:
        country = session.execute(
            text("SELECT id FROM countries WHERE code = :code"),
            {"code": country_code.upper()},
        ).fetchone()

        if not country:
            logger.error(f"Country {country_code} not found in database")
            return

        country_id = country[0]
        logger.info(f"Importing HPI for {country_code} (country_id={country_id})")

        # TODO: Implement per-country importers
        # For now, log what would be imported
        series_id = FRED_SERIES.get(country_code.upper())
        if series_id:
            logger.info(f"Would fetch FRED series: {series_id}")
            # Example FRED API call (requires API key):
            # url = f"https://api.stlouisfed.org/fred/series/observations?series_id={series_id}&api_key=KEY&file_type=json"
        else:
            logger.info(f"No FRED series for {country_code} -- use national source")

    engine.dispose()


if __name__ == "__main__":
    import os

    db_url = os.getenv("DATABASE_URL", "postgresql://pricemap:pricemap_dev@localhost:5432/pricemap")
    for code in ["MT", "BG"]:
        import_hpi(db_url, code)
