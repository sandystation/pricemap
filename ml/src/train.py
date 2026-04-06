"""
Main training script for PriceMap valuation models.

Usage:
    python -m src.train --country MT
    python -m src.train --country BG
"""

import argparse
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

import joblib
import lightgbm as lgb
import numpy as np
import xgboost as xgb
from sklearn.model_selection import KFold

from src.config import (
    ARTIFACTS_DIR,
    DATABASE_URL,
    LGBM_PARAMS,
    LGBM_WEIGHT,
    MIN_SAMPLES,
    N_FOLDS,
    XGB_PARAMS,
    XGB_WEIGHT,
)
from src.feature_store import build_features, load_training_data

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def train_model(country_code: str):
    """Train valuation model for a specific country."""
    logger.info(f"Starting training for {country_code}")

    # Load data
    df = load_training_data(DATABASE_URL, country_code)
    if len(df) < MIN_SAMPLES:
        logger.error(
            f"Insufficient data for {country_code}: {len(df)} samples (need {MIN_SAMPLES})"
        )
        return

    X, y, feature_names = build_features(df)
    logger.info(f"Feature matrix: {X.shape}, target: {y.shape}")

    # Spatial cross-validation (using lat/lon to create geographic folds)
    # Sort by latitude to create geographic strips
    lat_order = np.argsort(X[:, 0])  # lat is first feature
    fold_indices = np.array_split(lat_order, N_FOLDS)

    kf_splits = []
    for i in range(N_FOLDS):
        test_idx = fold_indices[i]
        train_idx = np.concatenate([fold_indices[j] for j in range(N_FOLDS) if j != i])
        kf_splits.append((train_idx, test_idx))

    # Train LightGBM with cross-validation
    lgb_scores = []
    xgb_scores = []
    best_lgb = None
    best_xgb = None
    best_score = float("inf")

    for fold, (train_idx, test_idx) in enumerate(kf_splits):
        X_train, X_test = X[train_idx], X[test_idx]
        y_train, y_test = y[train_idx], y[test_idx]

        # LightGBM
        lgb_model = lgb.LGBMRegressor(**LGBM_PARAMS)
        lgb_model.fit(
            X_train, y_train,
            eval_set=[(X_test, y_test)],
        )
        lgb_pred = lgb_model.predict(X_test)
        lgb_mae = np.mean(np.abs(y_test - lgb_pred))
        lgb_scores.append(lgb_mae)

        # XGBoost
        xgb_model = xgb.XGBRegressor(**XGB_PARAMS)
        xgb_model.fit(
            X_train, y_train,
            eval_set=[(X_test, y_test)],
            verbose=False,
        )
        xgb_pred = xgb_model.predict(X_test)
        xgb_mae = np.mean(np.abs(y_test - xgb_pred))
        xgb_scores.append(xgb_mae)

        # Ensemble
        ensemble_pred = LGBM_WEIGHT * lgb_pred + XGB_WEIGHT * xgb_pred
        ensemble_mae = np.mean(np.abs(y_test - ensemble_pred))

        logger.info(
            f"Fold {fold+1}/{N_FOLDS}: LGB MAE={lgb_mae:.0f}, XGB MAE={xgb_mae:.0f}, "
            f"Ensemble MAE={ensemble_mae:.0f}"
        )

        if ensemble_mae < best_score:
            best_score = ensemble_mae
            best_lgb = lgb_model
            best_xgb = xgb_model

    # Retrain on full data for final model
    final_lgb = lgb.LGBMRegressor(**LGBM_PARAMS)
    final_lgb.fit(X, y)

    final_xgb = xgb.XGBRegressor(**XGB_PARAMS)
    final_xgb.fit(X, y, verbose=False)

    # Compute metrics
    avg_lgb_mae = np.mean(lgb_scores)
    avg_xgb_mae = np.mean(xgb_scores)
    median_price = np.median(y)
    mape = avg_lgb_mae / median_price * 100

    logger.info(f"Average LGB MAE: {avg_lgb_mae:.0f} EUR")
    logger.info(f"Average XGB MAE: {avg_xgb_mae:.0f} EUR")
    logger.info(f"MAPE: {mape:.1f}%")
    logger.info(f"Median price: {median_price:.0f} EUR")

    # Feature importance
    importance = dict(
        zip(feature_names, final_lgb.feature_importances_.tolist())
    )

    # Save artifacts
    os.makedirs(ARTIFACTS_DIR, exist_ok=True)
    cc = country_code.lower()
    version = datetime.now(timezone.utc).strftime("%Y%m%d")

    lgb_path = os.path.join(ARTIFACTS_DIR, f"{cc}_lgb_v{version}.joblib")
    xgb_path = os.path.join(ARTIFACTS_DIR, f"{cc}_xgb_v{version}.joblib")
    meta_path = os.path.join(ARTIFACTS_DIR, f"{cc}_meta_v{version}.json")

    joblib.dump(final_lgb, lgb_path)
    joblib.dump(final_xgb, xgb_path)

    # Also save as the "latest" model for the backend to load
    latest_path = os.path.join(ARTIFACTS_DIR, f"{cc}_v1.joblib")
    joblib.dump(final_lgb, latest_path)

    metadata = {
        "country_code": country_code.upper(),
        "version": version,
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "sample_count": len(df),
        "feature_names": feature_names,
        "metrics": {
            "lgb_mae": round(avg_lgb_mae, 2),
            "xgb_mae": round(avg_xgb_mae, 2),
            "mape_pct": round(mape, 2),
            "median_price": round(median_price, 2),
        },
        "feature_importance": importance,
    }

    with open(meta_path, "w") as f:
        json.dump(metadata, f, indent=2)

    logger.info(f"Saved models to {ARTIFACTS_DIR}")
    logger.info(f"  LGB: {lgb_path}")
    logger.info(f"  XGB: {xgb_path}")
    logger.info(f"  Meta: {meta_path}")
    logger.info(f"  Latest: {latest_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train PriceMap valuation model")
    parser.add_argument("--country", required=True, help="Country code (MT, BG, CY, HR)")
    args = parser.parse_args()

    train_model(args.country.upper())
