import math
import re
from pathlib import Path
from typing import Any

import joblib
import numpy as np

from src.config import settings
from src.ml.locality_resolver import is_gozo, resolve_locality
from src.ml.location_features import compute_location_features

FURNISHING_MAP = {"unknown": 0, "unfurnished": 1, "partly_furnished": 2, "furnished": 3}
VIEW_MAP = {
    "unknown": 0, "none": 0, "garden": 1, "pool": 1,
    "city": 2, "valley": 3, "harbour": 4, "sea": 5,
}
QUALITY_MAP = {"budget": 1, "standard": 2, "premium": 3, "luxury": 4}
CONSTRUCTION_MAP = {"unknown": 0, "off_plan": 1, "under_construction": 2, "completed": 3}
RENOVATION_ERA_MAP = {"unknown": 0, "dated": 1, "recent": 2, "modern": 3}
PARKING_MAP = {
    "unknown": 0, "none": 0, "street": 1, "car_space": 2, "garage": 3, "double_garage": 4,
}
OUTDOOR_MAP = {
    "unknown": 0, "none": 0, "balcony": 1, "yard": 2,
    "garden": 3, "terrace": 4, "roof_terrace": 5,
}
FLOOR_CAT_MAP = {"unknown": 0, "ground": 1, "low": 2, "mid": 3, "high": 4, "penthouse_level": 5}
KITCHEN_MAP = {"unknown": 0, "kitchenette": 1, "separate": 2, "open_plan": 3}
ORIENTATION_MAP = {"unknown": 0, "north": 1, "west": 2, "east": 3, "south": 4}
CEILING_MAP = {"unknown": 0, "normal": 1, "high": 2, "double": 3}
NOISE_MAP = {"unknown": 0, "busy": 1, "moderate": 2, "quiet": 3}
LEASE_MAP = {"unknown": 0, "leasehold": 1, "freehold": 2}
FLOORING_MAP = {"unknown": 0, "concrete": 1, "tiles": 2, "wood": 3, "marble": 4}
CONSTRUCTION_TYPE_MAP = {"panel": 1, "epk": 2, "brick": 3}

LLM_NUMERIC_FEATURES = [
    "llm_condition",
    "llm_floor",
    "llm_total_floors",
    "llm_outdoor_sqm",
    "llm_building_units",
    "llm_interior_score",
    "llm_kitchen_score",
    "llm_bathroom_score",
    "llm_exterior_condition",
    "llm_street_quality",
]
LLM_BOOLEAN_FEATURES = [
    "llm_bright",
    "llm_quiet",
    "llm_sea_proximity",
    "llm_is_investment",
    "llm_is_new_build",
    "llm_has_storage",
]
LLM_MAPPED_FEATURES = {
    "llm_furnishing": FURNISHING_MAP,
    "llm_view": VIEW_MAP,
    "llm_quality_tier": QUALITY_MAP,
    "llm_construction_status": CONSTRUCTION_MAP,
    "llm_parking_type": PARKING_MAP,
    "llm_outdoor_space": OUTDOOR_MAP,
    "llm_floor_category": FLOOR_CAT_MAP,
    "llm_kitchen_type": KITCHEN_MAP,
    "llm_orientation": ORIENTATION_MAP,
    "llm_ceiling_height": CEILING_MAP,
    "llm_noise_exposure": NOISE_MAP,
    "llm_lease_type": LEASE_MAP,
    "llm_renovation_era": RENOVATION_ERA_MAP,
    "llm_flooring_type": FLOORING_MAP,
}


# Training-typical values (medians over clean Malta apartment-sale rows) for
# structural features the public form may omit. total_int_area is imputed from
# area_sqm separately (they're near-identical for apartments).
_STRUCT_IMPUTE = {"total_ext_area": 10.0, "rooms": 6.0, "bathrooms": 2.0, "bedrooms": 2.0}


def _artifact_dir() -> Path:
    configured = Path(settings.model_artifacts_dir)
    if configured.exists():
        return configured
    repo_dir = Path(__file__).resolve().parents[3] / "ml" / "artifacts"
    if repo_dir.exists():
        return repo_dir
    return configured


