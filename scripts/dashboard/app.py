"""
PriceMap Dev Dashboard — browse scraped properties, view images, search, inspect data.

Usage:
    cd scripts && python -m dashboard.app
    # Opens at http://localhost:8500
"""

import math
import os
import sys
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# Add parent dir to path so we can import docstore
sys.path.insert(0, str(Path(__file__).parent.parent))
from docstore import DocStore

IMAGE_DIR = Path(__file__).parent.parent.parent / "data" / "images"
TEMPLATES_DIR = Path(__file__).parent / "templates"

app = FastAPI(title="PriceMap Dashboard")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

_store = None


def get_store():
    global _store
    if _store is None:
        _store = DocStore()
    return _store


# --- Jinja2 filters ---

def format_eur(value):
    if value is None or (hasattr(value, '_undefined_name')):
        return "—"
    try:
        return f"€{float(value):,.0f}"
    except (ValueError, TypeError):
        return "—"


def format_sqm(value):
    if value is None or (hasattr(value, '_undefined_name')):
        return "—"
    try:
        return f"{float(value):,.0f} m²"
    except (ValueError, TypeError):
        return "—"


def time_ago(value):
    if not value:
        return "—"
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00").replace("+00:00", ""))
        delta = datetime.utcnow() - dt
        if delta.days > 0:
            return f"{delta.days}d ago"
        hours = delta.seconds // 3600
        if hours > 0:
            return f"{hours}h ago"
        return f"{delta.seconds // 60}m ago"
    except (ValueError, TypeError):
        return str(value)[:10]


templates.env.filters["eur"] = format_eur
templates.env.filters["sqm"] = format_sqm
templates.env.filters["time_ago"] = time_ago


# --- Routes ---

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    store = get_store()
    collections = []
    total_props = 0

    for name in store.list_collections():
        if name.startswith("_"):
            continue
        coll = store.collection(name)
        docs = coll.find()
        n = len(docs)
        total_props += n
        prices = [d["current"].get("price_eur") for d in docs if d["current"].get("price_eur")]
        collections.append({
            "name": name,
            "count": n,
            "with_price": len(prices),
            "avg_price": sum(prices) / len(prices) if prices else 0,
            "with_images": sum(1 for d in docs if d["current"].get("image_urls")),
            "with_coords": sum(1 for d in docs if d["current"].get("lat")),
            "with_desc": sum(1 for d in docs if d["current"].get("description")),
        })

    # Scrape runs
    runs_coll = store.collection("_scrape_runs")
    runs = sorted(runs_coll.find(), key=lambda r: r.get("started_at", ""), reverse=True)[:10]

    return templates.TemplateResponse(request, "index.html", {"collections": collections,
        "total_props": total_props,
        "runs": runs,
    })


@app.get("/browse/{collection}", response_class=HTMLResponse)
async def browse(
    request: Request,
    collection: str,
    page: int = Query(1, ge=1),
    sort: str = Query("newest"),
    q: str = Query(""),
    prop_type: str = Query(""),
    listing_type: str = Query(""),
    min_price: str = Query(""),
    max_price: str = Query(""),
):
    store = get_store()
    coll = store.collection(collection)
    docs = coll.find()

    # Parse price filters (empty string = no filter)
    try:
        min_price_f = float(min_price) if min_price else 0
    except ValueError:
        min_price_f = 0
    try:
        max_price_f = float(max_price) if max_price else 0
    except ValueError:
        max_price_f = 0

    # Filter
    if q:
        q_lower = q.lower()
        docs = [d for d in docs if
                q_lower in (d["current"].get("title") or "").lower() or
                q_lower in (d["current"].get("locality") or "").lower() or
                q_lower in (d["current"].get("description") or "").lower() or
                q_lower in (d["current"].get("address_raw") or "").lower()]

    if prop_type:
        docs = [d for d in docs if d["current"].get("property_type") == prop_type]

    if listing_type:
        docs = [d for d in docs if d["current"].get("listing_type") == listing_type]

    if min_price_f > 0:
        docs = [d for d in docs if (d["current"].get("price_eur") or 0) >= min_price_f]

    if max_price_f > 0:
        docs = [d for d in docs if (d["current"].get("price_eur") or float("inf")) <= max_price_f]

    # Sort
    if sort == "price_asc":
        docs.sort(key=lambda d: d["current"].get("price_eur") or float("inf"))
    elif sort == "price_desc":
        docs.sort(key=lambda d: d["current"].get("price_eur") or 0, reverse=True)
    elif sort == "area_desc":
        docs.sort(key=lambda d: d["current"].get("area_sqm") or 0, reverse=True)
    else:  # newest
        docs.sort(key=lambda d: d.get("last_seen") or "", reverse=True)

    # Collect filter options from all docs
    all_docs = coll.find()
    prop_types = sorted(set(d["current"].get("property_type") for d in all_docs if d["current"].get("property_type")))
    listing_types = sorted(set(d["current"].get("listing_type") for d in all_docs if d["current"].get("listing_type")))

    # Paginate
    per_page = 24
    total = len(docs)
    total_pages = max(1, math.ceil(total / per_page))
    page = min(page, total_pages)
    start = (page - 1) * per_page
    page_docs = docs[start:start + per_page]

    return templates.TemplateResponse(request, "browse.html", {"collection": collection,
        "docs": page_docs,
        "page": page,
        "total_pages": total_pages,
        "total": total,
        "sort": sort,
        "q": q,
        "prop_type": prop_type,
        "prop_types": prop_types,
        "listing_type": listing_type,
        "listing_types": listing_types,
        "min_price": min_price_f,
        "max_price": max_price_f,
    })


