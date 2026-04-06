"""
File-based document store for PriceMap.

Each collection is a JSONL file (one JSON document per line).
Documents are loaded into memory for fast lookups, flushed to disk atomically.
History tracking is built in: save_property() diffs tracked fields and appends
change events to the document's history array.

Usage:
    store = DocStore()
    coll = store.collection("mt_remax")
    doc_id, is_new = coll.save_property({"source": "mt_remax", "external_id": "123", ...})
    coll.close()
"""

import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import orjson

logger = logging.getLogger(__name__)

DEFAULT_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "collections")

# Fields that trigger a history event when they change
TRACKED_FIELDS = {
    "price_eur", "price_per_sqm", "price_adjusted_eur",
    "area_sqm", "bedrooms", "bathrooms", "rooms",
    "property_type", "locality", "title", "description",
    "condition", "is_active", "price_original", "price_currency",
    "address_raw", "floor", "total_floors",
}

# Fields excluded from current (metadata only)
META_FIELDS = {"source", "country_code", "external_id", "dedup_hash"}

# Auto-flush interval
FLUSH_EVERY = 100


class DocStore:
    """Entry point. Manages a directory of JSONL collections."""

    def __init__(self, data_dir: str = None):
        self.data_dir = Path(data_dir or DEFAULT_DATA_DIR)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._collections: dict[str, "Collection"] = {}

    def collection(self, name: str) -> "Collection":
        if name not in self._collections:
            path = self.data_dir / f"{name}.jsonl"
            self._collections[name] = Collection(name, path)
        return self._collections[name]

    def list_collections(self) -> list[str]:
        names = set(self._collections.keys())
        for f in self.data_dir.glob("*.jsonl"):
            name = f.stem
            if not name.startswith("_"):
                names.add(name)
        return sorted(names)

    def close(self):
        for coll in self._collections.values():
            coll.close()
        self._collections.clear()


class Collection:
    """In-memory collection backed by a JSONL file."""

    def __init__(self, name: str, path: Path):
        self.name = name
        self.path = path
        self._docs: dict[str, dict] | None = None  # lazy loaded
        self._dirty = False
        self._ops_since_flush = 0

    # --- Core CRUD ---

    def get(self, doc_id: str) -> dict | None:
        self._ensure_loaded()
        return self._docs.get(doc_id)

    def put(self, doc: dict) -> None:
        self._ensure_loaded()
        doc_id = doc.get("_id")
        if not doc_id:
            raise ValueError("Document must have an '_id' field")
        self._docs[doc_id] = doc
        self._mark_dirty()

    def delete(self, doc_id: str) -> bool:
        self._ensure_loaded()
        if doc_id in self._docs:
            del self._docs[doc_id]
            self._mark_dirty()
            return True
        return False

    def save_property(self, data: dict) -> tuple[str, bool]:
        """
        Main scraper entry point. Diffs incoming data against existing doc,
        tracks changes in history, returns (doc_id, is_new).
        """
        self._ensure_loaded()
        now = datetime.now(timezone.utc).isoformat()

        source = data.get("source", "")
        external_id = data.get("external_id", "")
        doc_id = f"{source}:{external_id}"
        country = data.pop("country_code", None) or data.pop("country", None)

        # Build the "current" fields dict (everything except meta)
        current_data = {}
        for k, v in data.items():
            if k not in META_FIELDS and v is not None:
                current_data[k] = v
        current_data["scraped_at"] = now

        existing = self._docs.get(doc_id)

        if existing:
            # Diff tracked fields
            changes = _diff_fields(existing.get("current", {}), current_data)

            # Always update last_seen and scraped_at
            existing["last_seen"] = now
            existing["current"]["scraped_at"] = now

            if changes:
                # Record history event
                event = _build_event(now, changes)
                existing.setdefault("history", []).append(event)
                logger.debug(f"Updated {doc_id}: {event['event']} ({len(changes)} fields)")

            # Always update current with all non-None incoming data
            # (fills in new fields, updates non-tracked fields, applies tracked changes)
            for k, v in current_data.items():
                if v is not None:
                    existing["current"][k] = v

            self._docs[doc_id] = existing
            self._mark_dirty()
            return doc_id, False
        else:
            # New document
            doc = {
                "_id": doc_id,
                "source": source,
                "country": country or _country_from_source(source),
                "first_seen": now,
                "last_seen": now,
                "current": current_data,
                "history": [{"date": now, "event": "created"}],
            }
            self._docs[doc_id] = doc
            self._mark_dirty()
            return doc_id, True

    def is_stale(self, doc_id: str, hours: int = 20) -> bool:
        """Check if a document hasn't been seen for more than `hours` hours."""
        doc = self.get(doc_id)
        if not doc:
            return True
        last = doc.get("last_seen")
        if not last:
            return True
        try:
            last_dt = datetime.fromisoformat(last)
            if last_dt.tzinfo is None:
                last_dt = last_dt.replace(tzinfo=timezone.utc)
            return datetime.now(timezone.utc) - last_dt > timedelta(hours=hours)
        except (ValueError, TypeError):
            return True

    # --- Query ---

    def find(self, predicate=None) -> list[dict]:
        self._ensure_loaded()
        if predicate is None:
            return list(self._docs.values())
        return [doc for doc in self._docs.values() if predicate(doc)]

    def count(self) -> int:
        self._ensure_loaded()
        return len(self._docs)

    # --- Persistence ---

    def flush(self) -> None:
        if not self._dirty or self._docs is None:
            return
        tmp_path = self.path.with_suffix(".jsonl.tmp")
        with open(tmp_path, "wb") as f:
            for doc in self._docs.values():
                f.write(orjson.dumps(doc, option=orjson.OPT_APPEND_NEWLINE))
        os.replace(tmp_path, self.path)
        self._dirty = False
        self._ops_since_flush = 0
        logger.debug(f"Flushed {self.name}: {len(self._docs)} docs")

    def close(self) -> None:
        self.flush()
        self._docs = None

    # --- Internals ---

    def _ensure_loaded(self):
        if self._docs is not None:
            return
        self._docs = {}
        if self.path.exists():
            with open(self.path, "rb") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        doc = orjson.loads(line)
                        doc_id = doc.get("_id")
                        if doc_id:
                            self._docs[doc_id] = doc
                    except orjson.JSONDecodeError:
                        logger.warning(f"Skipping malformed line in {self.path}")
            logger.info(f"Loaded {self.name}: {len(self._docs)} docs from {self.path}")
        else:
            logger.info(f"New collection: {self.name}")

    def _mark_dirty(self):
        self._dirty = True
        self._ops_since_flush += 1
        if self._ops_since_flush >= FLUSH_EVERY:
            self.flush()


