"""
Base scraper utilities: HTTP client, SQLite persistence, image downloading.
"""

import hashlib
import json
import logging
import os
import sqlite3
import time
from datetime import datetime, timezone

import httpx

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("scraper")

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "pricemap.db")
IMAGE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "images")

# BGN to EUR fixed rate
BGN_EUR_RATE = 1 / 1.95583

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def get_client(**kwargs):
    hdrs = dict(HEADERS)
    if "headers" in kwargs:
        hdrs.update(kwargs.pop("headers"))
    return httpx.Client(
        headers=hdrs,
        timeout=30.0,
        follow_redirects=True,
        **kwargs,
    )


def compute_dedup_hash(source: str, external_id: str) -> str:
    key = f"{source}:{external_id}"
    return hashlib.sha256(key.encode()).hexdigest()[:16]


def save_property(conn: sqlite3.Connection, data: dict) -> tuple[int, bool]:
    """
    Insert or update a property. Returns (id, is_new).
    """
    dedup = data.get("dedup_hash") or compute_dedup_hash(
        data.get("source", ""), data.get("external_id", "")
    )
    data["dedup_hash"] = dedup
    data["scraped_at"] = datetime.now(timezone.utc).isoformat()

    # Convert lists/dicts to JSON strings
    for field in ("image_urls", "image_local_paths"):
        if isinstance(data.get(field), (list, dict)):
            data[field] = json.dumps(data[field])
    if "raw_json" in data and not isinstance(data["raw_json"], str):
        data["raw_json"] = json.dumps(data["raw_json"], ensure_ascii=False)

    # Get country_id
    country_code = data.pop("country_code", None)
    if country_code and not data.get("country_id"):
        row = conn.execute(
            "SELECT id FROM countries WHERE code=?", (country_code,)
        ).fetchone()
        if row:
            data["country_id"] = row["id"]

    # Check existing
    existing = conn.execute(
        "SELECT id FROM properties WHERE source=? AND external_id=?",
        (data.get("source"), data.get("external_id")),
    ).fetchone()

    if existing:
        prop_id = existing["id"]
        # Update
        set_parts = []
        values = []
        skip = {"id", "created_at"}
        for k, v in data.items():
            if k not in skip and v is not None:
                set_parts.append(f"{k}=?")
                values.append(v)
        set_parts.append("updated_at=datetime('now')")
        values.append(prop_id)
        conn.execute(
            f"UPDATE properties SET {', '.join(set_parts)} WHERE id=?",
            values,
        )
        conn.commit()
        return prop_id, False
    else:
        # Insert
        cols = [k for k, v in data.items() if v is not None and k != "country_code"]
        placeholders = ", ".join(["?"] * len(cols))
        values = [data[k] for k in cols]
        cursor = conn.execute(
            f"INSERT INTO properties ({', '.join(cols)}) VALUES ({placeholders})",
            values,
        )
        conn.commit()
        return cursor.lastrowid, True


def download_images(
    client: httpx.Client,
    image_urls: list[str],
    source: str,
    external_id: str,
    max_images: int = 5,
) -> list[str]:
    """Download images to local storage. Returns list of local paths."""
    local_paths = []
    subdir = os.path.join(IMAGE_DIR, source)
    os.makedirs(subdir, exist_ok=True)

    for i, url in enumerate(image_urls[:max_images]):
        try:
            ext = ".jpg"
            if ".png" in url.lower():
                ext = ".png"
            elif ".webp" in url.lower():
                ext = ".webp"

            filename = f"{external_id}_{i}{ext}"
            filepath = os.path.join(subdir, filename)

            if os.path.exists(filepath):
                local_paths.append(filepath)
                continue

            resp = client.get(url)
            if resp.status_code == 200 and len(resp.content) > 1000:
                with open(filepath, "wb") as f:
                    f.write(resp.content)
                local_paths.append(filepath)
                time.sleep(0.3)
        except Exception as e:
            logger.warning(f"Failed to download image {url}: {e}")

    return local_paths


def start_scrape_run(conn, spider_name, country_code):
    cursor = conn.execute(
        "INSERT INTO scrape_runs (spider_name, country_code) VALUES (?, ?)",
        (spider_name, country_code),
    )
    conn.commit()
    return cursor.lastrowid


def finish_scrape_run(conn, run_id, items_scraped, items_new, errors_count):
    conn.execute(
        """UPDATE scrape_runs SET
            finished_at=datetime('now'), items_scraped=?, items_new=?,
            errors_count=?, status='finished'
        WHERE id=?""",
        (items_scraped, items_new, errors_count, run_id),
    )
    conn.commit()
