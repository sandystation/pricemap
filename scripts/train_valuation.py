"""
Train apartment valuation models for Malta using RE/MAX DocStore data.

Usage (run from scripts/ directory):
    python train_valuation.py --listing-type sale
    python train_valuation.py --listing-type rent
    python train_valuation.py --listing-type sale --dry-run
    python train_valuation.py --listing-type sale --property-type penthouse
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone

import joblib
import lightgbm as lgb
import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from docstore import DocStore
from osm_features import compute_osm_features, OSM_ALL_FEATURES

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ARTIFACTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "ml", "artifacts")

# ---------------------------------------------------------------------------
# Hyperparameters (from ml/src/config.py)
# ---------------------------------------------------------------------------
LGBM_PARAMS = {
    "objective": "regression",
    "metric": "mae",
    "boosting_type": "gbdt",
    "num_leaves": 63,
    "learning_rate": 0.05,
    "feature_fraction": 0.8,
    "bagging_fraction": 0.8,
    "bagging_freq": 5,
    "verbose": -1,
    "n_estimators": 500,
    "early_stopping_rounds": 50,
}

XGB_PARAMS = {
    "objective": "reg:squarederror",
    "max_depth": 6,
    "learning_rate": 0.05,
    "n_estimators": 500,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "early_stopping_rounds": 50,
}

LGBM_WEIGHT = 0.7
XGB_WEIGHT = 0.3
N_FOLDS = 5

# ---------------------------------------------------------------------------
# Outlier bounds per (property_type, listing_type)
# ---------------------------------------------------------------------------
MODEL_CONFIGS = {
    ("apartment", "sale"): {
        "min_price": 50_000,
        "max_price": 5_000_000,
        "min_area": 15,
        "max_area": 500,
        "require_area": True,
    },
    ("apartment", "rent"): {
        "min_price": 300,
        "max_price": 10_000,
        "min_area": 15,
        "max_area": 500,
        "require_area": False,
    },
    ("penthouse", "sale"): {
        "min_price": 100_000,
        "max_price": 10_000_000,
        "min_area": 30,
        "max_area": 800,
        "require_area": True,
    },
    ("penthouse", "rent"): {
        "min_price": 500,
        "max_price": 20_000,
        "min_area": 30,
        "max_area": 800,
        "require_area": False,
    },
}

# ---------------------------------------------------------------------------
# Amenity extraction from features list
# ---------------------------------------------------------------------------
AMENITY_KEYWORDS = {
    "has_balcony": ["Balcony"],
    "has_ac": ["A/C"],
    "has_ensuite": ["En Suite"],
    "has_lift": ["Lift", "Passenger Lift"],
    "has_double_glazed": ["Double Glazed"],
    "has_terrace": ["Terrace", "Roof Terrace"],
    "has_pool": ["Pool", "Communal Pool", "Pool Deck"],
    "has_ceramic_floor": ["Ceramic Floor"],
    "has_backyard": ["Back Yard"],
    "has_yard": ["Yard", "Court Yard"],
    "has_marble_floor": ["Marble Floor"],
    "has_walk_in_wardrobe": ["Walk in Wardrobe"],
    "has_alarm": ["Alarm System"],
    "has_video_intercom": ["Video Intercom", "Video Hall Porter"],
}

# Feature columns in the final matrix (excluding target-encoded categoricals
# which are added dynamically)
NUMERIC_FEATURES = [
    "lat", "lon", "area_sqm", "bedrooms", "bathrooms", "rooms",
    "total_int_area", "total_ext_area",
    "dist_coast_km", "dist_cbd_km",
] + OSM_ALL_FEATURES

# ---------------------------------------------------------------------------
# Distance features
# ---------------------------------------------------------------------------
import math

# Valletta CBD coordinates
VALLETTA_LAT, VALLETTA_LON = 35.8989, 14.5146

# Simplified Malta coastline polygon (main island + Gozo key points)
# Used to compute distance to nearest coast. Points are (lon, lat).
_MALTA_COAST_COORDS = [
    # Malta main island (clockwise from Valletta)
    (14.5146, 35.8989), (14.5366, 35.9025), (14.5621, 35.8236),
    (14.5435, 35.8100), (14.5200, 35.8050), (14.4700, 35.8190),
    (14.4200, 35.8350), (14.3500, 35.8600), (14.3340, 35.8850),
    (14.3430, 35.9100), (14.3600, 35.9300), (14.3850, 35.9420),
    (14.4200, 35.9530), (14.4500, 35.9580), (14.4800, 35.9590),
    (14.5080, 35.9550), (14.5146, 35.8989),
    # Gozo (separate ring, simplified)
]

_GOZO_COAST_COORDS = [
    (14.2100, 36.0300), (14.2600, 36.0550), (14.2900, 36.0570),
    (14.3100, 36.0500), (14.3200, 36.0350), (14.3000, 36.0200),
    (14.2500, 36.0150), (14.2100, 36.0300),
]


def _build_coast_boundary():
    """Build a shapely geometry of Malta's coastline for distance queries."""
    from shapely.geometry import Polygon, MultiPolygon
    malta = Polygon(_MALTA_COAST_COORDS)
    gozo = Polygon(_GOZO_COAST_COORDS)
    return MultiPolygon([malta, gozo]).boundary


_coast_boundary = None


