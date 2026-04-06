"""Data viewer for the PriceMap document store."""

import argparse
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime

from docstore import DocStore

IMAGE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "images")


def main():
    parser = argparse.ArgumentParser(description="PriceMap data viewer")
    parser.add_argument("--price-drops", action="store_true", help="Show price drops")
    parser.add_argument("--price-rises", action="store_true", help="Show price increases")
    parser.add_argument("--longest-listed", action="store_true", help="Days on market ranking")
    parser.add_argument("--changes", action="store_true", help="Summary of all change events")
    parser.add_argument("--property", type=str, help="Full history for a document ID")
    args = parser.parse_args()

    store = DocStore()
    collections = store.list_collections()

    if args.property:
        show_property_history(store, collections, args.property)
    elif args.price_drops:
        show_price_changes(store, collections, direction="drop")
    elif args.price_rises:
        show_price_changes(store, collections, direction="rise")
    elif args.longest_listed:
        show_longest_listed(store, collections)
    elif args.changes:
        show_changes_summary(store, collections)
    else:
        show_summary(store, collections)

    store.close()


def show_summary(store, collections):
    print("=" * 70)
    print("PriceMap Document Store Summary")
    print("=" * 70)

    total = 0
    all_docs = []

    print(f"\n{'Collection':<20} {'Total':>6} {'Price':>6} {'Coords':>7} {'Area':>6} {'Desc':>6} {'Images':>7} {'Loc':>6}")
    print("-" * 70)

    for name in collections:
        coll = store.collection(name)
        docs = coll.find()
        total += len(docs)
        all_docs.extend(docs)

        with_price = sum(1 for d in docs if d["current"].get("price_eur"))
        with_coords = sum(1 for d in docs if d["current"].get("lat"))
        with_area = sum(1 for d in docs if d["current"].get("area_sqm"))
        with_desc = sum(1 for d in docs if d["current"].get("description"))
        with_imgs = sum(1 for d in docs if d["current"].get("image_urls"))
        with_loc = sum(1 for d in docs if d["current"].get("locality"))

        print(f"{name:<20} {len(docs):>6} {with_price:>6} {with_coords:>7} {with_area:>6} {with_desc:>6} {with_imgs:>7} {with_loc:>6}")

    print(f"\nTotal: {total} properties across {len(collections)} collections")

    # Price stats by country
    by_country = defaultdict(list)
    for d in all_docs:
        p = d["current"].get("price_eur")
        if p and p > 0:
            by_country[d.get("country", "?")].append(p)

    if by_country:
        print(f"\n{'Country':<10} {'N':>6} {'Avg EUR':>12} {'Min EUR':>12} {'Max EUR':>12}")
        print("-" * 55)
        for country, prices in sorted(by_country.items()):
            print(f"{country:<10} {len(prices):>6} {int(sum(prices)/len(prices)):>12,} {int(min(prices)):>12,} {int(max(prices)):>12,}")

    # Property types
    types = Counter(d["current"].get("property_type", "unknown") for d in all_docs)
    print("\nProperty types:")
    for t, n in types.most_common():
        print(f"  {t:<15} {n:>5}")

    # Top localities
    locs = Counter(d["current"].get("locality") for d in all_docs if d["current"].get("locality"))
    print("\nTop 10 localities:")
    for loc, n in locs.most_common(10):
        print(f"  {loc:<30} {n:>5}")

    # History stats
    total_events = 0
    event_types = Counter()
    for d in all_docs:
        for h in d.get("history", []):
            total_events += 1
            event_types[h.get("event", "unknown")] += 1

    print(f"\nHistory: {total_events} events")
    for et, n in event_types.most_common():
        print(f"  {et:<25} {n:>5}")

    # Images on disk
    if os.path.exists(IMAGE_DIR):
        img_count = sum(len(f) for _, _, f in os.walk(IMAGE_DIR))
        img_size = sum(
            os.path.getsize(os.path.join(dp, f))
            for dp, _, fn in os.walk(IMAGE_DIR)
            for f in fn
        )
        print(f"\nImages on disk: {img_count} files, {img_size / 1024 / 1024:.0f} MB")