@app.get("/property/{collection}/{ext_id:path}", response_class=HTMLResponse)
async def property_detail(request: Request, collection: str, ext_id: str):
    store = get_store()
    coll = store.collection(collection)
    doc_id = f"{collection}:{ext_id}"
    doc = coll.get(doc_id)
    if not doc:
        return HTMLResponse(f"<h1>Not found: {doc_id}</h1>", status_code=404)

    # Check which local images actually exist
    local_images = []
    for path in (doc["current"].get("image_local_paths") or []):
        if os.path.exists(path):
            local_images.append(path)

    return templates.TemplateResponse(request, "property.html", {"doc": doc,
        "collection": collection,
        "ext_id": ext_id,
        "local_images": local_images,
        "current": doc.get("current", {}),
        "history": doc.get("history", []),
    })


@app.get("/image/{path:path}")
async def serve_image(path: str):
    """Serve a local image file."""
    # Path comes without leading /, add it back for absolute paths
    if not path.startswith("/"):
        # Check if it looks like an absolute path missing the /
        if path.startswith("home/") or path.startswith("data/"):
            path = "/" + path
        else:
            path = str(IMAGE_DIR / path)

    if os.path.exists(path):
        return FileResponse(path)
    return HTMLResponse(f"Image not found: {path}", status_code=404)


@app.get("/search", response_class=HTMLResponse)
async def search(
    request: Request,
    q: str = Query(""),
    country: str = Query(""),
):
    if not q:
        return templates.TemplateResponse(request, "search.html", {"q": "", "results": [], "country": "",
        })

    store = get_store()
    results = []
    q_lower = q.lower()

    for name in store.list_collections():
        if name.startswith("_"):
            continue
        coll = store.collection(name)
        for doc in coll.find():
            if country and doc.get("country") != country.upper():
                continue
            cur = doc["current"]
            searchable = " ".join(str(v) for v in [
                cur.get("title"), cur.get("locality"), cur.get("description"),
                cur.get("address_raw"), cur.get("property_type"),
            ] if v).lower()

            if q_lower in searchable:
                results.append({"doc": doc, "collection": name})

    # Sort by price descending
    results.sort(key=lambda r: r["doc"]["current"].get("price_eur") or 0, reverse=True)

    return templates.TemplateResponse(request, "search.html", {"q": q,
        "country": country,
        "results": results[:100],
        "total": len(results),
    })


@app.get("/stats", response_class=HTMLResponse)
async def stats(request: Request):
    store = get_store()
    by_locality = {}
    by_type = {}
    by_country = {}
    history_events = {}

    for name in store.list_collections():
        if name.startswith("_"):
            continue
        coll = store.collection(name)
        for doc in coll.find():
            cur = doc["current"]
            price = cur.get("price_eur")
            loc = cur.get("locality") or "Unknown"
            ptype = cur.get("property_type") or "unknown"
            country = doc.get("country") or "?"

            if price and price > 0:
                by_locality.setdefault(loc, []).append(price)
                by_type.setdefault(ptype, []).append(price)
                by_country.setdefault(country, []).append(price)

            for h in doc.get("history", []):
                evt = h.get("event", "unknown")
                history_events[evt] = history_events.get(evt, 0) + 1

    def summarize(groups):
        return sorted([
            {"name": k, "count": len(v), "avg": sum(v)/len(v), "min": min(v), "max": max(v)}
            for k, v in groups.items()
        ], key=lambda x: -x["count"])

    return templates.TemplateResponse(request, "stats.html", {"by_locality": summarize(by_locality)[:30],
        "by_type": summarize(by_type),
        "by_country": summarize(by_country),
        "history_events": sorted(history_events.items(), key=lambda x: -x[1]),
    })


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("dashboard.app:app", host="0.0.0.0", port=8500, reload=True)
