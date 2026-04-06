"""Build feature matrix from database for model training."""

import logging

import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text

logger = logging.getLogger(__name__)


def load_training_data(database_url: str, country_code: str) -> pd.DataFrame:
    """Load properties with prices for a given country."""
    sync_url = database_url.replace("+asyncpg", "")
    engine = create_engine(sync_url)

    query = text("""
        SELECT
            p.id,
            p.lat, p.lon,
            p.property_type, p.area_sqm,
            p.floor, p.total_floors, p.rooms, p.bedrooms, p.bathrooms,
            p.year_built, p.year_renovated, p.condition,
            p.has_parking, p.has_garden, p.has_pool, p.has_elevator, p.has_balcony,
            p.distance_coast_m, p.distance_center_m,
            p.price_adjusted_eur,
            p.price_type,
            p.listing_date, p.transaction_date,
            r.name as region_name
        FROM properties p
        LEFT JOIN regions r ON p.region_id = r.id
        JOIN countries c ON p.country_id = c.id
        WHERE c.code = :code
            AND p.price_adjusted_eur IS NOT NULL
            AND p.price_adjusted_eur > 0
            AND p.lat IS NOT NULL
            AND p.lon IS NOT NULL
            AND p.area_sqm IS NOT NULL
            AND p.area_sqm > 0
    """)

    df = pd.read_sql(query, engine, params={"code": country_code.upper()})
    engine.dispose()

    logger.info(f"Loaded {len(df)} properties for {country_code}")
    return df


def build_features(df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, list[str]]:
    """Build feature matrix X and target y from dataframe."""
    feature_names = []

    # Numeric features
    numeric_cols = [
        "lat", "lon", "area_sqm", "floor", "rooms", "bedrooms",
        "year_built", "distance_coast_m", "distance_center_m",
    ]

    X_parts = []
    for col in numeric_cols:
        vals = df[col].fillna(-1).values.reshape(-1, 1)
        X_parts.append(vals)
        feature_names.append(col)

    # One-hot: property_type
    prop_types = ["apartment", "house", "villa", "studio", "maisonette", "penthouse"]
    for pt in prop_types:
        X_parts.append((df["property_type"] == pt).astype(float).values.reshape(-1, 1))
        feature_names.append(f"type_{pt}")

    # One-hot: condition
    conditions = ["new", "excellent", "good", "needs_renovation"]
    for cond in conditions:
        X_parts.append((df["condition"] == cond).astype(float).values.reshape(-1, 1))
        feature_names.append(f"cond_{cond}")

    # Boolean amenities
    bool_cols = ["has_parking", "has_garden", "has_pool", "has_elevator", "has_balcony"]
    for col in bool_cols:
        X_parts.append(df[col].fillna(0).astype(float).values.reshape(-1, 1))
        feature_names.append(col)

    # Transaction type (transaction prices are more reliable)
    X_parts.append(
        (df["price_type"] == "transaction").astype(float).values.reshape(-1, 1)
    )
    feature_names.append("is_transaction")

    X = np.hstack(X_parts)
    y = df["price_adjusted_eur"].values

    return X, y, feature_names
