import logging
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)

MODEL_DIR = Path(__file__).parent / "models"


class PricePredictor:
    """Loads trained models and runs inference for property valuation."""

    def __init__(self):
        self._models: dict = {}
        self._load_models()

    def _load_models(self):
        """Load serialized model artifacts per country."""
        for model_file in MODEL_DIR.glob("*.joblib"):
            country_code = model_file.stem.split("_")[0].upper()
            try:
                import joblib

                self._models[country_code] = joblib.load(model_file)
                logger.info(f"Loaded model for {country_code}: {model_file.name}")
            except Exception as e:
                logger.warning(f"Failed to load model {model_file}: {e}")

    def has_model(self, country_code: str) -> bool:
        return country_code.upper() in self._models

    def predict(
        self,
        country_code: str,
        lat: float,
        lon: float,
        property_type: str,
        area_sqm: float,
        floor: int | None = None,
        rooms: int | None = None,
        bedrooms: int | None = None,
        year_built: int | None = None,
        condition: str | None = None,
        comparables: list | None = None,
        confidence_score: float = 50.0,
    ) -> dict:
        """
        Predict property price. Uses ML model if available, falls back to comparables.
        """
        country_code = country_code.upper()

        # If we have a trained model and sufficient confidence, use it
        if self.has_model(country_code) and confidence_score >= 30:
            return self._model_predict(
                country_code=country_code,
                lat=lat,
                lon=lon,
                property_type=property_type,
                area_sqm=area_sqm,
                floor=floor,
                rooms=rooms,
                bedrooms=bedrooms,
                year_built=year_built,
                condition=condition,
            )

        # Fallback: comparable-based estimation
        return self._comparables_predict(
            area_sqm=area_sqm,
            comparables=comparables or [],
        )

    def _model_predict(
        self,
        country_code: str,
        lat: float,
        lon: float,
        property_type: str,
        area_sqm: float,
        floor: int | None,
        rooms: int | None,
        bedrooms: int | None,
        year_built: int | None,
        condition: str | None,
    ) -> dict:
        """Run ML model inference."""
        from src.ml.features import build_feature_vector

        features = build_feature_vector(
            lat=lat,
            lon=lon,
            property_type=property_type,
            area_sqm=area_sqm,
            floor=floor,
            rooms=rooms,
            bedrooms=bedrooms,
            year_built=year_built,
            condition=condition,
        )

        model = self._models[country_code]

        # Predict median, low (10th percentile), high (90th percentile)
        estimate = float(model.predict(features.reshape(1, -1))[0])

        # Use model's quantile predictions if available, else approximate
        if hasattr(model, "predict_quantile"):
            low = float(model.predict_quantile(features.reshape(1, -1), 0.1)[0])
            high = float(model.predict_quantile(features.reshape(1, -1), 0.9)[0])
        else:
            low = estimate * 0.85
            high = estimate * 1.15

        return {
            "estimate": round(estimate, -2),  # Round to nearest 100
            "low": round(low, -2),
            "high": round(high, -2),
            "method": "model",
            "model_version": f"{country_code.lower()}_v1",
            "feature_importance": self._get_feature_importance(country_code),
            "data_freshness": None,
        }

    def _comparables_predict(self, area_sqm: float, comparables: list) -> dict:
        """Estimate from comparable properties using inverse-distance weighting."""
        if not comparables:
            # No data at all -- return a very rough estimate
            return {
                "estimate": 0,
                "low": 0,
                "high": 0,
                "method": "no_data",
                "model_version": "none",
                "feature_importance": {},
                "data_freshness": None,
            }

        prices_per_sqm = []
        weights = []
        for comp in comparables:
            if hasattr(comp, "price_per_sqm"):
                psqm = comp.price_per_sqm
                dist = max(comp.distance_m, 100)  # Minimum 100m to avoid division issues
            else:
                psqm = comp.get("price_per_sqm", 0)
                dist = max(comp.get("distance_m", 1000), 100)

            if psqm > 0:
                prices_per_sqm.append(psqm)
                weights.append(1.0 / dist)

        if not prices_per_sqm:
            return {
                "estimate": 0,
                "low": 0,
                "high": 0,
                "method": "no_data",
                "model_version": "none",
                "feature_importance": {},
                "data_freshness": None,
            }

        arr = np.array(prices_per_sqm)
        w = np.array(weights)
        w = w / w.sum()

        weighted_avg = float(np.average(arr, weights=w))
        estimate = weighted_avg * area_sqm

        std = float(np.std(arr)) * area_sqm
        low = max(estimate - 1.5 * std, estimate * 0.75)
        high = estimate + 1.5 * std

        return {
            "estimate": round(estimate, -2),
            "low": round(low, -2),
            "high": round(high, -2),
            "method": "comparables",
            "model_version": "comparables_v1",
            "feature_importance": {"location": 0.5, "area_sqm": 0.3, "comparables": 0.2},
            "data_freshness": None,
        }

    def _get_feature_importance(self, country_code: str) -> dict[str, float]:
        """Extract feature importance from trained model."""
        model = self._models.get(country_code)
        if model and hasattr(model, "feature_importances_"):
            from src.ml.features import FEATURE_NAMES

            importances = model.feature_importances_
            total = sum(importances)
            if total > 0:
                return {
                    name: round(float(imp / total), 3)
                    for name, imp in zip(FEATURE_NAMES, importances)
                }
        return {}