def _haversine_km(lat1, lon1, lat2, lon2):
    """Haversine distance in kilometers."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def compute_distances(lat: float, lon: float) -> dict:
    """Compute distance to coast and CBD in km."""
    global _coast_boundary
    if _coast_boundary is None:
        _coast_boundary = _build_coast_boundary()

    from shapely.geometry import Point
    # Distance to coast: use shapely (degrees) then convert roughly to km
    # At Malta's latitude, 1 degree lat ≈ 111 km, 1 degree lon ≈ 90 km
    pt = Point(lon, lat)
    coast_deg = _coast_boundary.distance(pt)
    # Approximate conversion using average scale at Malta latitude
    coast_km = coast_deg * 100.0  # rough: avg of 111 and 90

    cbd_km = _haversine_km(lat, lon, VALLETTA_LAT, VALLETTA_LON)

    return {"dist_coast_km": round(coast_km, 3), "dist_cbd_km": round(cbd_km, 3)}

AMENITY_FEATURES = list(AMENITY_KEYWORDS.keys()) + [
    "is_premium_zone", "is_gozo", "is_resort",
    "is_near_beach", "is_seafront", "is_sea_view", "is_quiet_road",
    "is_city_center", "is_countryside",
]

CATEGORICAL_FEATURES = ["locality_enc", "province_enc"]

# ---------------------------------------------------------------------------
# Structured source-specific features
# ---------------------------------------------------------------------------
# bg_imot has floor, total_floors, construction_type in structured data
# These override LLM-extracted values when available (more reliable)
CONSTRUCTION_TYPE_MAP = {"panel": 1, "epk": 2, "brick": 3}

# Resort/seasonal neighborhoods (rent is seasonal, not year-round)
_RESORT_KEYWORDS = ["к.к.", "Златни пясъци", "Слънчев бряг", "Слънчев ден",
                    "Ален мак", "Св.Св. Константин", "Елените", "Приморско"]

# Bulgarian month names for date parsing
_BG_MONTHS = {
    "януари": 1, "февруари": 2, "март": 3, "април": 4,
    "май": 5, "юни": 6, "юли": 7, "август": 8,
    "септември": 9, "октомври": 10, "ноември": 11, "декември": 12,
}


def _parse_listing_date(date_str: str):
    """Parse listing date from ISO or Bulgarian format. Returns datetime or None."""
    from datetime import datetime, timezone
    import re

    if not date_str:
        return None

    # ISO format: 2026-02-16T10:34:49.443
    if date_str[:4].isdigit() and "-" in date_str[:5]:
        try:
            return datetime.fromisoformat(date_str.replace("Z", "+00:00")).replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            pass

    # Bulgarian format: "5 април, 2026"
    match = re.match(r"(\d{1,2})\s+(\w+),?\s*(\d{4})", date_str)
    if match:
        day, month_bg, year = match.groups()
        month_num = _BG_MONTHS.get(month_bg.lower())
        if month_num:
            try:
                return datetime(int(year), month_num, int(day), tzinfo=timezone.utc)
            except ValueError:
                pass

    return None


# Load city/town populations for population-based features
_POP_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "osm_cache", "city_populations.json")
_CITY_POPULATIONS: dict[str, int] = {}
if os.path.exists(_POP_PATH):
    with open(_POP_PATH) as _f:
        for _country_pops in json.load(_f).values():
            _CITY_POPULATIONS.update(_country_pops)


def _get_population(cur: dict) -> float | None:
    """Get city/town population for a property."""
    # Try locality directly
    locality = cur.get("locality", "")
    pop = _CITY_POPULATIONS.get(locality)
    if pop:
        return float(pop)

    # For bg_imot: locality is "Център, Sofia" -- extract city name
    if "," in locality:
        city = locality.split(",")[-1].strip()
        pop = _CITY_POPULATIONS.get(city)
        if pop:
            return float(pop)

    # Try address_raw city part
    addr = cur.get("address_raw", "")
    if "," in addr:
        city = addr.split(",")[-1].strip()
        pop = _CITY_POPULATIONS.get(city)
        if pop:
            return float(pop)

    return None


EXTRA_NUMERIC_FEATURES = ["struct_floor", "struct_total_floors", "listing_age_days", "listing_year",
                          "city_population", "city_population_log", "area_sqm_log",
                          "rental_density_2km", "listing_score"]
EXTRA_CATEGORICAL_FEATURES = {"construction_type": CONSTRUCTION_TYPE_MAP}

# ---------------------------------------------------------------------------
# LLM-extracted features (from llm_enrich.py)
# ---------------------------------------------------------------------------
LLM_NUMERIC_FEATURES = [
    "llm_condition", "llm_floor", "llm_total_floors",
    "llm_outdoor_sqm", "llm_building_units",
]
LLM_BOOLEAN_FEATURES = [
    "llm_bright", "llm_quiet", "llm_sea_proximity",
    "llm_is_investment", "llm_is_new_build", "llm_has_storage",
]

# Ordinal encoding maps for LLM categorical features
FURNISHING_MAP = {"unknown": 0, "unfurnished": 1, "partly_furnished": 2, "furnished": 3}
VIEW_MAP = {"unknown": 0, "none": 0, "garden": 1, "pool": 1, "city": 2, "valley": 3, "harbour": 4, "sea": 5}
QUALITY_MAP = {"budget": 1, "standard": 2, "premium": 3, "luxury": 4}
CONSTRUCTION_MAP = {"unknown": 0, "off_plan": 1, "under_construction": 2, "completed": 3}
RENOVATION_ERA_MAP = {"unknown": 0, "dated": 1, "recent": 2, "modern": 3}
PARKING_MAP = {"unknown": 0, "none": 0, "street": 1, "car_space": 2, "garage": 3, "double_garage": 4}
OUTDOOR_MAP = {"unknown": 0, "none": 0, "balcony": 1, "yard": 2, "garden": 3, "terrace": 4, "roof_terrace": 5}
FLOOR_CAT_MAP = {"unknown": 0, "ground": 1, "low": 2, "mid": 3, "high": 4, "penthouse_level": 5}
KITCHEN_MAP = {"unknown": 0, "kitchenette": 1, "separate": 2, "open_plan": 3}
ORIENTATION_MAP = {"unknown": 0, "north": 1, "west": 2, "east": 3, "south": 4}
CEILING_MAP = {"unknown": 0, "normal": 1, "high": 2, "double": 3}
NOISE_MAP = {"unknown": 0, "busy": 1, "moderate": 2, "quiet": 3}
LEASE_MAP = {"unknown": 0, "leasehold": 1, "freehold": 2}
FLOORING_MAP = {"unknown": 0, "concrete": 1, "tiles": 2, "wood": 3, "marble": 4}

# Features with natural order -- keep as ordinal (numeric)
LLM_ORDINAL_FEATURES = {
    "llm_furnishing": FURNISHING_MAP,
    "llm_quality_tier": QUALITY_MAP,
    "llm_construction_status": CONSTRUCTION_MAP,
    "llm_floor_category": FLOOR_CAT_MAP,
    "llm_ceiling_height": CEILING_MAP,
    "llm_noise_exposure": NOISE_MAP,
    "llm_lease_type": LEASE_MAP,
}

# Features without natural order -- use LightGBM native categorical
LLM_CATEGORICAL_FEATURES = {
    "llm_view": VIEW_MAP,
    "llm_parking_type": PARKING_MAP,
    "llm_outdoor_space": OUTDOOR_MAP,
    "llm_kitchen_type": KITCHEN_MAP,
    "llm_orientation": ORIENTATION_MAP,
}

# Image-based LLM features (only present if llm_enrich ran with --with-images)
LLM_IMAGE_NUMERIC = ["llm_interior_score", "llm_kitchen_score", "llm_bathroom_score",
                      "llm_exterior_condition", "llm_street_quality"]
LLM_IMAGE_ORDINAL = {
    "llm_renovation_era": RENOVATION_ERA_MAP,
}
LLM_IMAGE_CATEGORICAL = {
    "llm_flooring_type": FLOORING_MAP,
}


# ===================================================================
# Data Loading
# ===================================================================

def load_training_data(
    listing_type: str,
    property_type: str = "apartment",
    collections: list[str] | None = None,
) -> list[dict]:
    """Load and filter properties from one or more DocStore collections."""
    config = MODEL_CONFIGS.get((property_type, listing_type))
    if config is None:
        raise ValueError(
            f"No config for ({property_type}, {listing_type}). "
            f"Available: {list(MODEL_CONFIGS.keys())}"
        )

    if collections is None:
        collections = ["mt_remax"]

    store = DocStore()
    all_docs = []
    for coll_name in collections:
        coll = store.collection(coll_name)
        all_docs.extend(coll.find())
    store.close()

    result = []
    skipped = {"type": 0, "listing": 0, "suspicious": 0, "duplicate": 0,
               "no_price": 0, "no_coords": 0, "price_outlier": 0,
               "area_outlier": 0, "no_area": 0, "non_monthly": 0}

    for doc in all_docs:
        cur = doc.get("current", {})

        if cur.get("property_type") != property_type:
            skipped["type"] += 1
            continue
        if cur.get("listing_type") != listing_type:
            skipped["listing"] += 1
            continue
        if cur.get("suspicious"):
            skipped["suspicious"] += 1
            continue
        if cur.get("duplicate_of"):
            skipped["duplicate"] += 1
            continue

        price = cur.get("price_eur")
        if not price or price <= 0:
            skipped["no_price"] += 1
            continue

        lat = cur.get("lat") or cur.get("map_lat")
        lon = cur.get("lon") or cur.get("map_lon")
        if not lat or not lon:
            skipped["no_coords"] += 1
            continue
        # Ensure lat/lon keys exist for build_dataframe
        cur["lat"] = lat
        cur["lon"] = lon

        # Rental period filter
        if listing_type == "rent":
            raw = cur.get("raw_data")
            if isinstance(raw, dict):
                period = raw.get("Period", "Monthly")
            elif isinstance(raw, list) and raw and isinstance(raw[0], dict):
                period = raw[0].get("Period", "Monthly")
            else:
                period = "Monthly"
            if period != "Monthly":
                skipped["non_monthly"] += 1
                continue

        # VAT normalization: Bulgarian listings marked "без ДДС" need 20% added
        if cur.get("vat_status") == "excluded":
            price = price * 1.20

        # Price outlier check
        if price < config["min_price"] or price > config["max_price"]:
            skipped["price_outlier"] += 1
            continue

        # Area handling
        area = cur.get("area_sqm")
        if area is not None and area <= 1.0:
            area = None  # sentinel value from API
        if area is not None:
            if area < config["min_area"] or area > config["max_area"]:
                skipped["area_outlier"] += 1
                continue
        elif config["require_area"]:
            skipped["no_area"] += 1
            continue

        # Price per sqm sanity check (catches mistyped prices)
        if area and area > 0 and price > 0:
            ppsqm = price / area
            if listing_type == "sale" and (ppsqm > 30_000 or ppsqm < 100):
                skipped["price_outlier"] += 1
                continue

        # For bg_imot: combine city + neighborhood as locality
        # (e.g., "Център" exists in 9 cities at wildly different prices)
        addr = cur.get("address_raw", "")
        if "," in addr and doc.get("country", cur.get("country_code", "")) == "BG":
            city = addr.split(",")[-1].strip()
            cur["locality"] = f"{cur.get('locality', '')}, {city}"

        # Store cleaned area and doc_id for feature building
        cur["_clean_area"] = area
        cur["_doc_id"] = doc.get("_id", "")
        result.append(cur)

    logger.info(
        f"Loaded {len(result)} {property_type} {listing_type} samples "
        f"(skipped: {dict(skipped)})"
    )
    return result


# ===================================================================
# Feature Engineering
# ===================================================================

def extract_amenities(cur: dict) -> dict:
    """Extract boolean amenity features from a doc.

    Works for RE/MAX (has `features` list), MaltaPark (has `has_*` fields),
    and bg_imot (has `has_*` fields from HTML scraper).
    """
    features_list = cur.get("features")

    if features_list:
        # RE/MAX: parse from features list
        feat_set = set(features_list)
        result = {
            key: 1.0 if any(kw in feat_set for kw in keywords) else 0.0
            for key, keywords in AMENITY_KEYWORDS.items()
        }
    elif cur.get("source") == "mt_maltapark":
        # MaltaPark: map structured boolean fields
        result = {k: np.nan for k in AMENITY_KEYWORDS}
        result["has_balcony"] = float(cur.get("has_balcony", 0) or 0)
        result["has_lift"] = float(cur.get("has_elevator", 0) or 0)
        result["has_pool"] = float(cur.get("has_pool", 0) or 0)
    elif any(cur.get(k) is not None for k in ("has_ac", "has_elevator", "has_furnishing", "has_access_control")):
        # bg_imot: has_* fields from HTML scraper
        result = {k: np.nan for k in AMENITY_KEYWORDS}
        result["has_balcony"] = float(cur.get("has_balcony", 0) or 0)
        result["has_ac"] = float(cur.get("has_ac", 0) or 0)
        result["has_lift"] = float(cur.get("has_elevator", 0) or 0)
        result["has_alarm"] = float(cur.get("has_access_control", 0) or 0)
        result["has_video_intercom"] = float(cur.get("has_cctv", 0) or 0)
        result["has_yard"] = float(cur.get("has_garden", 0) or 0)
    else:
        result = {k: np.nan for k in AMENITY_KEYWORDS}

    return result


def extract_llm_features(cur: dict) -> dict:
    """Extract LLM-enriched features from a doc's current dict."""
    row = {}
    # Numeric
    for f in LLM_NUMERIC_FEATURES:
        val = cur.get(f)
        row[f] = float(val) if val is not None else np.nan
    # Boolean
    for f in LLM_BOOLEAN_FEATURES:
        val = cur.get(f)
        row[f] = float(val) if val is not None else np.nan
    # Ordinal (natural order -- encode as numbers)
    for f, mapping in LLM_ORDINAL_FEATURES.items():
        val = cur.get(f)
        row[f] = float(mapping.get(val, 0)) if val is not None else np.nan
    # Categorical (no natural order -- label-encode for LightGBM native categorical)
    for f, mapping in LLM_CATEGORICAL_FEATURES.items():
        val = cur.get(f)
        row[f] = float(mapping.get(val, 0)) if val is not None else np.nan
    # Image-based numeric
    for f in LLM_IMAGE_NUMERIC:
        val = cur.get(f)
        row[f] = float(val) if val is not None else np.nan
    # Image-based ordinal
    for f, mapping in LLM_IMAGE_ORDINAL.items():
        val = cur.get(f)
        row[f] = float(mapping.get(val, 0)) if val is not None else np.nan
    # Image-based categorical
    for f, mapping in LLM_IMAGE_CATEGORICAL.items():
        val = cur.get(f)
        row[f] = float(mapping.get(val, 0)) if val is not None else np.nan
    return row


