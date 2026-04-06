"""
Seed the countries table with initial data.
Run once after database migration:
    python scripts/seed_countries.py
"""

import os

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://pricemap:pricemap_dev@localhost:5432/pricemap"
)

COUNTRIES = [
    {"code": "MT", "name": "Malta", "currency": "EUR"},
    {"code": "BG", "name": "Bulgaria", "currency": "EUR"},
    {"code": "CY", "name": "Cyprus", "currency": "EUR"},
    {"code": "HR", "name": "Croatia", "currency": "EUR"},
]

# Key regions/localities for each country
REGIONS = {
    "MT": [
        "Valletta", "Sliema", "St Julian's", "Gzira", "Msida", "Birkirkara",
        "Mosta", "Naxxar", "San Gwann", "Swieqi", "Attard", "Balzan", "Lija",
        "Rabat", "Mdina", "Mellieha", "St Paul's Bay", "Bugibba",
        "Marsaskala", "Zabbar", "Fgura", "Paola", "Tarxien",
        "Victoria (Gozo)", "Marsalforn", "Xlendi",
    ],
    "BG": [
        "Sofia", "Plovdiv", "Varna", "Burgas", "Ruse", "Stara Zagora",
        "Pleven", "Sliven", "Dobrich", "Shumen", "Blagoevgrad",
        "Veliko Tarnovo", "Bansko", "Sunny Beach", "Golden Sands",
    ],
    "CY": [
        "Nicosia", "Limassol", "Larnaca", "Paphos", "Famagusta",
        "Paralimni", "Ayia Napa",
    ],
    "HR": [
        "Zagreb", "Split", "Rijeka", "Osijek", "Zadar", "Dubrovnik",
        "Pula", "Rovinj", "Makarska", "Hvar", "Korcula",
    ],
}


def seed():
    engine = create_engine(DATABASE_URL)

    with Session(engine) as session:
        for country in COUNTRIES:
            # Upsert country
            existing = session.execute(
                text("SELECT id FROM countries WHERE code = :code"),
                {"code": country["code"]},
            ).fetchone()

            if existing:
                country_id = existing[0]
                print(f"Country {country['code']} already exists (id={country_id})")
            else:
                result = session.execute(
                    text(
                        "INSERT INTO countries (code, name, currency) "
                        "VALUES (:code, :name, :currency) RETURNING id"
                    ),
                    country,
                )
                country_id = result.fetchone()[0]
                print(f"Inserted country {country['code']} (id={country_id})")

            # Seed regions
            regions = REGIONS.get(country["code"], [])
            for region_name in regions:
                exists = session.execute(
                    text(
                        "SELECT id FROM regions WHERE country_id = :cid AND name = :name"
                    ),
                    {"cid": country_id, "name": region_name},
                ).fetchone()

                if not exists:
                    session.execute(
                        text(
                            "INSERT INTO regions (country_id, name) VALUES (:cid, :name)"
                        ),
                        {"cid": country_id, "name": region_name},
                    )

            session.commit()
            print(f"  Seeded {len(regions)} regions for {country['code']}")

    engine.dispose()
    print("Done!")


if __name__ == "__main__":
    seed()
