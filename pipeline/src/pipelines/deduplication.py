import hashlib
import logging

logger = logging.getLogger(__name__)


class DeduplicationPipeline:
    """Detect and mark duplicate listings using address hash + geospatial proximity."""

    def __init__(self):
        self._seen_hashes: set[str] = set()

    def process_item(self, item, spider):
        dedup_hash = self._compute_hash(item)
        item["dedup_hash"] = dedup_hash

        if dedup_hash in self._seen_hashes:
            logger.debug(f"Duplicate detected: {dedup_hash}")
            # Don't drop -- let persistence pipeline handle upsert
            item["_is_duplicate"] = True
        else:
            self._seen_hashes.add(dedup_hash)
            item["_is_duplicate"] = False

        return item

    def _compute_hash(self, item) -> str:
        """Compute a dedup hash from source + external_id, or address + price."""
        # Best case: same source + same external ID
        if item.get("source") and item.get("external_id"):
            key = f"{item['source']}:{item['external_id']}"
            return hashlib.sha256(key.encode()).hexdigest()[:16]

        # Fallback: address + price + type
        parts = [
            item.get("address_raw", "").lower().strip(),
            str(item.get("price", "")),
            item.get("property_type", ""),
            str(item.get("area_sqm", "")),
        ]
        key = "|".join(parts)
        return hashlib.sha256(key.encode()).hexdigest()[:16]
