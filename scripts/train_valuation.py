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

AMENITY_FEATURES = list(AMENITY_KEYWORDS.keys()) + ["is_premium_zone"]

CATEGORICAL_FEATURES = ["locality_enc", "province_enc"]

# ---------------------------------------------------------------------------
# LLM-extracted features (from llm_enrich.py)
# ---------------------------------------------------------------------------
LLM_NUMERIC_FEATURES = ["llm_condition", "llm_floor", "llm_total_floors"]
LLM_BOOLEAN_FEATURES = ["llm_bright", "llm_quiet", "llm_sea_proximity"]

# Ordinal encoding maps for LLM categorical features
FURNISHING_MAP = {"unknown": 0, "unfurnished": 1, "partly_furnished": 2, "furnished": 3}
VIEW_MAP = {"unknown": 0, "none": 0, "garden": 1, "pool": 1, "city": 2, "valley": 3, "harbour": 4, "sea": 5}
QUALITY_MAP = {"budget": 1, "standard": 2, "premium": 3, "luxury": 4}
CONSTRUCTION_MAP = {"unknown": 0, "off_plan": 1, "under_construction": 2, "completed": 3}
RENOVATION_ERA_MAP = {"unknown": 0, "dated": 1, "recent": 2, "modern": 3}

LLM_ORDINAL_FEATURES = {
    "llm_furnishing": FURNISHING_MAP,
    "llm_view": VIEW_MAP,
    "llm_quality_tier": QUALITY_MAP,
    "llm_construction_status": CONSTRUCTION_MAP,
}

# Image-based LLM features (only present if llm_enrich ran with --with-images)
LLM_IMAGE_NUMERIC = ["llm_interior_score"]
LLM_IMAGE_ORDINAL = {"llm_renovation_era": RENOVATION_ERA_MAP}


# ===================================================================
# Data Loading
# ===================================================================

def load_training_data(
    listing_type: str,
    property_type: str = "apartment",
) -> list[dict]:
    """Load and filter properties from DocStore."""
    config = MODEL_CONFIGS.get((property_type, listing_type))
    if config is None:
        raise ValueError(
            f"No config for ({property_type}, {listing_type}). "
            f"Available: {list(MODEL_CONFIGS.keys())}"
        )

    store = DocStore()
    coll = store.collection("mt_remax")
    all_docs = coll.find()
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

        lat = cur.get("lat")
        lon = cur.get("lon")
        if not lat or not lon:
            skipped["no_coords"] += 1
            continue

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

def extract_amenities(features_list: list | None) -> dict:
    """Parse RE/MAX features list into boolean amenity columns."""
    if not features_list:
        return {k: np.nan for k in AMENITY_KEYWORDS}
    feat_set = set(features_list)
    return {
        key: 1.0 if any(kw in feat_set for kw in keywords) else 0.0
        for key, keywords in AMENITY_KEYWORDS.items()
    }


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
    # Ordinal categorical
    for f, mapping in LLM_ORDINAL_FEATURES.items():
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
    return row


def build_dataframe(
    docs: list[dict],
    llm_run: dict[str, dict] | None = None,
) -> pd.DataFrame:
    """Convert list of property dicts to a feature DataFrame.

    If llm_run is provided (doc_id -> features dict from a run file),
    those features are used instead of llm_* fields in the doc.
    """
    rows = []
    for cur in docs:
        amenities = extract_amenities(cur.get("features"))
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

        dists = compute_distances(cur["lat"], cur["lon"])
        osm = compute_osm_features(cur["lat"], cur["lon"])

        # Premium zone: from raw_data.Zone field (luxury developments)
        raw = cur.get("raw_data", {})
        zone = raw.get("Zone") if isinstance(raw, dict) else None
        is_premium = 1.0 if zone else 0.0

        rows.append({
            "price_eur": cur["price_eur"],
            "lat": cur["lat"],
            "lon": cur["lon"],
            "area_sqm": cur.get("_clean_area", np.nan),
            "is_premium_zone": is_premium,
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
        })
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
        + LLM_NUMERIC_FEATURES + LLM_BOOLEAN_FEATURES
        + list(LLM_ORDINAL_FEATURES.keys())
        + LLM_IMAGE_NUMERIC + list(LLM_IMAGE_ORDINAL.keys())
    )


# ===================================================================
# Spatial Cross-Validation
# ===================================================================

def spatial_cv_splits(lats: np.ndarray, n_folds: int = N_FOLDS):
    """Create geographic folds by latitude strips."""
    lat_order = np.argsort(lats)
    fold_indices = np.array_split(lat_order, n_folds)
    splits = []
    for i in range(n_folds):
        test_idx = fold_indices[i]
        train_idx = np.concatenate([fold_indices[j] for j in range(n_folds) if j != i])
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