def build_dataframe(
    docs: list[dict],
    llm_run: dict[str, dict] | None = None,
    coord_overrides: dict[str, tuple[float, float]] | None = None,
    rental_coords: list[tuple[float, float]] | None = None,
) -> pd.DataFrame:
    """Convert list of property dicts to a feature DataFrame.

    If llm_run is provided (doc_id -> features dict from a run file),
    those features are used instead of llm_* fields in the doc.
    If coord_overrides is provided (doc_id -> (lat, lon)), geocoded
    coordinates replace town-level ones for distance calculations.
    If rental_coords is provided, computes rental_density_2km for each property.
    """
    # Build KDTree for rental density computation
    _rental_tree = None
    if rental_coords:
        from scipy.spatial import cKDTree
        _rental_tree = cKDTree(
            [(lat * 111.0, lon * 89.0) for lat, lon in rental_coords]
        )

    rows = []
    n_refined = 0
    for cur in docs:
        amenities = extract_amenities(cur)
        total_int = cur.get("total_int_area")
        total_ext = cur.get("total_ext_area")

        # LLM features: prefer run file if provided, else use DocStore fields
        doc_id = cur.get("_doc_id", "")
        if llm_run and doc_id in llm_run:
            # Build a fake "current" with llm_ prefix for extract_llm_features
            llm_cur = {f"llm_{k}": v for k, v in llm_run[doc_id].items()}
            llm_cur["llm_model"] = llm_run[doc_id].get("_model", None)
            llm = extract_llm_features(llm_cur)
            llm_model = llm_cur.get("llm_model")
        else:
            llm = extract_llm_features(cur)
            llm_model = cur.get("llm_model")

        # Use best available coordinates:
        # 1. Precise map coords from imot.bg (map_lat/map_lon) -- street-level
        # 2. Geocoded location_reference from LLM enrichment
        # 3. Neighborhood-level geocoding (lat/lon) -- fallback
        lat, lon = cur["lat"], cur["lon"]
        if cur.get("map_lat"):
            lat, lon = cur["map_lat"], cur["map_lon"]
            n_refined += 1
        elif coord_overrides and doc_id in coord_overrides:
            lat, lon = coord_overrides[doc_id]
            n_refined += 1

        # Structured source-specific features (bg_imot has floor/construction_type)
        struct_floor = cur.get("floor")
        struct_floor = float(struct_floor) if struct_floor is not None else np.nan
        struct_total_floors = cur.get("total_floors")
        struct_total_floors = float(struct_total_floors) if struct_total_floors is not None else np.nan
        ct = cur.get("construction_type", "")
        construction_type = float(CONSTRUCTION_TYPE_MAP.get(ct, 0)) if ct else np.nan

        # Temporal features from listing date
        listing_age_days = np.nan
        listing_year = np.nan

        # For bg_imot: extract real creation date from the obiava ID in the URL
        # URL format: obiava-1b176839608204609-... where digits 3-12 are Unix timestamp
        url = cur.get("url", "")
        creation_date = None
        if url:
            import re as _re
            id_match = _re.search(r'obiava-\w{2}(\d{10})', url)
            if id_match:
                ts = int(id_match.group(1))
                if 1400000000 < ts < 2000000000:
                    from datetime import datetime, timezone
                    creation_date = datetime.fromtimestamp(ts, tz=timezone.utc)

        # Fall back to listing_date / last_modified for other sources
        if not creation_date:
            date_str = cur.get("listing_date") or cur.get("last_modified") or ""
            if date_str:
                creation_date = _parse_listing_date(str(date_str))

        if creation_date:
            from datetime import datetime, timezone
            now = datetime.now(timezone.utc)
            listing_age_days = (now - creation_date).days
            listing_year = creation_date.year + creation_date.month / 12.0

        dists = compute_distances(lat, lon)
        osm = compute_osm_features(lat, lon)

        # Premium zone: from raw_data.Zone field (luxury developments)
        raw = cur.get("raw_data", {})
        zone = raw.get("Zone") if isinstance(raw, dict) else None
        is_premium = 1.0 if zone else 0.0

        # Gozo: separate island with ~50% lower prices than Malta
        locality = cur.get("locality", "")
        is_gozo = 1.0 if locality.startswith("Gozo") or cur.get("province") == "Gozo" else 0.0

        # Resort: seasonal rental market (Bulgarian coastal resorts)
        is_resort = 1.0 if any(kw in locality for kw in _RESORT_KEYWORDS) else 0.0

        # RE/MAX LocationTypes (from detail API)
        raw_detail = cur.get("raw_data_detail", {})
        loc_types = set()
        if isinstance(raw_detail, dict):
            for lt in (raw_detail.get("LocationTypes") or []):
                name = lt.get("Name", "") if isinstance(lt, dict) else ""
                if name:
                    loc_types.add(name)
        is_near_beach = 1.0 if "Near Beach" in loc_types else 0.0
        is_seafront = 1.0 if "Seafront" in loc_types else 0.0
        is_sea_view = 1.0 if "Sea View" in loc_types else 0.0
        is_quiet_road = 1.0 if "On Quiet Road" in loc_types else 0.0
        is_city_center = 1.0 if "Village Core (City Center)" in loc_types else 0.0
        is_countryside = 1.0 if "Countryside" in loc_types or "Rural" in loc_types else 0.0

        # RE/MAX Score (listing quality 0-100)
        score = raw_detail.get("Score") if isinstance(raw_detail, dict) else None
        listing_score = float(score) if score and score > 0 else np.nan

        # Use LLM-corrected area if available (catches attic/common parts inflation)
        area = cur.get("_clean_area", np.nan)
        if llm_run and doc_id in llm_run:
            actual_area = llm_run[doc_id].get("actual_living_area")
            if actual_area and actual_area > 10:
                area = float(actual_area)

        # Rental density: count of rental listings within 2km
        rental_density = np.nan
        if _rental_tree is not None:
            pts = _rental_tree.query_ball_point([lat * 111.0, lon * 89.0], r=2.0)
            rental_density = float(len(pts))

        rows.append({
            "price_eur": cur["price_eur"],
            "lat": lat,
            "lon": lon,
            "area_sqm": area,
            "area_sqm_log": math.log(area) if area is not None and not (isinstance(area, float) and np.isnan(area)) and area > 0 else np.nan,
            "is_premium_zone": is_premium,
            "is_gozo": is_gozo,
            "is_resort": is_resort,
            "is_near_beach": is_near_beach,
            "is_seafront": is_seafront,
            "is_sea_view": is_sea_view,
            "is_quiet_road": is_quiet_road,
            "is_city_center": is_city_center,
            "is_countryside": is_countryside,
            "rental_density_2km": rental_density,
            "listing_score": listing_score,
            "struct_floor": struct_floor,
            "struct_total_floors": struct_total_floors,
            "construction_type": construction_type,
            "listing_age_days": listing_age_days,
            "listing_year": listing_year,
            "city_population": _get_population(cur),
            "city_population_log": math.log(_get_population(cur)) if _get_population(cur) else np.nan,
            **dists,
            **osm,
            "bedrooms": cur.get("bedrooms") or np.nan,
            "bathrooms": cur.get("bathrooms") or np.nan,
            "rooms": cur.get("rooms") or np.nan,
            "total_int_area": total_int if total_int else np.nan,
            "total_ext_area": total_ext if total_ext else np.nan,
            "locality": cur.get("locality", "Unknown"),
            "province": cur.get("province", "Unknown"),
            **amenities,
            **llm,
            "_llm_model": llm_model,
            "_doc_id": doc_id,
        })
    if n_refined:
        logger.info(f"Refined coordinates for {n_refined}/{len(docs)} docs via geocoded location_reference")
    return pd.DataFrame(rows)