def _resolve_version(prefix: str) -> str:
    """Newest version for which the FULL quartet (lgb, xgb, encoders, meta) exists.

    Selecting model + metadata by one coherent version prevents shipping a model
    paired with a different version's metadata (e.g. after a partial rollback that
    leaves a stale meta_v*.json behind).
    """
    d = _artifact_dir()
    suffixes = {"lgb": "joblib", "xgb": "joblib", "encoders": "joblib", "meta": "json"}
    have: dict[str, set[str]] = {}
    for suffix, ext in suffixes.items():
        pat = re.compile(rf"^{re.escape(prefix)}_{suffix}_v(.+)\.{ext}$")
        have[suffix] = {
            m.group(1) for p in d.glob(f"{prefix}_{suffix}_v*.{ext}")
            if (m := pat.match(p.name))
        }
    complete = have["lgb"] & have["xgb"] & have["encoders"] & have["meta"]
    if not complete:
        raise FileNotFoundError(f"No complete artifact quartet for {prefix} in {d}")
    return sorted(complete)[-1]


def _as_float(value: Any) -> float:
    if value is None or value == "":
        return np.nan
    try:
        return float(value)
    except (TypeError, ValueError):
        return np.nan


def _bool_float(value: Any) -> float:
    if value is None:
        return np.nan
    return 1.0 if bool(value) else 0.0