def train_and_evaluate(
    df: pd.DataFrame,
    feature_names: list[str],
    n_folds: int = N_FOLDS,
) -> dict:
    """
    Train LightGBM + XGBoost ensemble with spatial CV.
    Returns dict with models, metrics, feature importance, and locality encoding.
    """
    log_target = np.log(df["price_eur"].values)
    lats = df["lat"].values

    splits = spatial_cv_splits(lats, n_folds)

    all_y_true = []
    all_y_pred = []
    fold_metrics = []

    for fold_i, (train_idx, test_idx) in enumerate(splits):
        df_train = df.iloc[train_idx]
        df_test = df.iloc[test_idx]

        # Target encode locality and province within fold
        log_target_train = log_target[train_idx]

        loc_train = target_encode(
            df_train["locality"], pd.Series(log_target_train, index=df_train.index),
            df_train["locality"],
        )
        loc_test = target_encode(
            df_train["locality"], pd.Series(log_target_train, index=df_train.index),
            df_test["locality"],
        )
        prov_train = target_encode(
            df_train["province"], pd.Series(log_target_train, index=df_train.index),
            df_train["province"],
        )
        prov_test = target_encode(
            df_train["province"], pd.Series(log_target_train, index=df_train.index),
            df_test["province"],
        )

        # Build feature matrices
        base_cols = (
            NUMERIC_FEATURES + AMENITY_FEATURES
            + LLM_NUMERIC_FEATURES + LLM_BOOLEAN_FEATURES
            + list(LLM_ORDINAL_FEATURES.keys())
            + LLM_IMAGE_NUMERIC + list(LLM_IMAGE_ORDINAL.keys())
        )
        X_train = df_train[base_cols].copy()
        X_train["locality_enc"] = loc_train.values
        X_train["province_enc"] = prov_train.values
        X_train = X_train[feature_names].values

        X_test = df_test[base_cols].copy()
        X_test["locality_enc"] = loc_test.values
        X_test["province_enc"] = prov_test.values
        X_test = X_test[feature_names].values

        y_train = log_target[train_idx]
        y_test = log_target[test_idx]

        # Train LightGBM
        lgb_model = lgb.LGBMRegressor(**LGBM_PARAMS)
        lgb_model.fit(X_train, y_train, eval_set=[(X_test, y_test)])
        lgb_pred_log = lgb_model.predict(X_test)

        # Train XGBoost
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

    # Full-data target encoding
    locality_enc_full = target_encode(
        df["locality"], pd.Series(log_target, index=df.index),
        df["locality"],
    )
    province_enc_full = target_encode(
        df["province"], pd.Series(log_target, index=df.index),
        df["province"],
    )

    base_cols = (
        NUMERIC_FEATURES + AMENITY_FEATURES
        + LLM_NUMERIC_FEATURES + LLM_BOOLEAN_FEATURES
        + list(LLM_ORDINAL_FEATURES.keys())
        + LLM_IMAGE_NUMERIC + list(LLM_IMAGE_ORDINAL.keys())
    )
    X_full = df[base_cols].copy()
    X_full["locality_enc"] = locality_enc_full.values
    X_full["province_enc"] = province_enc_full.values
    X_full = X_full[feature_names].values

    final_lgb = lgb.LGBMRegressor(**LGBM_PARAMS)
    # No early stopping on full retrain -- remove eval_set
    params_no_es = {k: v for k, v in LGBM_PARAMS.items() if k != "early_stopping_rounds"}
    final_lgb = lgb.LGBMRegressor(**params_no_es)
    final_lgb.fit(X_full, log_target)

    params_no_es_xgb = {k: v for k, v in XGB_PARAMS.items() if k != "early_stopping_rounds"}
    final_xgb = xgb.XGBRegressor(**params_no_es_xgb)
    final_xgb.fit(X_full, log_target, verbose=False)

    # Feature importance
    importance = dict(zip(feature_names, final_lgb.feature_importances_.tolist()))

    # Locality encoding map for inference
    locality_map = dict(zip(df["locality"], locality_enc_full))
    province_map = dict(zip(df["province"], province_enc_full))

    # Collect LLM enrichment metadata from training data
    llm_models_used = df.get("_llm_model")  # not in features, but we stored it
    llm_enriched_count = int(df["llm_condition"].notna().sum())
    llm_feature_coverage = round(100 * llm_enriched_count / len(df), 1)

    return {
        "lgb_model": final_lgb,
        "xgb_model": final_xgb,
        "feature_names": feature_names,
        "feature_importance": importance,
        "locality_encoding": locality_map,
        "province_encoding": province_map,
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
    for col in NUMERIC_FEATURES + AMENITY_FEATURES:
        n_valid = df[col].notna().sum()
        print(f"  {col:20s}: {n_valid:>5d}/{len(df)} ({100 * n_valid / len(df):5.1f}%)")

    llm_cols = (
        LLM_NUMERIC_FEATURES + LLM_BOOLEAN_FEATURES
        + list(LLM_ORDINAL_FEATURES.keys())
        + LLM_IMAGE_NUMERIC + list(LLM_IMAGE_ORDINAL.keys())
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
        "--llm-run", default=None,
        help="Load LLM features from a specific enrichment run ID (see llm_enrich.py --stats)",
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

    # Load LLM run data if specified
    llm_run_data = None
    llm_run_meta = None
    if args.llm_run:
        from llm_enrich import load_run, ENRICHMENTS_DIR
        llm_run_data = load_run(args.llm_run)
        meta_path = os.path.join(ENRICHMENTS_DIR, args.llm_run, "metadata.json")
        if os.path.exists(meta_path):
            with open(meta_path) as f:
                llm_run_meta = json.load(f)
        logger.info(f"Loaded LLM run '{args.llm_run}': {len(llm_run_data)} enrichments")

    # Load data
    docs = load_training_data(args.listing_type, args.property_type)
    if len(docs) < 50:
        logger.error(f"Only {len(docs)} samples -- need at least 50 to train.")
        sys.exit(1)

    # Build DataFrame
    df = build_dataframe(docs, llm_run=llm_run_data)
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
        results["llm_run_meta"] = llm_run_meta

    # Save
    save_artifacts(results, args.property_type, args.listing_type, config)

    logger.info("Done.")


if __name__ == "__main__":
    main()