def target_encode(
    train_series: pd.Series,
    train_target: pd.Series,
    apply_series: pd.Series,
    smoothing: float = 10.0,
) -> pd.Series:
    """Smoothed target encoding. Fit on train, transform apply_series."""
    global_mean = train_target.mean()
    stats = train_target.groupby(train_series).agg(["mean", "count"])
    smooth = (
        (stats["count"] * stats["mean"] + smoothing * global_mean)
        / (stats["count"] + smoothing)
    )
    return apply_series.map(smooth).fillna(global_mean)


def get_feature_names() -> list[str]:
    """Return the ordered list of feature column names."""
    return (
        NUMERIC_FEATURES + AMENITY_FEATURES + CATEGORICAL_FEATURES
        + EXTRA_NUMERIC_FEATURES + list(EXTRA_CATEGORICAL_FEATURES.keys())
        + LLM_NUMERIC_FEATURES + LLM_BOOLEAN_FEATURES
        + list(LLM_ORDINAL_FEATURES.keys())
        + list(LLM_CATEGORICAL_FEATURES.keys())
        + LLM_IMAGE_NUMERIC + list(LLM_IMAGE_ORDINAL.keys())
        + list(LLM_IMAGE_CATEGORICAL.keys())
    )


# ===================================================================
# Spatial Cross-Validation
# ===================================================================