def show_price_changes(store, collections, direction="drop"):
    """Show properties with price changes."""
    label = "Price Drops" if direction == "drop" else "Price Increases"
    print(f"\n{'=' * 70}")
    print(label)
    print(f"{'=' * 70}\n")

    changes = []
    for name in collections:
        coll = store.collection(name)
        for doc in coll.find():
            for h in doc.get("history", []):
                pc = (h.get("changes") or {}).get("price_eur")
                if pc and pc.get("old") and pc.get("new"):
                    old, new = pc["old"], pc["new"]
                    if (direction == "drop" and new < old) or (direction == "rise" and new > old):
                        pct = (new - old) / old * 100
                        changes.append({
                            "id": doc["_id"],
                            "locality": doc["current"].get("locality", "?"),
                            "type": doc["current"].get("property_type", "?"),
                            "old": old,
                            "new": new,
                            "pct": pct,
                            "date": h["date"],
                        })

    if not changes:
        print("No price changes found yet. Run scrapers multiple times to detect changes.")
        return

    changes.sort(key=lambda x: x["pct"] if direction == "drop" else -x["pct"])
    print(f"{'ID':<35} {'Locality':<15} {'Old':>10} {'New':>10} {'Change':>8} {'Date'}")
    print("-" * 95)
    for c in changes[:30]:
        print(f"{c['id']:<35} {c['locality']:<15} {c['old']:>10,.0f} {c['new']:>10,.0f} {c['pct']:>+7.1f}% {c['date'][:10]}")


def show_longest_listed(store, collections):
    """Show properties that have been listed the longest."""
    print(f"\n{'=' * 70}")
    print("Longest Listed Properties")
    print(f"{'=' * 70}\n")

    listings = []
    now = datetime.utcnow()
    for name in collections:
        coll = store.collection(name)
        for doc in coll.find():
            fs = doc.get("first_seen")
            if fs:
                try:
                    first = datetime.fromisoformat(fs.replace("+00:00", "").replace("Z", ""))
                    days = (now - first).days
                    listings.append({
                        "id": doc["_id"],
                        "locality": doc["current"].get("locality", "?"),
                        "price": doc["current"].get("price_eur", 0),
                        "type": doc["current"].get("property_type", "?"),
                        "days": days,
                        "first_seen": fs[:10],
                    })
                except (ValueError, TypeError):
                    pass

    listings.sort(key=lambda x: -x["days"])
    print(f"{'ID':<35} {'Locality':<15} {'Price':>10} {'Days':>5} {'First Seen'}")
    print("-" * 85)
    for l in listings[:30]:
        print(f"{l['id']:<35} {l['locality']:<15} {l['price']:>10,.0f} {l['days']:>5} {l['first_seen']}")


def show_changes_summary(store, collections):
    """Summary of all change events."""
    print(f"\n{'=' * 70}")
    print("Change Events Summary")
    print(f"{'=' * 70}\n")

    by_collection = defaultdict(lambda: Counter())
    for name in collections:
        coll = store.collection(name)
        for doc in coll.find():
            for h in doc.get("history", []):
                by_collection[name][h.get("event", "unknown")] += 1

    for name, events in sorted(by_collection.items()):
        total = sum(events.values())
        print(f"\n{name} ({total} events):")
        for et, n in events.most_common():
            print(f"  {et:<25} {n:>5}")


def show_property_history(store, collections, doc_id):
    """Full history for a single property."""
    for name in collections:
        coll = store.collection(name)
        doc = coll.get(doc_id)
        if doc:
            print(f"\n{'=' * 70}")
            print(f"Property: {doc_id}")
            print(f"{'=' * 70}")
            print(f"Source: {doc.get('source')}")
            print(f"Country: {doc.get('country')}")
            print(f"First seen: {doc.get('first_seen')}")
            print(f"Last seen: {doc.get('last_seen')}")

            print(f"\n--- Current State ---")
            cur = doc.get("current", {})
            for k, v in sorted(cur.items()):
                if v is not None and v != "" and v != []:
                    if isinstance(v, str) and len(v) > 80:
                        v = v[:80] + "..."
                    if isinstance(v, list):
                        v = f"[{len(v)} items]"
                    print(f"  {k:<25} {v}")

            print(f"\n--- History ({len(doc.get('history', []))} events) ---")
            for h in doc.get("history", []):
                print(f"  [{h['date'][:19]}] {h['event']}")
                for field, change in (h.get("changes") or {}).items():
                    if isinstance(change, dict):
                        print(f"    {field}: {change.get('old')} → {change.get('new')}")
                    else:
                        print(f"    {field}: {change}")
            return

    print(f"Property {doc_id} not found. Try one of the existing IDs from --summary.")


if __name__ == "__main__":
    main()
