"""Model evaluation utilities."""

import numpy as np
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score


def evaluate_predictions(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    """Compute standard regression metrics."""
    mae = mean_absolute_error(y_true, y_pred)
    rmse = np.sqrt(mean_squared_error(y_true, y_pred))
    r2 = r2_score(y_true, y_pred)
    mape = np.mean(np.abs((y_true - y_pred) / y_true)) * 100
    median_ae = np.median(np.abs(y_true - y_pred))

    return {
        "mae": round(mae, 2),
        "rmse": round(rmse, 2),
        "r2": round(r2, 4),
        "mape_pct": round(mape, 2),
        "median_ae": round(median_ae, 2),
        "n_samples": len(y_true),
    }


def price_accuracy_buckets(
    y_true: np.ndarray, y_pred: np.ndarray
) -> dict[str, float]:
    """What percentage of predictions fall within X% of actual price."""
    errors_pct = np.abs((y_true - y_pred) / y_true) * 100

    return {
        "within_5pct": round(np.mean(errors_pct <= 5) * 100, 1),
        "within_10pct": round(np.mean(errors_pct <= 10) * 100, 1),
        "within_15pct": round(np.mean(errors_pct <= 15) * 100, 1),
        "within_20pct": round(np.mean(errors_pct <= 20) * 100, 1),
        "within_25pct": round(np.mean(errors_pct <= 25) * 100, 1),
    }
