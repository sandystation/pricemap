"""
Calculate rental yields for sale listings using the rent model predictions.

For each property on sale, predicts the expected monthly rent using the trained
rent model, then calculates gross rental yield = (annual_rent / sale_price) * 100.

Usage (run from scripts/ directory):
    python rental_yields.py --country BG                          # all BG cities
    python rental_yields.py --country BG --city Sofia             # Sofia only
    python rental_yields.py --country BG --city Sofia --top 20    # top 20
    python rental_yields.py --country BG --min-yield 8            # yield > 8%
    python rental_yields.py --country MT                          # Malta
"""

import argparse
import logging
import os
import sys

import joblib
import numpy as np
import pandas as pd

from docstore import DocStore
from llm_enrich import load_run
from train_valuation import (
    build_dataframe, get_feature_names, load_training_data,
    _build_feature_matrix, NUMERIC_FEATURES, AMENITY_FEATURES,
    EXTRA_NUMERIC_FEATURES, EXTRA_CATEGORICAL_FEATURES,
    LLM_NUMERIC_FEATURES, LLM_BOOLEAN_FEATURES, LLM_ORDINAL_FEATURES,
    LLM_CATEGORICAL_FEATURES, LLM_IMAGE_NUMERIC, LLM_IMAGE_ORDINAL,
    LLM_IMAGE_CATEGORICAL, LGBM_PARAMS, XGB_PARAMS, LGBM_WEIGHT, XGB_WEIGHT,
)
import lightgbm as lgb
import xgboost as xgb

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

ARTIFACTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "ml", "artifacts")

base_cols = (
    NUMERIC_FEATURES + AMENITY_FEATURES
    + EXTRA_NUMERIC_FEATURES + list(EXTRA_CATEGORICAL_FEATURES.keys())
    + LLM_NUMERIC_FEATURES + LLM_BOOLEAN_FEATURES
    + list(LLM_ORDINAL_FEATURES.keys())
    + list(LLM_CATEGORICAL_FEATURES.keys())
    + LLM_IMAGE_NUMERIC + list(LLM_IMAGE_ORDINAL.keys())
    + list(LLM_IMAGE_CATEGORICAL.keys())
)
all_cat_names = (
    ["locality_enc", "province_enc"]
    + list(EXTRA_CATEGORICAL_FEATURES.keys())
    + list(LLM_CATEGORICAL_FEATURES.keys())
    + list(LLM_IMAGE_CATEGORICAL.keys())
)


def train_rent_model(collections, llm_runs):
    """Train a rent model on the fly and return (lgb_model, xgb_model, feature_names, loc_codes_map, prov_codes_map)."""
    llm_data = {}
    for run in llm_runs:
        llm_data.update(load_run(run))

    coord_overrides = None
    try:
        from geocode_locations import build_coordinate_overrides
        coord_overrides = {}
        for run in llm_runs:
            try:
                coord_overrides.update(build_coordinate_overrides(run))
            except:
                pass
    except:
        pass

    docs = load_training_data("rent", "apartment", collections=collections)
    df = build_dataframe(docs, llm_run=llm_data, coord_overrides=coord_overrides)
    feature_names = get_feature_names()
    log_target = np.log(df["price_eur"].values)

    loc_cat = df["locality"].astype("category")
    prov_cat = df["province"].astype("category")
    loc_codes = loc_cat.cat.codes.values.astype(float)
    prov_codes = prov_cat.cat.codes.values.astype(float)
    cat_indices = [feature_names.index(c) for c in all_cat_names]

    X = _build_feature_matrix(df, base_cols, feature_names, loc_codes, prov_codes, np.arange(len(df)))

    p = {k: v for k, v in LGBM_PARAMS.items() if k != "early_stopping_rounds"}
    lgb_m = lgb.LGBMRegressor(**p)
    lgb_m.fit(X, log_target, categorical_feature=cat_indices)

    xp = {k: v for k, v in XGB_PARAMS.items() if k != "early_stopping_rounds"}
    xgb_m = xgb.XGBRegressor(**xp)
    xgb_m.fit(X, log_target, verbose=False)

    # Build locality/province -> code mapping
    loc_map = dict(zip(loc_cat, loc_codes))
    prov_map = dict(zip(prov_cat, prov_codes))

    logger.info(f"Rent model trained on {len(df)} samples")
    return lgb_m, xgb_m, feature_names, loc_map, prov_map, cat_indices