def spatial_cv_splits(lats: np.ndarray, n_folds: int = N_FOLDS, localities: np.ndarray | None = None):
    """Create geographic folds stratified by locality clusters.

    Groups properties by locality (city/town), then distributes each group
    across folds proportionally. Within each group, properties are sorted
    by latitude for spatial separation. This ensures every fold sees every
    city/region, preventing the model from being tested on unseen cities.

    Falls back to simple latitude strips if localities are not provided.
    """
    all_idx = np.arange(len(lats))

    if localities is None:
        # Simple latitude strip fallback
        lat_order = np.argsort(lats)
        fold_indices = np.array_split(lat_order, n_folds)
        splits = []
        for i in range(n_folds):
            test_idx = fold_indices[i]
            train_idx = np.concatenate([fold_indices[j] for j in range(n_folds) if j != i])
            splits.append((train_idx, test_idx))
        return splits

    # Group indices by locality
    from collections import defaultdict
    groups = defaultdict(list)
    for idx in all_idx:
        groups[localities[idx]].append(idx)

    # For each group, sort by latitude and split into n_folds
    fold_buckets = [[] for _ in range(n_folds)]
    for loc, indices in groups.items():
        arr = np.array(indices)
        sorted_arr = arr[np.argsort(lats[arr])]
        group_folds = np.array_split(sorted_arr, n_folds)
        for i in range(n_folds):
            fold_buckets[i].append(group_folds[i])

    # Build train/test splits
    splits = []
    for i in range(n_folds):
        test_idx = np.concatenate(fold_buckets[i])
        train_parts = []
        for j in range(n_folds):
            if j != i:
                train_parts.append(np.concatenate(fold_buckets[j]))
        train_idx = np.concatenate(train_parts)
        splits.append((train_idx, test_idx))
    return splits


