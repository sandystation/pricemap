import json
import math
from pathlib import Path

import numpy as np

OSM_DISTANCE_FEATURES = [
    "dist_school_km",
    "dist_bus_km",
    "dist_supermarket_km",
    "dist_restaurant_km",
    "dist_hospital_km",
    "dist_pharmacy_km",
    "dist_park_km",
    "dist_worship_km",
    "dist_beach_km",
    "dist_marina_km",
    "dist_airport_km",
    "dist_kindergarten_km",
    "dist_university_km",
]
OSM_KEY_LOCATION_FEATURES = [
    "dist_burgas_km",
    "dist_plovdiv_km",
    "dist_sea_km",
    "dist_sliema_km",
    "dist_sofia_km",
    "dist_stjulians_km",
    "dist_varna_km",
]
OSM_DENSITY_FEATURES = ["poi_count_500m", "dining_count_500m"]
OSM_ALL_FEATURES = OSM_DISTANCE_FEATURES + OSM_KEY_LOCATION_FEATURES + OSM_DENSITY_FEATURES

VALLETTA_LAT, VALLETTA_LON = 35.8989, 14.5146
KEY_LOCATIONS = {
    "sliema": (35.9116, 14.5027),
    "stjulians": (35.9186, 14.4903),
}

POI_FEATURE_MAP = {
    "dist_school_km": ["schools"],
    "dist_bus_km": ["bus_stops"],
    "dist_supermarket_km": ["supermarkets"],
    "dist_restaurant_km": ["restaurants", "cafes"],
    "dist_hospital_km": ["hospitals", "clinics"],
    "dist_pharmacy_km": ["pharmacies"],
    "dist_park_km": ["parks"],
    "dist_worship_km": ["worship"],
    "dist_beach_km": ["beaches"],
    "dist_marina_km": ["marinas"],
    "dist_airport_km": ["airports"],
    "dist_kindergarten_km": ["kindergartens"],
    "dist_university_km": ["universities"],
}


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    return radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def compute_distances(lat: float, lon: float) -> dict[str, float]:
    # Approximate coast distance using Malta/Gozo coastline point samples from training.
    coast_points = [
        (35.8989, 14.5146),
        (35.9025, 14.5366),
        (35.8236, 14.5621),
        (35.8100, 14.5435),
        (35.8050, 14.5200),
        (35.8190, 14.4700),
        (35.8350, 14.4200),
        (35.8600, 14.3500),
        (35.8850, 14.3340),
        (35.9300, 14.3600),
        (35.9530, 14.4200),
        (35.9590, 14.4800),
        (36.0300, 14.2100),
        (36.0550, 14.2600),
        (36.0570, 14.2900),
        (36.0350, 14.3200),
        (36.0150, 14.2500),
    ]
    coast_km = min(haversine_km(lat, lon, clat, clon) for clat, clon in coast_points)
    return {
        "dist_coast_km": round(coast_km, 3),
        "dist_cbd_km": round(haversine_km(lat, lon, VALLETTA_LAT, VALLETTA_LON), 3),
    }


def _cache_dirs() -> list[Path]:
    here = Path(__file__).resolve()
    return [
        Path("/app/data/osm_cache"),
        here.parents[3] / "data" / "osm_cache",
        Path.cwd() / "data" / "osm_cache",
    ]


def _load_poi(name: str) -> list[tuple[float, float]]:
    for directory in _cache_dirs():
        path = directory / f"{name}.json"
        if path.exists():
            data = json.loads(path.read_text())
            return [(float(lat), float(lon)) for lat, lon in data]
    return []


def _nearest_km(lat: float, lon: float, names: list[str]) -> float:
    best = math.inf
    for name in names:
        for poi_lat, poi_lon in _load_poi(name):
            best = min(best, haversine_km(lat, lon, poi_lat, poi_lon))
    return round(best, 3) if best < math.inf else np.nan


def _count_within(lat: float, lon: float, names: list[str], radius_km: float = 0.5) -> float:
    count = 0
    for name in names:
        for poi_lat, poi_lon in _load_poi(name):
            if haversine_km(lat, lon, poi_lat, poi_lon) <= radius_km:
                count += 1
    return float(count)


def compute_location_features(lat: float, lon: float) -> dict[str, float]:
    features = {name: np.nan for name in OSM_ALL_FEATURES}
    features.update(compute_distances(lat, lon))

    for feature_name, poi_names in POI_FEATURE_MAP.items():
        features[feature_name] = _nearest_km(lat, lon, poi_names)

    features["poi_count_500m"] = _count_within(
        lat,
        lon,
        [
            "schools",
            "bus_stops",
            "supermarkets",
            "restaurants",
            "cafes",
            "hospitals",
            "clinics",
            "pharmacies",
            "parks",
            "worship",
            "beaches",
            "marinas",
            "airports",
            "kindergartens",
            "universities",
        ],
    )
    features["dining_count_500m"] = _count_within(lat, lon, ["restaurants", "cafes"])

    for key, (key_lat, key_lon) in KEY_LOCATIONS.items():
        features[f"dist_{key}_km"] = round(haversine_km(lat, lon, key_lat, key_lon), 3)

    return features
