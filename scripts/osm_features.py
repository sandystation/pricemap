"""
OpenStreetMap POI distance features for property valuation.

Downloads POI data from the Overpass API for Malta, caches locally,
and provides fast nearest-neighbor distance computation via KD-tree.

Usage:
    from osm_features import compute_osm_features
    features = compute_osm_features(lat=35.9116, lon=14.5027)
    # {'dist_school_km': 0.23, 'dist_bus_km': 0.08, ..., 'poi_500m': 42}
"""

import json
import logging
import math
import os
from pathlib import Path

import httpx
import numpy as np
from scipy.spatial import KDTree

logger = logging.getLogger(__name__)

CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "osm_cache")
OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# Malta bounding box (covers Malta, Gozo, Comino)
MALTA_BBOX = "35.78,14.18,36.09,14.58"

# POI categories to query: (tag_key, tag_value, cache_name)
POI_CATEGORIES = [
    ("amenity", "school", "schools"),
    ("public_transport", "platform", "bus_stops"),
    ("shop", "supermarket", "supermarkets"),
    ("amenity", "restaurant", "restaurants"),
    ("amenity", "cafe", "cafes"),
    ("amenity", "hospital", "hospitals"),
    ("amenity", "clinic", "clinics"),
    ("amenity", "pharmacy", "pharmacies"),
    ("leisure", "park", "parks"),
    ("amenity", "place_of_worship", "worship"),
]

# Approximate conversion at Malta latitude (35.9°N)
# 1 degree lat ≈ 111.0 km, 1 degree lon ≈ cos(35.9°) * 111.0 ≈ 89.8 km
DEG_TO_KM_LAT = 111.0
DEG_TO_KM_LON = 89.8
RADIUS_500M_DEG = 0.005  # ~500m in degrees (approximate)


def _overpass_query(tag_key: str, tag_value: str) -> list[tuple[float, float]]:
    """Query Overpass API for nodes/ways with given tag in Malta."""
    query = f"""
    [out:json][timeout:120];
    (
      node["{tag_key}"="{tag_value}"]({MALTA_BBOX});
      way["{tag_key}"="{tag_value}"]({MALTA_BBOX});
    );
    out center;
    """
    import time
    for attempt in range(3):
        try:
            resp = httpx.post(OVERPASS_URL, data={"data": query}, timeout=120)
            resp.raise_for_status()
            data = resp.json()
            break
        except Exception as e:
            if attempt < 2:
                wait = 10 * (attempt + 1)
                logger.warning(f"Overpass query failed ({e}), retrying in {wait}s...")
                time.sleep(wait)
            else:
                logger.error(f"Overpass query failed after 3 attempts: {e}")
                return []

    coords = []
    for el in data.get("elements", []):
        if el["type"] == "node":
            coords.append((el["lat"], el["lon"]))
        elif el["type"] == "way" and "center" in el:
            coords.append((el["center"]["lat"], el["center"]["lon"]))
    return coords