# --- Helpers ---

def _diff_fields(old: dict, new: dict) -> dict:
    """Compare tracked fields. Returns {field: {"old": v1, "new": v2}} for changed fields."""
    changes = {}
    for field in TRACKED_FIELDS:
        old_val = old.get(field)
        new_val = new.get(field)

        # Skip if new value not provided
        if new_val is None:
            continue

        # Normalize for comparison
        if isinstance(old_val, str) and isinstance(new_val, str):
            if old_val.strip() == new_val.strip():
                continue
        elif isinstance(old_val, (int, float)) and isinstance(new_val, (int, float)):
            if abs(float(old_val) - float(new_val)) < 0.01:
                continue
        elif old_val == new_val:
            continue

        # None → value is not a "change" for most fields (it's initial population)
        # But price changes from None are worth tracking
        if old_val is None and field not in ("price_eur", "is_active"):
            continue

        changes[field] = {"old": old_val, "new": new_val}

    return changes


def _build_event(date: str, changes: dict) -> dict:
    """Build a history event from a set of changes."""
    if "is_active" in changes and changes["is_active"]["new"] == 0:
        event_type = "deactivated"
    elif "is_active" in changes and changes["is_active"]["new"] == 1:
        event_type = "reactivated"
    elif "price_eur" in changes and len(changes) == 1:
        event_type = "price_change"
    elif "price_eur" in changes:
        event_type = "price_and_content_change"
    elif len(changes) > 1:
        event_type = "multi_change"
    else:
        event_type = "content_change"

    return {
        "date": date,
        "event": event_type,
        "changes": changes,
    }


def _country_from_source(source: str) -> str:
    """Infer country code from source name."""
    if source.startswith("mt_"):
        return "MT"
    elif source.startswith("bg_"):
        return "BG"
    elif source.startswith("cy_"):
        return "CY"
    elif source.startswith("hr_"):
        return "HR"
    return ""


# --- Scrape run helpers ---

def start_scrape_run(store: DocStore, spider_name: str, country_code: str) -> str:
    """Record a scrape run start. Returns run_id."""
    coll = store.collection("_scrape_runs")
    now = datetime.now(timezone.utc).isoformat()
    run_id = f"{spider_name}:{now}"
    coll.put({
        "_id": run_id,
        "spider_name": spider_name,
        "country_code": country_code,
        "started_at": now,
        "finished_at": None,
        "items_scraped": 0,
        "items_new": 0,
        "items_updated": 0,
        "errors_count": 0,
        "status": "running",
    })
    coll.flush()
    return run_id


def update_scrape_run(store: DocStore, run_id: str, **kwargs):
    """Incrementally update a scrape run (e.g. items_scraped, errors_count)."""
    coll = store.collection("_scrape_runs")
    doc = coll.get(run_id)
    if doc:
        doc.update(kwargs)
        coll.put(doc)


def finish_scrape_run(store: DocStore, run_id: str, items_scraped: int,
                      items_new: int, errors_count: int, items_updated: int = 0):
    """Finalize a scrape run."""
    coll = store.collection("_scrape_runs")
    doc = coll.get(run_id)
    if doc:
        doc.update({
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "items_scraped": items_scraped,
            "items_new": items_new,
            "items_updated": items_updated,
            "errors_count": errors_count,
            "status": "finished",
        })
        coll.put(doc)
    coll.flush()
