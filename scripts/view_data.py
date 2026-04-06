"""Quick data viewer for the scraped property database."""

import json
import os
import sqlite3
import sys

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "pricemap.db")


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    print("=" * 70)
    print("PriceMap Database Summary")
    print("=" * 70)

    # Overall stats
    total = conn.execute("SELECT COUNT(*) FROM properties").fetchone()[0]
    print(f"\nTotal properties: {total}")
    print(f"Database: {DB_PATH}")
    print(f"Size: {os.path.getsize(DB_PATH) / 1024 / 1024:.1f} MB")

    # Per source
    print(f"\n{'Source':<20} {'Total':>6} {'Price':>6} {'Coords':>7} {'Area':>6} {'Desc':>6} {'Images':>7} {'Location':>9}")
    print("-" * 70)
    for row in conn.execute("""
        SELECT source, COUNT(*) as total,
            COUNT(CASE WHEN price_eur > 0 THEN 1 END) as prices,
            COUNT(CASE WHEN lat IS NOT NULL THEN 1 END) as coords,
            COUNT(CASE WHEN area_sqm > 0 THEN 1 END) as areas,
            COUNT(CASE WHEN description != '' THEN 1 END) as descs,
            COUNT(CASE WHEN image_urls != '[]' THEN 1 END) as imgs,
            COUNT(CASE WHEN locality IS NOT NULL THEN 1 END) as locs
        FROM properties GROUP BY source
    """):
        print(f"{row['source']:<20} {row['total']:>6} {row['prices']:>6} {row['coords']:>7} {row['areas']:>6} {row['descs']:>6} {row['imgs']:>7} {row['locs']:>9}")

    # Per country
    print(f"\n{'Country':<10} {'N':>6} {'Avg EUR':>12} {'Min EUR':>12} {'Max EUR':>12}")
    print("-" * 55)
    for row in conn.execute("""
        SELECT c.name, COUNT(*) as n,
            CAST(AVG(p.price_eur) AS INT) as avg_p,
            CAST(MIN(p.price_eur) AS INT) as min_p,
            CAST(MAX(p.price_eur) AS INT) as max_p
        FROM properties p JOIN countries c ON c.id = p.country_id
        WHERE p.price_eur > 0
        GROUP BY c.code
    """):
        print(f"{row['name']:<10} {row['n']:>6} {row['avg_p']:>12,} {row['min_p']:>12,} {row['max_p']:>12,}")

    # Property types
    print("\nProperty types:")
    for row in conn.execute("""
        SELECT property_type, COUNT(*) as n FROM properties
        GROUP BY property_type ORDER BY n DESC
    """):
        print(f"  {row['property_type']:<15} {row['n']:>5}")

    # Top localities
    print("\nTop 10 localities:")
    for row in conn.execute("""
        SELECT locality, COUNT(*) as n FROM properties
        WHERE locality IS NOT NULL
        GROUP BY locality ORDER BY n DESC LIMIT 10
    """):
        print(f"  {row['locality']:<25} {row['n']:>5}")

    # Images
    img_dir = os.path.join(os.path.dirname(DB_PATH), "images")
    if os.path.exists(img_dir):
        img_count = sum(len(f) for _, _, f in os.walk(img_dir))
        img_size = sum(
            os.path.getsize(os.path.join(dp, f))
            for dp, _, fn in os.walk(img_dir)
            for f in fn
        )
        print(f"\nImages: {img_count} files, {img_size / 1024 / 1024:.0f} MB")

    # Scrape runs
    print("\nScrape runs:")
    for row in conn.execute("""
        SELECT spider_name, status, items_scraped, items_new, errors_count, started_at
        FROM scrape_runs ORDER BY started_at DESC
    """):
        print(f"  {row['spider_name']:<20} {row['status']:<10} scraped={row['items_scraped']} new={row['items_new']} errors={row['errors_count']}")

    # Sample record
    if "--sample" in sys.argv:
        source = sys.argv[sys.argv.index("--sample") + 1] if len(sys.argv) > sys.argv.index("--sample") + 1 else None
        where = f"WHERE source='{source}'" if source else ""
        row = conn.execute(f"""
            SELECT * FROM properties {where} ORDER BY RANDOM() LIMIT 1
        """).fetchone()
        if row:
            print(f"\n{'='*70}")
            print(f"Sample record (id={row['id']}):")
            print(f"{'='*70}")
            for key in row.keys():
                val = row[key]
                if val and key in ("image_urls", "image_local_paths", "raw_json"):
                    try:
                        parsed = json.loads(val)
                        if isinstance(parsed, list):
                            val = f"[{len(parsed)} items]"
                        else:
                            val = json.dumps(parsed, ensure_ascii=False)[:100]
                    except (json.JSONDecodeError, TypeError):
                        pass
                if val is not None and val != "":
                    if isinstance(val, str) and len(val) > 100:
                        val = val[:100] + "..."
                    print(f"  {key:<25} {val}")

    conn.close()


if __name__ == "__main__":
    main()
