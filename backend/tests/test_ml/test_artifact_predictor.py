import numpy as np

from src.ml.artifact_predictor import ArtifactValuationPredictor
from src.services.llm_enrichment_service import parse_enrichment_response


def test_parse_enrichment_response_clamps_scores():
    parsed = parse_enrichment_response(
        """
        {
          "condition": 8,
          "floor": 3,
          "total_floors": 8,
          "furnishing": "furnished",
          "view": "sea",
          "construction_status": "completed",
          "quality_tier": "premium",
          "bright": true,
          "quiet": false,
          "sea_proximity": true,
          "parking_type": "garage",
          "outdoor_space": "terrace",
          "outdoor_sqm": 12,
          "floor_category": "mid",
          "building_units": 10,
          "kitchen_type": "open_plan",
          "orientation": "south",
          "is_investment": false,
          "is_new_build": false,
          "has_storage": true,
          "ceiling_height": "normal",
          "noise_exposure": "quiet",
          "lease_type": "freehold",
          "location_reference": "Tower Road",
          "actual_living_area": 95,
          "is_house_floor": false,
          "area_includes_extra": false,
          "data_quality_note": null
        }
        """,
        with_images=False,
    )

    assert parsed is not None
    assert parsed["condition"] == 5
    assert parsed["view"] == "sea"


def test_artifact_feature_vector_matches_latest_sale_model_shape():
    predictor = ArtifactValuationPredictor()
    enriched = {
        "condition": 4,
        "floor": 3,
        "total_floors": 8,
        "furnishing": "furnished",
        "view": "sea",
        "construction_status": "completed",
        "quality_tier": "premium",
        "bright": True,
        "quiet": True,
        "sea_proximity": True,
        "parking_type": "garage",
        "outdoor_space": "terrace",
        "floor_category": "mid",
        "is_investment": False,
        "is_new_build": False,
        "has_storage": True,
    }
    payload = {
        "listing_type": "sale",
        "area_sqm": 100,
        "bedrooms": 2,
        "bathrooms": 2,
        "rooms": 4,
        "total_int_area": 90,
        "total_ext_area": 10,
        "floor": 3,
        "total_floors": 8,
        "has_balcony": True,
        "has_pool": False,
        "has_elevator": True,
        "has_garden": False,
    }

    vector, _, feature_names = predictor.build_features(
        payload=payload,
        enriched=enriched,
        lat=35.9116,
        lon=14.5027,
        locality="Sliema",
    )
    model = predictor._load("sale")["lgb"]

    assert vector.shape == (1, len(feature_names))
    assert vector.shape[1] == model.n_features_in_
    assert np.isfinite(vector[0][feature_names.index("area_sqm")])
