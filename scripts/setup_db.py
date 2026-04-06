"""
Set up SQLite file-based database for local development and scraping.
"""

import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "pricemap.db")


def get_db(path=DB_PATH):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def create_tables(conn):
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS countries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        currency TEXT DEFAULT 'EUR'
    );

    CREATE TABLE IF NOT EXISTS regions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        country_id INTEGER REFERENCES countries(id),
        name TEXT NOT NULL,
        UNIQUE(country_id, name)
    );

    CREATE TABLE IF NOT EXISTS properties (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        country_id INTEGER REFERENCES countries(id),
        region_id INTEGER REFERENCES regions(id),
        external_id TEXT,
        source TEXT NOT NULL,

        -- Address & Location
        address_raw TEXT,
        address_normalized TEXT,
        locality TEXT,
        lat REAL,
        lon REAL,

        -- Property characteristics
        property_type TEXT,
        area_sqm REAL,
        floor INTEGER,
        total_floors INTEGER,
        rooms INTEGER,
        bedrooms INTEGER,
        bathrooms INTEGER,
        year_built INTEGER,
        year_renovated INTEGER,
        condition TEXT,

        -- Amenities
        has_parking INTEGER,
        has_garden INTEGER,
        has_pool INTEGER,
        has_elevator INTEGER,
        has_balcony INTEGER,
        has_furnishing INTEGER,
        has_garage INTEGER,
        energy_class TEXT,

        -- Construction
        construction_type TEXT,

        -- Pricing
        price_eur REAL,
        price_original REAL,
        price_currency TEXT DEFAULT 'EUR',
        price_type TEXT DEFAULT 'asking',
        price_per_sqm REAL,
        price_adjusted_eur REAL,

        -- Dates
        listing_date TEXT,
        transaction_date TEXT,
        scraped_at TEXT,
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now')),

        -- Content
        title TEXT,
        description TEXT,
        url TEXT,
        image_urls TEXT,  -- JSON array of image URLs
        image_local_paths TEXT,  -- JSON array of local file paths

        -- Agent/seller
        agent_name TEXT,
        agent_company TEXT,
        agent_phone TEXT,
        agent_url TEXT,

        -- Status
        is_active INTEGER DEFAULT 1,
        dedup_hash TEXT,

        -- Raw data
        raw_json TEXT  -- Full raw scraped data as JSON for debugging
    );

    CREATE INDEX IF NOT EXISTS ix_properties_source ON properties(source);
    CREATE INDEX IF NOT EXISTS ix_properties_country ON properties(country_id);
    CREATE INDEX IF NOT EXISTS ix_properties_type ON properties(property_type);
    CREATE INDEX IF NOT EXISTS ix_properties_price ON properties(price_eur);
    CREATE INDEX IF NOT EXISTS ix_properties_dedup ON properties(dedup_hash);
    CREATE INDEX IF NOT EXISTS ix_properties_locality ON properties(locality);
    CREATE INDEX IF NOT EXISTS ix_properties_latlon ON properties(lat, lon);
    CREATE UNIQUE INDEX IF NOT EXISTS ix_properties_ext ON properties(source, external_id);

    CREATE TABLE IF NOT EXISTS scrape_runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        spider_name TEXT NOT NULL,
        country_code TEXT,
        started_at TEXT DEFAULT (datetime('now')),
        finished_at TEXT,
        items_scraped INTEGER DEFAULT 0,
        items_new INTEGER DEFAULT 0,
        items_updated INTEGER DEFAULT 0,
        errors_count INTEGER DEFAULT 0,
        status TEXT DEFAULT 'running'
    );
    """)
    conn.commit()


def seed_countries(conn):
    countries = [
        ("MT", "Malta", "EUR"),
        ("BG", "Bulgaria", "EUR"),
        ("CY", "Cyprus", "EUR"),
        ("HR", "Croatia", "EUR"),
    ]
    for code, name, currency in countries:
        conn.execute(
            "INSERT OR IGNORE INTO countries (code, name, currency) VALUES (?, ?, ?)",
            (code, name, currency),
        )

    # Key localities
    regions = {
        "MT": [
            "Valletta", "Sliema", "St Julian's", "Gzira", "Msida", "Birkirkara",
            "Mosta", "Naxxar", "San Gwann", "Swieqi", "Attard", "Balzan",
            "Mellieha", "St Paul's Bay", "Bugibba", "Marsaskala", "Zabbar",
            "Fgura", "Paola", "Tarxien", "Hamrun", "Qormi", "Rabat",
            "Victoria (Gozo)", "Marsalforn", "Xlendi", "Gharb",
        ],
        "BG": [
            "Sofia", "Plovdiv", "Varna", "Burgas", "Ruse", "Stara Zagora",
            "Pleven", "Sliven", "Dobrich", "Veliko Tarnovo", "Bansko",
            "Sunny Beach", "Golden Sands", "Blagoevgrad", "Shumen",
        ],
        "CY": [
            "Nicosia", "Limassol", "Larnaca", "Paphos", "Paralimni", "Ayia Napa",
        ],
        "HR": [
            "Zagreb", "Split", "Rijeka", "Osijek", "Zadar", "Dubrovnik",
            "Pula", "Rovinj", "Makarska",
        ],
    }

    for code, names in regions.items():
        country = conn.execute("SELECT id FROM countries WHERE code=?", (code,)).fetchone()
        if country:
            for name in names:
                conn.execute(
                    "INSERT OR IGNORE INTO regions (country_id, name) VALUES (?, ?)",
                    (country["id"], name),
                )

    conn.commit()


if __name__ == "__main__":
    conn = get_db()
    create_tables(conn)
    seed_countries(conn)

    # Verify
    for row in conn.execute("SELECT code, name FROM countries"):
        regions = conn.execute(
            "SELECT COUNT(*) as c FROM regions WHERE country_id = (SELECT id FROM countries WHERE code=?)",
            (row["code"],),
        ).fetchone()
        print(f"  {row['code']} - {row['name']}: {regions['c']} regions")

    conn.close()
    print(f"\nDatabase created at: {DB_PATH}")
