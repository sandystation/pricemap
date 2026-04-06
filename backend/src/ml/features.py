import numpy as np

# Feature names matching the training order
FEATURE_NAMES = [
    "lat",
    "lon",
    "area_sqm",
    "floor",
    "rooms",
    "bedrooms",
    "year_built",
    "type_apartment",
    "type_house",
    "type_villa",
    "type_studio",
    "type_maisonette",
    "type_penthouse",
    "cond_new",
    "cond_excellent",
    "cond_good",
    "cond_needs_renovation",
]

PROPERTY_TYPES = ["apartment", "house", "villa", "studio", "maisonette", "penthouse"]
CONDITIONS = ["new", "excellent", "good", "needs_renovation"]


def build_feature_vector(
    lat: float,
    lon: float,
    property_type: str,
    area_sqm: float,
    floor: int | None = None,
    rooms: int | None = None,
    bedrooms: int | None = None,
    year_built: int | None = None,
    condition: str | None = None,
) -> np.ndarray:
    """Build a feature vector for model prediction."""
    features = [
        lat,
        lon,
        area_sqm,
        floor if floor is not None else -1,  # -1 signals missing
        rooms if rooms is not None else -1,
        bedrooms if bedrooms is not None else -1,
        year_built if year_built is not None else -1,
    ]

    # One-hot encode property type
    for pt in PROPERTY_TYPES:
        features.append(1.0 if property_type == pt else 0.0)

    # One-hot encode condition
    for cond in CONDITIONS:
        features.append(1.0 if condition == cond else 0.0)

    return np.array(features, dtype=np.float64)