class ArtifactValuationPredictor:
    def __init__(self):
        self._cache: dict[str, dict[str, Any]] = {}

    def _load(self, listing_type: str) -> dict[str, Any]:
        listing_type = listing_type.lower()
        if listing_type not in {"sale", "rent"}:
            raise ValueError("listing_type must be sale or rent")
        if listing_type in self._cache:
            return self._cache[listing_type]

        prefix = f"mt_apartment_{listing_type}"
        import json

        d = _artifact_dir()
        version = _resolve_version(prefix)
        meta = json.loads((d / f"{prefix}_meta_v{version}.json").read_text())
        loaded = {
            "lgb": joblib.load(d / f"{prefix}_lgb_v{version}.joblib"),
            "xgb": joblib.load(d / f"{prefix}_xgb_v{version}.joblib"),
            "encoders": joblib.load(d / f"{prefix}_encoders_v{version}.joblib"),
            "meta": meta,
            "version": meta.get("version") or version,
        }
        self._cache[listing_type] = loaded
        return loaded

    def build_features(
        self,
        payload: dict[str, Any],
        enriched: dict[str, Any],
        lat: float,
        lon: float,
        locality: str | None,
    ) -> tuple[np.ndarray, list[str], list[str]]:
        loaded = self._load(str(payload["listing_type"]))
        feature_names = loaded["meta"]["feature_names"]
        values = {name: np.nan for name in feature_names}
        missing: list[str] = []

        area = _as_float(payload.get("area_sqm"))
        actual_area = _as_float(enriched.get("actual_living_area"))
        if not math.isnan(actual_area) and actual_area > 10:
            area = actual_area

        values.update(
            {
                "lat": lat,
                "lon": lon,
                "area_sqm": area,
                "area_sqm_log": math.log(area) if area and not math.isnan(area) else np.nan,
                "bedrooms": _as_float(payload.get("bedrooms")),
                "bathrooms": _as_float(payload.get("bathrooms")),
                "rooms": _as_float(payload.get("rooms")),
                "total_int_area": _as_float(payload.get("total_int_area")),
                "total_ext_area": _as_float(payload.get("total_ext_area")),
                "struct_floor": _as_float(payload.get("floor")),
                "struct_total_floors": _as_float(payload.get("total_floors")),
                "listing_age_days": np.nan,
                "listing_year": np.nan,
                "city_population": np.nan,
                "city_population_log": np.nan,
                "rental_density_2km": np.nan,
                "listing_score": np.nan,
                "construction_type": np.nan,
                "is_premium_zone": 0.0,
                "is_resort": 0.0,
                "is_gozo": 1.0 if is_gozo(lat) else 0.0,
                "is_near_beach": _bool_float(enriched.get("sea_proximity")),
                "is_seafront": 1.0 if enriched.get("view") == "sea" else 0.0,
                "is_sea_view": 1.0 if enriched.get("view") in {"sea", "harbour"} else 0.0,
                "is_quiet_road": _bool_float(enriched.get("quiet")),
                "is_city_center": 0.0,
                "is_countryside": 1.0 if enriched.get("view") == "valley" else 0.0,
            }
        )
        values.update(compute_location_features(lat, lon))

        values["has_balcony"] = _bool_float(payload.get("has_balcony"))
        values["has_pool"] = _bool_float(payload.get("has_pool"))
        values["has_lift"] = _bool_float(payload.get("has_elevator"))
        values["has_yard"] = _bool_float(payload.get("has_garden"))

        for name in LLM_NUMERIC_FEATURES:
            raw_key = name.removeprefix("llm_")
            values[name] = _as_float(enriched.get(raw_key))
        for name in LLM_BOOLEAN_FEATURES:
            raw_key = name.removeprefix("llm_")
            values[name] = _bool_float(enriched.get(raw_key))
        for name, mapping in LLM_MAPPED_FEATURES.items():
            raw_key = name.removeprefix("llm_")
            raw_value = enriched.get(raw_key)
            values[name] = float(mapping.get(raw_value, 0)) if raw_value is not None else np.nan

        encoders = loaded["encoders"]
        # Nominatim returns Maltese endonyms that don't match the anglicized
        # encoder keys; resolve (with a coordinate fallback) so locality_enc is
        # not silently NaN for the majority of real requests.
        resolved_locality = resolve_locality(locality, lat, lon, encoders["locality"].keys())
        if resolved_locality is not None:
            values["locality_enc"] = float(encoders["locality"][resolved_locality])
        else:
            missing.append("locality_enc")
        # province_enc is only ever populated at training time; flag it missing
        # only for models that actually use it (older, pre-serve-consistent models).
        if "province_enc" in feature_names:
            missing.append("province_enc")

        for required in [
            "bathrooms",
            "rooms",
            "total_int_area",
            "total_ext_area",
            "llm_condition",
            "llm_furnishing",
            "llm_quality_tier",
            "llm_construction_status",
        ]:
            if required in values and (values[required] is None or np.isnan(values[required])):
                missing.append(required)

        # Serve-time imputation. The public form omits features the model was
        # trained WITH (~always present in training), so raw NaN is out-of-distribution
        # and biases the trees high — the model is well-calibrated on complete inputs
        # and collapses on sparse ones. Fill missing STRUCTURAL features with
        # training-typical values so a sparse input lands in the normal operating range.
        def _is_nan(v: Any) -> bool:
            return v is None or (isinstance(v, float) and math.isnan(v))

        if _is_nan(values.get("total_int_area")) and area and not math.isnan(area):
            values["total_int_area"] = area  # internal area ~= total for apartments
        for feat, default in _STRUCT_IMPUTE.items():
            if feat in values and _is_nan(values[feat]):
                values[feat] = default

        vector = np.array([values[name] for name in feature_names], dtype=np.float64)
        return vector.reshape(1, -1), missing, feature_names

    def predict(
        self,
        payload: dict[str, Any],
        enriched: dict[str, Any],
        lat: float,
        lon: float,
        locality: str | None,
    ) -> dict[str, Any]:
        loaded = self._load(str(payload["listing_type"]))
        x, missing, feature_names = self.build_features(payload, enriched, lat, lon, locality)

        weights = loaded["meta"].get("ensemble_weights", {"lgb": 0.7, "xgb": 0.3})
        pred_log = (
            float(weights.get("lgb", 0.7)) * loaded["lgb"].predict(x)[0]
            + float(weights.get("xgb", 0.3)) * loaded["xgb"].predict(x)[0]
        )
        estimate = float(np.exp(pred_log))
        # Asking -> transaction adjustment (listings are asking prices).
        country = str(payload.get("country_code", "MT")).upper()
        estimate *= float(settings.adjustment_factors.get(country, 1.0))
        mape = float(loaded["meta"].get("cv_metrics", {}).get("mape_pct", 20.0)) / 100
        # Feature-aware band: widen for sparse inputs (each missing high-impact
        # feature adds uncertainty), so the range is honest rather than falsely tight.
        band = min(max(mape * 1.25, 0.12) + 0.02 * len(missing), 0.45)

        importances = loaded["meta"].get("feature_importance", {})
        total_importance = sum(float(v) for v in importances.values()) or 1.0

        return {
            "estimate": round(estimate, -2),
            "low": round(max(0, estimate * (1 - band)), -2),
            "high": round(estimate * (1 + band), -2),
            "missing_features": sorted(set(missing)),
            "feature_importance": {
                name: round(float(value) / total_importance, 3)
                for name, value in sorted(
                    importances.items(), key=lambda item: float(item[1]), reverse=True
                )[:20]
            },
            "model_version": f"mt_apartment_{payload['listing_type']}_v{loaded['version']}",
            "feature_names": feature_names,
        }


# Module-level singleton so each worker process loads the LGB+XGB models once
# (into its instance cache) and reuses them across jobs, rather than cold-loading
# the artifacts from disk on every valuation.
PREDICTOR = ArtifactValuationPredictor()