def _load_or_download(name: str, tag_key: str, tag_value: str) -> list[tuple[float, float]]:
    """Load POI coords from cache or download from Overpass."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    cache_path = os.path.join(CACHE_DIR, f"{name}.json")

    if os.path.exists(cache_path):
        with open(cache_path) as f:
            return [tuple(c) for c in json.load(f)]

    logger.info(f"Downloading OSM {name} ({tag_key}={tag_value}) for Malta...")
    coords = _overpass_query(tag_key, tag_value)
    with open(cache_path, "w") as f:
        json.dump(coords, f)
    logger.info(f"  {name}: {len(coords)} POIs cached")
    return coords


class OSMFeatureComputer:
    """Preloads POI data and builds KD-trees for fast distance queries."""

    def __init__(self):
        self._trees: dict[str, KDTree] = {}
        self._coords: dict[str, np.ndarray] = {}
        self._all_pois: np.ndarray | None = None
        self._all_restaurants_cafes: np.ndarray | None = None
        self._loaded = False

    def load(self):
        """Download/load all POI categories and build KD-trees."""
        if self._loaded:
            return

        all_poi_coords = []
        restaurant_cafe_coords = []

        for tag_key, tag_value, name in POI_CATEGORIES:
            coords = _load_or_download(name, tag_key, tag_value)
            if coords:
                arr = np.array(coords)
                self._coords[name] = arr
                self._trees[name] = KDTree(arr)
                all_poi_coords.extend(coords)
                if name in ("restaurants", "cafes"):
                    restaurant_cafe_coords.extend(coords)

        if all_poi_coords:
            self._all_pois = np.array(all_poi_coords)
        if restaurant_cafe_coords:
            self._all_restaurants_cafes = np.array(restaurant_cafe_coords)

        self._loaded = True
        total = sum(len(c) for c in self._coords.values())
        logger.info(f"OSM features loaded: {total} POIs across {len(self._coords)} categories")

    def compute(self, lat: float, lon: float) -> dict:
        """Compute all OSM distance features for a point."""
        self.load()
        point = np.array([[lat, lon]])
        result = {}

        # Distance to nearest POI of each type
        distance_features = {
            "dist_school_km": ["schools"],
            "dist_bus_km": ["bus_stops"],
            "dist_supermarket_km": ["supermarkets"],
            "dist_restaurant_km": ["restaurants", "cafes"],
            "dist_hospital_km": ["hospitals", "clinics"],
            "dist_pharmacy_km": ["pharmacies"],
            "dist_park_km": ["parks"],
            "dist_worship_km": ["worship"],
        }

        for feat_name, categories in distance_features.items():
            min_dist = float("inf")
            for cat in categories:
                if cat in self._trees:
                    deg_dist, _ = self._trees[cat].query(point)
                    km_dist = self._deg_to_km(deg_dist[0], lat)
                    min_dist = min(min_dist, km_dist)
            result[feat_name] = round(min_dist, 3) if min_dist < float("inf") else np.nan

        # Density features: count within 500m
        if self._all_pois is not None:
            count = self._trees_count_within(self._all_pois, lat, lon, RADIUS_500M_DEG)
            result["poi_count_500m"] = count

        if self._all_restaurants_cafes is not None:
            count = self._trees_count_within(self._all_restaurants_cafes, lat, lon, RADIUS_500M_DEG)
            result["dining_count_500m"] = count

        return result

    @staticmethod
    def _deg_to_km(deg_dist: float, lat: float) -> float:
        """Convert approximate degree distance to km at given latitude."""
        # Average of lat and lon scales at this latitude
        avg_scale = (DEG_TO_KM_LAT + DEG_TO_KM_LON) / 2
        return deg_dist * avg_scale

    @staticmethod
    def _trees_count_within(coords: np.ndarray, lat: float, lon: float, radius_deg: float) -> int:
        """Count points within radius_deg of (lat, lon)."""
        dlat = coords[:, 0] - lat
        dlon = coords[:, 1] - lon
        dist_sq = dlat ** 2 + dlon ** 2
        return int(np.sum(dist_sq <= radius_deg ** 2))


# Module-level singleton
_computer = None


def compute_osm_features(lat: float, lon: float) -> dict:
    """Compute OSM distance and density features for a property location."""
    global _computer
    if _computer is None:
        _computer = OSMFeatureComputer()
    return _computer.compute(lat, lon)


# Feature names exported for train_valuation.py
OSM_DISTANCE_FEATURES = [
    "dist_school_km", "dist_bus_km", "dist_supermarket_km",
    "dist_restaurant_km", "dist_hospital_km", "dist_pharmacy_km",
    "dist_park_km", "dist_worship_km",
]
OSM_DENSITY_FEATURES = ["poi_count_500m", "dining_count_500m"]
OSM_ALL_FEATURES = OSM_DISTANCE_FEATURES + OSM_DENSITY_FEATURES
