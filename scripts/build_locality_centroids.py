"""Build per-locality geographic centroids for serve-time locality resolution.

The valuation encoders key locality by anglicized RE/MAX names (Sliema,
"Gozo - Victoria"). At serve time the geocoder returns Maltese endonyms
(Tas-Sliema, Ix-Xaghra) that don't match, so locality_enc drops to NaN. A
nearest-centroid fallback on lat/lon always yields a sensible locality.

Outputs backend/src/ml/mt_locality_centroids.json: {locality_key: [lat, lon]}
for every locality the sale/rent encoders know, using the median coordinate of
that locality's training listings (same map_lat/lon preference as training).
"""
import json
import os
from collections import defaultdict
from statistics import median

import joblib

from docstore import DocStore

ART = os.path.join(os.path.dirname(os.path.dirname(__file__)), "ml", "artifacts")
OUT = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "backend", "src", "ml", "mt_locality_centroids.json",
)


def encoder_localities() -> set[str]:
    keys: set[str] = set()
    for lt in ("sale", "rent"):
        enc = joblib.load(os.path.join(ART, f"mt_apartment_{lt}_encoders_v20260703.joblib"))
        keys.update(enc["locality"].keys())
    return keys


def main():
    keys = encoder_localities()
    coords: dict[str, list] = defaultdict(list)
    store = DocStore()
    coll = store.collection("mt_remax")
    for doc in coll.find():
        cur = doc.get("current", {})
        loc = cur.get("locality")
        if not loc:
            continue
        lat = cur.get("map_lat") or cur.get("lat")
        lon = cur.get("map_lon") or cur.get("lon")
        if lat and lon:
            coords[loc].append((float(lat), float(lon)))
    store.close()

    centroids = {}
    for loc in sorted(keys):
        pts = coords.get(loc)
        if pts:
            centroids[loc] = [
                round(median(p[0] for p in pts), 6),
                round(median(p[1] for p in pts), 6),
            ]
    missing = sorted(k for k in keys if k not in centroids)

    with open(OUT, "w") as f:
        json.dump(centroids, f, indent=2, sort_keys=True)
        f.write("\n")

    print(f"Wrote {len(centroids)} locality centroids to {OUT}")
    n_gozo = sum(1 for c in centroids.values() if c[0] > 36.0)
    print(f"  Gozo centroids (lat>36.0): {n_gozo}")
    if missing:
        print(f"  WARNING: {len(missing)} encoder localities had no coords: {missing}")


if __name__ == "__main__":
    main()