def predict_rent(lgb_m, xgb_m, feature_names, df_sale, loc_map, prov_map, cat_indices):
    """Predict monthly rent for sale properties using the rent model."""
    # Map sale localities to rent model's codes (with fallback for unseen localities)
    default_loc = np.nanmedian(list(loc_map.values()))
    default_prov = np.nanmedian(list(prov_map.values()))

    loc_codes = np.array([loc_map.get(l, default_loc) for l in df_sale["locality"]])
    prov_codes = np.array([prov_map.get(p, default_prov) for p in df_sale["province"]])

    X = _build_feature_matrix(df_sale, base_cols, feature_names, loc_codes, prov_codes, np.arange(len(df_sale)))

    pred_log = LGBM_WEIGHT * lgb_m.predict(X) + XGB_WEIGHT * xgb_m.predict(X)
    return np.exp(pred_log)


def calculate_yields(collections, llm_runs, city_filter=None, min_yield=0, top_n=20,
                     investable_only=False, max_age_days=365):
    """Calculate rental yields for sale properties."""
    # Load LLM data
    llm_data = {}
    for run in llm_runs:
        llm_data.update(load_run(run))

    coord_overrides = None
    try:
        from geocode_locations import build_coordinate_overrides
        coord_overrides = {}
        for run in llm_runs:
            try:
                coord_overrides.update(build_coordinate_overrides(run))
            except:
                pass
    except:
        pass

    # Train rent model
    logger.info("Training rent model...")
    lgb_m, xgb_m, feature_names, loc_map, prov_map, cat_indices = train_rent_model(collections, llm_runs)

    # Load sale properties
    logger.info("Loading sale properties...")
    sale_docs = load_training_data("sale", "apartment", collections=collections)
    df_sale = build_dataframe(sale_docs, llm_run=llm_data, coord_overrides=coord_overrides)

    # Filter by city if requested
    if city_filter:
        df_sale = df_sale[df_sale["locality"].str.contains(city_filter, case=False, na=False)]
        logger.info(f"Filtered to {len(df_sale)} sales in {city_filter}")

    if len(df_sale) == 0:
        logger.error("No sale properties to analyze")
        return

    # Predict rent
    logger.info(f"Predicting rents for {len(df_sale)} sale properties...")
    predicted_rent = predict_rent(lgb_m, xgb_m, feature_names, df_sale, loc_map, prov_map, cat_indices)

    df_sale = df_sale.copy()
    df_sale["predicted_rent"] = predicted_rent
    df_sale["annual_rent"] = predicted_rent * 12
    df_sale["gross_yield"] = (df_sale["annual_rent"] / df_sale["price_eur"] * 100).round(2)

    # Investable filter: remove listings that can't actually be rented
    if investable_only:
        before = len(df_sale)

        # 1. Must be completed (not under construction or off-plan)
        df_sale = df_sale[df_sale["llm_construction_status"] >= 3]  # 3 = completed

        # 2. Must be finished (condition >= 3 = good/standard)
        df_sale = df_sale[df_sale["llm_condition"] >= 3]

        # 3. Exclude listings older than max_age_days
        if "listing_age_days" in df_sale.columns:
            df_sale = df_sale[
                (df_sale["listing_age_days"].isna()) |
                (df_sale["listing_age_days"] <= max_age_days)
            ]

        # 4. VAT normalization: if excluded, reduce yield by 20%
        #    (price in training already adjusted, but yield calc used raw price)
        #    Actually the price_eur in df already has VAT adjustment from load_training_data
        #    So this is already handled. Just flag it in output.

        logger.info(f"Investable filter: {before} -> {len(df_sale)} "
                     f"(removed {before - len(df_sale)} under-construction/shell/stale)")

    # Filter by min yield
    df_sale = df_sale[df_sale["gross_yield"] >= min_yield]

    # Sort by yield descending
    df_sale = df_sale.sort_values("gross_yield", ascending=False)

    # Get URLs and LLM notes -- index by doc_id stored in the training docs
    store = DocStore()
    coll_name = collections[0]
    coll = store.collection(coll_name)
    coll._ensure_loaded()
    doc_info = {}  # doc_id -> {url, vat, note}
    for doc_id, doc in coll._docs.items():
        cur = doc.get("current", {})
        llm_note = llm_data.get(doc_id, {}).get("data_quality_note", "")
        doc_info[doc_id] = {
            "url": cur.get("url", ""),
            "vat": cur.get("vat_status", "?"),
            "note": llm_note,
        }
    store.close()

    # Print results
    print(f"\n{'='*110}")
    mode = "INVESTABLE ONLY" if investable_only else "ALL"
    print(f"  RENTAL YIELD ANALYSIS ({mode}) -- Top {min(top_n, len(df_sale))} properties")
    if city_filter:
        print(f"  City: {city_filter}")
    if investable_only:
        print(f"  Filters: completed, condition >= good, listed < {max_age_days} days")
    print(f"  {len(df_sale)} properties with yield >= {min_yield}%")
    print(f"{'='*110}")

    for i, (idx, row) in enumerate(df_sale.head(top_n).iterrows()):
        area = int(row["area_sqm"]) if not pd.isna(row["area_sqm"]) else "?"
        rooms = int(row["rooms"]) if not pd.isna(row["rooms"]) else "?"
        cond = int(row["llm_condition"]) if not pd.isna(row["llm_condition"]) else "?"
        cond_label = {1: "shell", 2: "reno", 3: "good", 4: "exc", 5: "lux"}.get(cond, "?")
        locality = str(row["locality"])[:25]

        did = row.get("_doc_id", "") if "_doc_id" in df_sale.columns else ""
        info = doc_info.get(did, {})
        url = info.get("url", "")
        vat = info.get("vat", "?")
        note = info.get("note", "")

        # Build warnings
        warnings = []
        if vat == "excluded":
            warnings.append("⚠ +VAT")
        if note and any(x in note.lower() for x in ["render", "3d", "not actual"]):
            warnings.append("⚠ renders")
        if note and any(x in note.lower() for x in ["common part", "attic", "basement"]):
            warnings.append("⚠ area")
        age = row.get("listing_age_days", 0)
        if not pd.isna(age) and age > 365:
            warnings.append(f"⚠ {int(age)}d old")

        warn_str = " ".join(warnings)

        print(
            f"{i+1:>3d}. {row['gross_yield']:>5.1f}% "
            f"EUR {row['price_eur']:>9,.0f} "
            f"→ EUR {row['predicted_rent']:>6,.0f}/m "
            f"| {area:>4}m² {rooms}rm {cond_label:>4s} "
            f"| {locality}"
        )
        if url or warn_str:
            print(f"     {url}  {warn_str}")
        print()

    # Summary stats
    print(f"\n--- Summary ---")
    print(f"Median yield: {df_sale['gross_yield'].median():.1f}%")
    print(f"Mean yield: {df_sale['gross_yield'].mean():.1f}%")
    print(f"Top quartile: >= {df_sale['gross_yield'].quantile(0.75):.1f}%")

    # By city
    if not city_filter:
        print(f"\n--- Median yield by city ---")
        city_yields = {}
        for _, row in df_sale.iterrows():
            loc = str(row["locality"])
            city = loc.split(",")[-1].strip() if "," in loc else loc
            if city not in city_yields:
                city_yields[city] = []
            city_yields[city].append(row["gross_yield"])

        for city in sorted(city_yields.keys(), key=lambda c: -np.median(city_yields[c])):
            if len(city_yields[city]) >= 10:
                med = np.median(city_yields[city])
                print(f"  {city:20s}: {med:.1f}% (n={len(city_yields[city])})")


def main():
    parser = argparse.ArgumentParser(description="Calculate rental yields for sale properties")
    parser.add_argument("--country", required=True, choices=["BG", "MT"], help="Country")
    parser.add_argument("--city", default=None, help="Filter by city name")
    parser.add_argument("--top", type=int, default=20, help="Number of top results (default: 20)")
    parser.add_argument("--min-yield", type=float, default=0, help="Minimum yield %% (default: 0)")
    parser.add_argument("--investable", action="store_true",
                        help="Only show genuinely investable: completed, finished, listed < 1 year")
    parser.add_argument("--max-age", type=int, default=365,
                        help="Max listing age in days (default: 365, used with --investable)")
    args = parser.parse_args()

    if args.country == "BG":
        collections = ["bg_imot"]
        llm_runs = ["bg_imot_v2_full"]
    elif args.country == "MT":
        collections = ["mt_remax"]
        llm_runs = ["v3_with_locref"]

    calculate_yields(collections, llm_runs, city_filter=args.city,
                     min_yield=args.min_yield, top_n=args.top,
                     investable_only=args.investable, max_age_days=args.max_age)


if __name__ == "__main__":
    main()
