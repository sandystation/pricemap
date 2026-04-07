"""
RE/MAX Malta enrichment - fetches detail API for each listing to add
descriptions, features, room dimensions, agent info, and full photos.

The list API at /api/properties returns empty Description fields.
The detail API at /api/properties/{MLS} has everything.

Usage:
    cd scripts
    python enrich_remax_mt.py              # Enrich all docs missing descriptions
    python enrich_remax_mt.py --all        # Re-enrich everything
    python enrich_remax_mt.py --delay 0.5  # Faster (default 1.0s)
"""

import argparse
import logging
import time

import httpx

from scraper_base import get_store

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("enrich_remax")

DETAIL_API = "https://remax-malta.com/api/properties"


def fetch_detail(client: httpx.Client, mls: str) -> dict | None:
    """Fetch the detail API for a single property."""
    try:
        resp = client.get(f"{DETAIL_API}/{mls}")
        resp.raise_for_status()
        return resp.json().get("data", {})
    except Exception as e:
        logger.error(f"Failed to fetch {mls}: {e}")
        return None


def enrich_doc(doc: dict, detail: dict) -> bool:
    """Update a doc's current fields from the detail API response.
    Returns True if anything changed."""
    cur = doc.get("current", {})
    changed = False

    # Description
    desc = detail.get("Description", "")
    if desc and desc != cur.get("description", ""):
        cur["description"] = desc
        changed = True

    # Features (structured)
    features = detail.get("Features", [])
    if features:
        feature_names = [f["Name"] for f in features if f.get("Name")]
        if feature_names != cur.get("features", []):
            cur["features"] = feature_names
            changed = True

        # Extract boolean amenities from features
        feat_lower = " ".join(feature_names).lower()
        for field, keywords in [
            ("has_balcony", ["balcony", "terrace"]),
            ("has_pool", ["pool"]),
            ("has_garden", ["garden"]),
            ("has_elevator", ["lift", "elevator"]),
            ("has_parking", ["parking"]),
        ]:
            if any(kw in feat_lower for kw in keywords):
                if not cur.get(field):
                    cur[field] = 1
                    changed = True

    # Room dimensions
    rooms = detail.get("Rooms", [])
    if rooms:
        rooms_detail = []
        for r in rooms:
            rt = r.get("RoomType", {})
            rooms_detail.append({
                "type": rt.get("Name", ""),
                "width": r.get("RoomWidth"),
                "length": r.get("RoomLength"),
                "size_sqm": r.get("RoomSize"),
                "description": r.get("Description"),
            })
        cur["rooms_detail"] = rooms_detail
        changed = True

    # Agent info
    agent = detail.get("Agent", {})
    if agent:
        agent_name = f"{agent.get('Name', '')} {agent.get('Surname', '')}".strip()
        if agent_name and agent_name != cur.get("agent_name"):
            cur["agent_name"] = agent_name
            changed = True
        if agent.get("WorkEmail"):
            cur["agent_email"] = agent["WorkEmail"]
            changed = True
        if agent.get("MobileNumber"):
            cur["agent_phone"] = agent["MobileNumber"]
            changed = True
        office = agent.get("Office", {})
        if office.get("Name"):
            cur["agent_office"] = office["Name"]
            changed = True

    # Energy rating
    energy = detail.get("EnergyRating", "")
    if energy and energy != cur.get("energy_rating"):
        cur["energy_rating"] = energy
        changed = True

    # Measurements
    meas = detail.get("Measurment", {})
    if meas:
        plot = meas.get("PlotSize")
        if plot and plot > 0:
            cur["plot_size_sqm"] = plot
            changed = True
        roof = meas.get("RoofSquareMeters")
        if roof and roof > 0:
            cur["roof_sqm"] = roof
            changed = True

    # All photos (high res)
    photos = detail.get("Photos", [])
    if photos:
        high_res_urls = []
        for p in photos:
            high = p.get("High", {})
            url = high.get("ImageURL", "")
            if url:
                high_res_urls.append(url)
        if high_res_urls and high_res_urls != cur.get("all_image_urls"):
            cur["all_image_urls"] = high_res_urls
            changed = True

    # Store raw detail API response
    cur["raw_data_detail"] = detail
    changed = True

    return changed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--all", action="store_true", help="Re-enrich all docs")
    parser.add_argument("--delay", type=float, default=1.0, help="Delay between requests")
    args = parser.parse_args()

    store = get_store()
    coll = store.collection("mt_remax")
    coll._ensure_loaded()

    client = httpx.Client(
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
            "Referer": "https://www.remax-malta.com/property-for-sale",
        },
        timeout=30.0,
        follow_redirects=True,
    )

    # Find docs to enrich
    to_enrich = []
    for doc_id, doc in coll._docs.items():
        cur = doc.get("current", {})
        if args.all or not cur.get("description"):
            mls = cur.get("external_id") or doc_id.split(":", 1)[-1]
            to_enrich.append((doc_id, mls))

    total = len(to_enrich)
    logger.info(f"Enriching {total} docs (delay={args.delay}s, est. {total * args.delay / 3600:.1f}h)")

    enriched = 0
    errors = 0

    try:
        for i, (doc_id, mls) in enumerate(to_enrich):
            detail = fetch_detail(client, mls)
            if detail is None:
                errors += 1
                time.sleep(args.delay)
                continue

            doc = coll._docs[doc_id]
            if enrich_doc(doc, detail):
                coll._mark_dirty()
                enriched += 1

            if (i + 1) % 100 == 0:
                logger.info(f"Progress: {i + 1}/{total} ({enriched} enriched, {errors} errors)")

            time.sleep(args.delay)

    except KeyboardInterrupt:
        logger.info("Interrupted — flushing what we have")
    finally:
        coll.flush()
        coll.close()
        client.close()
        store.close()

    logger.info(f"DONE: {enriched} enriched, {errors} errors out of {total}")


if __name__ == "__main__":
    main()
