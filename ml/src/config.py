"""Training configuration and hyperparameters."""

import os

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://pricemap:pricemap_dev@localhost:5432/pricemap"
)

ARTIFACTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "artifacts")

# LightGBM hyperparameters
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

# XGBoost hyperparameters (ensemble member)
XGB_PARAMS = {
    "objective": "reg:squarederror",
    "max_depth": 6,
    "learning_rate": 0.05,
    "n_estimators": 500,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "early_stopping_rounds": 50,
}

# Ensemble weights
LGBM_WEIGHT = 0.7
XGB_WEIGHT = 0.3

# Spatial cross-validation folds
N_FOLDS = 5

# Minimum samples required to train a model for a country
MIN_SAMPLES = 50