# ===================================================================
# Evaluation
# ===================================================================

def evaluate_predictions(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    """Compute regression metrics on original EUR scale."""
    mae = mean_absolute_error(y_true, y_pred)
    rmse = float(np.sqrt(mean_squared_error(y_true, y_pred)))
    r2 = r2_score(y_true, y_pred)
    mape = float(np.mean(np.abs((y_true - y_pred) / y_true)) * 100)
    median_ae = float(np.median(np.abs(y_true - y_pred)))
    return {
        "mae": round(mae, 2),
        "rmse": round(rmse, 2),
        "r2": round(r2, 4),
        "mape_pct": round(mape, 2),
        "median_ae": round(median_ae, 2),
        "n_samples": len(y_true),
    }


def price_accuracy_buckets(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    """Percentage of predictions within X% of actual price."""
    errors_pct = np.abs((y_true - y_pred) / y_true) * 100
    return {
        "within_5pct": round(float(np.mean(errors_pct <= 5) * 100), 1),
        "within_10pct": round(float(np.mean(errors_pct <= 10) * 100), 1),
        "within_15pct": round(float(np.mean(errors_pct <= 15) * 100), 1),
        "within_20pct": round(float(np.mean(errors_pct <= 20) * 100), 1),
        "within_25pct": round(float(np.mean(errors_pct <= 25) * 100), 1),
    }


# ===================================================================
# Training
# ===================================================================

def _build_feature_matrix(df_slice, base_cols, feature_names, loc_codes, prov_codes, indices):
    """Assemble feature matrix with label-encoded locality/province."""
    X = df_slice[base_cols].copy()
    X["locality_enc"] = loc_codes[indices]
    X["province_enc"] = prov_codes[indices]
    return X[feature_names].values


def train_and_evaluate(
    df: pd.DataFrame,
    feature_names: list[str],
    n_folds: int = N_FOLDS,
) -> dict:
    """
    Train LightGBM + XGBoost ensemble with spatial CV.
    Uses LightGBM native categorical encoding for locality/province.
    """
    log_target = np.log(df["price_eur"].values)
    lats = df["lat"].values

    # Label-encode locality and province as integers for LightGBM categorical
    loc_cat = df["locality"].astype("category")
    prov_cat = df["province"].astype("category")
    loc_codes = loc_cat.cat.codes.values.astype(float)
    prov_codes = prov_cat.cat.codes.values.astype(float)

    # Indices of categorical features in the feature matrix
    all_cat_names = (
        ["locality_enc", "province_enc"]
        + list(EXTRA_CATEGORICAL_FEATURES.keys())
        + list(LLM_CATEGORICAL_FEATURES.keys())
        + list(LLM_IMAGE_CATEGORICAL.keys())
    )
    cat_indices = [feature_names.index(c) for c in all_cat_names]

    base_cols = (
        NUMERIC_FEATURES + AMENITY_FEATURES
        + EXTRA_NUMERIC_FEATURES + list(EXTRA_CATEGORICAL_FEATURES.keys())
        + LLM_NUMERIC_FEATURES + LLM_BOOLEAN_FEATURES
        + list(LLM_ORDINAL_FEATURES.keys())
        + list(LLM_CATEGORICAL_FEATURES.keys())
        + LLM_IMAGE_NUMERIC + list(LLM_IMAGE_ORDINAL.keys())
        + list(LLM_IMAGE_CATEGORICAL.keys())
    )

    localities_arr = df["locality"].values
    splits = spatial_cv_splits(lats, n_folds, localities=localities_arr)

    all_y_true = []
    all_y_pred = []
    fold_metrics = []

    for fold_i, (train_idx, test_idx) in enumerate(splits):
        X_train = _build_feature_matrix(df.iloc[train_idx], base_cols, feature_names, loc_codes, prov_codes, train_idx)
        X_test = _build_feature_matrix(df.iloc[test_idx], base_cols, feature_names, loc_codes, prov_codes, test_idx)
        y_train = log_target[train_idx]
        y_test = log_target[test_idx]

        # LightGBM with native categorical support
        lgb_model = lgb.LGBMRegressor(**LGBM_PARAMS)
        lgb_model.fit(X_train, y_train, eval_set=[(X_test, y_test)],
                      categorical_feature=cat_indices)
        lgb_pred_log = lgb_model.predict(X_test)

        # XGBoost (uses integer codes as ordinal -- still benefits)
        xgb_model = xgb.XGBRegressor(**XGB_PARAMS)
        xgb_model.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=False)
        xgb_pred_log = xgb_model.predict(X_test)

        # Ensemble in log space, then exponentiate
        ensemble_log = LGBM_WEIGHT * lgb_pred_log + XGB_WEIGHT * xgb_pred_log
        ensemble_eur = np.exp(ensemble_log)
        actual_eur = np.exp(y_test)

        metrics = evaluate_predictions(actual_eur, ensemble_eur)
        buckets = price_accuracy_buckets(actual_eur, ensemble_eur)
        fold_metrics.append({**metrics, **buckets})

        all_y_true.extend(actual_eur.tolist())
        all_y_pred.extend(ensemble_eur.tolist())

        logger.info(
            f"Fold {fold_i + 1}/{n_folds}: "
            f"MAE={metrics['mae']:,.0f}, MAPE={metrics['mape_pct']:.1f}%, "
            f"R2={metrics['r2']:.3f}, within_10pct={buckets['within_10pct']:.1f}%"
        )

    # Overall CV metrics
    overall = evaluate_predictions(np.array(all_y_true), np.array(all_y_pred))
    overall_buckets = price_accuracy_buckets(np.array(all_y_true), np.array(all_y_pred))

    logger.info("--- Cross-validation summary ---")
    logger.info(f"MAE: {overall['mae']:,.0f} EUR")
    logger.info(f"MAPE: {overall['mape_pct']:.1f}%")
    logger.info(f"R2: {overall['r2']:.4f}")
    logger.info(f"Median AE: {overall['median_ae']:,.0f} EUR")
    for k, v in overall_buckets.items():
        logger.info(f"  {k}: {v}%")

    # Retrain on full data
    logger.info("Retraining on full dataset...")

    X_full = _build_feature_matrix(df, base_cols, feature_names, loc_codes, prov_codes, np.arange(len(df)))

    params_no_es = {k: v for k, v in LGBM_PARAMS.items() if k != "early_stopping_rounds"}
    final_lgb = lgb.LGBMRegressor(**params_no_es)
    final_lgb.fit(X_full, log_target, categorical_feature=cat_indices)

    params_no_es_xgb = {k: v for k, v in XGB_PARAMS.items() if k != "early_stopping_rounds"}
    final_xgb = xgb.XGBRegressor(**params_no_es_xgb)
    final_xgb.fit(X_full, log_target, verbose=False)

    # Feature importance
    importance = dict(zip(feature_names, final_lgb.feature_importances_.tolist()))

    # Category mappings for inference (locality name -> integer code)
    locality_map = dict(zip(loc_cat, loc_codes))
    province_map = dict(zip(prov_cat, prov_codes))

    # Collect LLM enrichment metadata from training data
    llm_enriched_count = int(df["llm_condition"].notna().sum())
    llm_feature_coverage = round(100 * llm_enriched_count / len(df), 1)

    return {
        "lgb_model": final_lgb,
        "xgb_model": final_xgb,
        "feature_names": feature_names,
        "feature_importance": importance,
        "locality_encoding": {k: int(v) for k, v in locality_map.items()},
        "province_encoding": {k: int(v) for k, v in province_map.items()},
        "global_mean_log_price": float(log_target.mean()),
        "cv_metrics": {**overall, **overall_buckets},
        "fold_metrics": fold_metrics,
        "sample_count": len(df),
        "median_price": float(np.median(df["price_eur"])),
        "llm_enriched_count": llm_enriched_count,
        "llm_feature_coverage_pct": llm_feature_coverage,
    }


# ===================================================================
# Artifact Saving
# ===================================================================

def save_artifacts(
    results: dict,
    property_type: str,
    listing_type: str,
    config: dict,
) -> str:
    """Save trained models and metadata to ml/artifacts/."""
    os.makedirs(ARTIFACTS_DIR, exist_ok=True)
    version = datetime.now(timezone.utc).strftime("%Y%m%d")
    prefix = f"mt_{property_type}_{listing_type}"

    lgb_path = os.path.join(ARTIFACTS_DIR, f"{prefix}_lgb_v{version}.joblib")
    xgb_path = os.path.join(ARTIFACTS_DIR, f"{prefix}_xgb_v{version}.joblib")
    enc_path = os.path.join(ARTIFACTS_DIR, f"{prefix}_encoders_v{version}.joblib")
    meta_path = os.path.join(ARTIFACTS_DIR, f"{prefix}_meta_v{version}.json")

    joblib.dump(results["lgb_model"], lgb_path)
    joblib.dump(results["xgb_model"], xgb_path)
    joblib.dump({
        "locality": results["locality_encoding"],
        "province": results["province_encoding"],
        "global_mean_log_price": results["global_mean_log_price"],
    }, enc_path)

    metadata = {
        "country_code": "MT",
        "property_type": property_type,
        "listing_type": listing_type,
        "version": version,
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "sample_count": results["sample_count"],
        "median_price": results["median_price"],
        "target_transform": "log",
        "ensemble_weights": {"lgb": LGBM_WEIGHT, "xgb": XGB_WEIGHT},
        "feature_names": results["feature_names"],
        "feature_importance": results["feature_importance"],
        "outlier_bounds": config,
        "cv_metrics": results["cv_metrics"],
        "fold_metrics": results["fold_metrics"],
        "llm_enrichment": {
            "enriched_samples": results["llm_enriched_count"],
            "coverage_pct": results["llm_feature_coverage_pct"],
            "run_id": results.get("llm_run_id"),
            "run_meta": results.get("llm_run_meta"),
        },
    }

    with open(meta_path, "w") as f:
        json.dump(metadata, f, indent=2)

    logger.info(f"Saved artifacts to {ARTIFACTS_DIR}/")
    logger.info(f"  LGB:      {os.path.basename(lgb_path)}")
    logger.info(f"  XGB:      {os.path.basename(xgb_path)}")
    logger.info(f"  Encoders: {os.path.basename(enc_path)}")
    logger.info(f"  Meta:     {os.path.basename(meta_path)}")

    return ARTIFACTS_DIR


# ===================================================================
# Dry Run (data stats)
# ===================================================================

def print_dry_run_stats(df: pd.DataFrame, listing_type: str):
    """Print data statistics without training."""
    print(f"\n{'=' * 60}")
    print(f"  Data Summary: {len(df)} samples ({listing_type})")
    print(f"{'=' * 60}")

    print(f"\nPrice (EUR):")
    p = df["price_eur"]
    print(f"  min={p.min():,.0f}  P5={p.quantile(0.05):,.0f}  "
          f"median={p.median():,.0f}  P95={p.quantile(0.95):,.0f}  max={p.max():,.0f}")

    print(f"\nFeature coverage:")
    for col in NUMERIC_FEATURES + AMENITY_FEATURES + EXTRA_NUMERIC_FEATURES + list(EXTRA_CATEGORICAL_FEATURES.keys()):
        if col in df.columns:
            n_valid = df[col].notna().sum()
            print(f"  {col:25s}: {n_valid:>5d}/{len(df)} ({100 * n_valid / len(df):5.1f}%)")

    llm_cols = (
        LLM_NUMERIC_FEATURES + LLM_BOOLEAN_FEATURES
        + list(LLM_ORDINAL_FEATURES.keys())
        + list(LLM_CATEGORICAL_FEATURES.keys())
        + LLM_IMAGE_NUMERIC + list(LLM_IMAGE_ORDINAL.keys())
        + list(LLM_IMAGE_CATEGORICAL.keys())
    )
    llm_any = df[llm_cols[0]].notna().sum() if llm_cols else 0
    if llm_any > 0:
        print(f"\nLLM feature coverage:")
        for col in llm_cols:
            n_valid = df[col].notna().sum()
            print(f"  {col:25s}: {n_valid:>5d}/{len(df)} ({100 * n_valid / len(df):5.1f}%)")
        models = df["_llm_model"].dropna().value_counts()
        if len(models):
            print(f"\nLLM models used:")
            for m, c in models.items():
                print(f"  {m}: {c}")
    else:
        print(f"\nLLM features: none (run llm_enrich.py first)")

    print(f"\nTop 15 localities:")
    for loc, cnt in df["locality"].value_counts().head(15).items():
        print(f"  {loc:25s}: {cnt:>4d}")

    print(f"\nBedrooms distribution:")
    for bd, cnt in df["bedrooms"].value_counts().sort_index().items():
        if not np.isnan(bd):
            print(f"  {int(bd)} bed: {cnt:>4d}")
    print()


# ===================================================================
# Main
# ===================================================================

def main():
    parser = argparse.ArgumentParser(description="Train Malta valuation model")
    parser.add_argument(
        "--listing-type", required=True, choices=["sale", "rent"],
        help="sale or rent",
    )
    parser.add_argument(
        "--property-type", default="apartment",
        help="Property type (default: apartment)",
    )
    parser.add_argument(
        "--collections", default="mt_remax",
        help="Comma-separated collection names (default: mt_remax)",
    )
    parser.add_argument(
        "--llm-run", default=None,
        help="LLM enrichment run ID(s). Comma-separated for multiple collections (see llm_enrich.py --stats)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Show data stats without training",
    )
    args = parser.parse_args()

    config_key = (args.property_type, args.listing_type)
    if config_key not in MODEL_CONFIGS:
        logger.error(f"No config for {config_key}. Available: {list(MODEL_CONFIGS.keys())}")
        sys.exit(1)
    config = MODEL_CONFIGS[config_key]

    # Load LLM run data if specified (supports multiple comma-separated runs)
    llm_run_data = None
    llm_run_meta = None
    coord_overrides = None
    if args.llm_run:
        from llm_enrich import load_run, ENRICHMENTS_DIR
        run_ids = [r.strip() for r in args.llm_run.split(",")]
        llm_run_data = {}
        llm_run_meta = []
        for run_id in run_ids:
            run_data = load_run(run_id)
            llm_run_data.update(run_data)
            meta_path = os.path.join(ENRICHMENTS_DIR, run_id, "metadata.json")
            if os.path.exists(meta_path):
                with open(meta_path) as f:
                    llm_run_meta.append(json.load(f))
            logger.info(f"Loaded LLM run '{run_id}': {len(run_data)} enrichments")
        logger.info(f"Total LLM enrichments: {len(llm_run_data)}")

        # Load geocoded coordinate overrides from all runs
        try:
            from geocode_locations import build_coordinate_overrides
            coord_overrides = {}
            for run_id in run_ids:
                try:
                    overrides = build_coordinate_overrides(run_id)
                    coord_overrides.update(overrides)
                except FileNotFoundError:
                    pass
            if coord_overrides:
                logger.info(f"Loaded {len(coord_overrides)} geocoded coordinate overrides")
        except Exception:
            pass

    # Load data
    collection_list = [c.strip() for c in args.collections.split(",")]
    docs = load_training_data(args.listing_type, args.property_type, collections=collection_list)
    if len(docs) < 50:
        logger.error(f"Only {len(docs)} samples -- need at least 50 to train.")
        sys.exit(1)

    # Load rental coordinates for rental_density_2km feature
    rental_coords = None
    store2 = DocStore()
    for coll_name in collection_list:
        coll2 = store2.collection(coll_name)
        coords = []
        for doc in coll2.find():
            cur = doc.get("current", {})
            if cur.get("listing_type") == "rent" and cur.get("property_type") == "apartment":
                rlat = cur.get("map_lat") or cur.get("lat")
                rlon = cur.get("map_lon") or cur.get("lon")
                if rlat and rlon:
                    coords.append((rlat, rlon))
        if coords:
            rental_coords = coords
    store2.close()
    if rental_coords:
        logger.info(f"Loaded {len(rental_coords)} rental coords for density feature")

    # Build DataFrame
    df = build_dataframe(docs, llm_run=llm_run_data, coord_overrides=coord_overrides,
                         rental_coords=rental_coords)
    logger.info(
        f"DataFrame: {len(df)} rows, "
        f"area_sqm coverage: {df['area_sqm'].notna().sum()}/{len(df)} "
        f"({100 * df['area_sqm'].notna().mean():.1f}%)"
    )

    if args.dry_run:
        print_dry_run_stats(df, args.listing_type)
        return

    # Train
    feature_names = get_feature_names()
    results = train_and_evaluate(df, feature_names)

    # Add LLM run info to results for metadata tracking
    if llm_run_meta:
        results["llm_run_id"] = args.llm_run
        results["llm_run_meta"] = llm_run_meta if len(llm_run_meta) > 1 else llm_run_meta[0]

    # Save
    save_artifacts(results, args.property_type, args.listing_type, config)

    logger.info("Done.")


if __name__ == "__main__":
    main()
