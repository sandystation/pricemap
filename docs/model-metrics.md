# Model Metrics Log

Tracks training runs and their results to compare the impact of different preprocessing and feature engineering choices.

## Benchmarks & Target Metrics

### Industry AVMs

| System | MAPE | Data |
|--------|------|------|
| Zillow Zestimate | ~7% median | Millions of US transactions, tax records, MLS |
| HouseCanary | 5-8% | 6-model ensemble, massive US data |
| Redfin Estimate | 6-9% | Transaction-trained |
| Academic AVMs (typical) | 10-25% | Asking prices, limited features, 10K-200K samples |

### Target levels for PriceMap

| Level | MAPE | What it requires |
|-------|------|------------------|
| Current | 22-23% | Scraper data + LLM text features |
| Good (asking prices) | 15-18% | + distance features (coast, CBD), + image features, + more data sources |
| Very good | 10-15% | + transaction prices, + 50K+ samples, + GPBoost spatial effects |
| Industry-grade | 5-10% | Transaction data, tax records, repeat sales, massive dataset |

### Why our MAPE is higher than industry AVMs

1. **Asking prices, not transactions** -- asking prices have 5-15% more noise than closed sale prices. All industry AVMs train on actual transaction prices.
2. **Small dataset** -- 2,292 sales is tiny. Zillow has millions. Academic studies showing 10-15% MAPE typically have 50K-200K samples.
3. **Missing key features** -- floor level (71% missing), year built (0%), distance to coast/CBD (not computed), school quality data (not available).
4. **Strict spatial CV** -- our geographic fold splits prevent spatial data leakage. Standard k-fold would show ~5pp better MAPE but overestimates real-world accuracy.

### Prioritized next improvements (by expected impact)

| Priority | Improvement | Expected MAPE reduction | Effort |
|----------|-------------|------------------------|--------|
| 1 | Distance to coast + Valletta CBD | 1-3pp | Low |
| 2 | LLM image features (--with-images) | 1-2pp | Low (photos on disk) |
| 3 | Add MaltaPark data (needs geocoding) | 1-2pp | Medium |
| 4 | GPBoost spatial random effects | 1-3pp | Medium |
| 5 | Transaction price data (Malta PPR) | 3-5pp | High (paid/restricted) |

---

## Baseline (no LLM features) - 2026-04-08

Training script: `scripts/train_valuation.py`
Features: 19 (numeric + amenity booleans + target-encoded locality/province)
LLM enrichment: none
Model: LightGBM 0.7 + XGBoost 0.3 ensemble, log(price) target, 5-fold spatial CV

### Sales (apartment, mt_remax)

| Metric | Value |
|--------|-------|
| Samples | 2,292 |
| MAPE | 27.2% |
| R2 | 0.5217 |
| MAE | 152,444 EUR |
| Median AE | 74,101 EUR |
| Within 5% | 15.4% |
| Within 10% | 28.7% |
| Within 15% | 39.9% |
| Within 20% | 50.1% |
| Within 25% | 59.4% |

Top features: total_int_area, area_sqm, total_ext_area, locality_enc, lat, lon

### Rents (apartment, mt_remax)

| Metric | Value |
|--------|-------|
| Samples | 9,395 |
| MAPE | 26.4% |
| R2 | 0.4165 |
| MAE | 431 EUR |
| Median AE | 295 EUR |
| Within 5% | 13.1% |
| Within 10% | 25.8% |
| Within 15% | 37.7% |
| Within 20% | 49.1% |
| Within 25% | 58.8% |

Top features: rooms, area_sqm, lon, lat, locality_enc, bedrooms

---

## After LLM enrichment (text-only) - 2026-04-08

LLM run: `20260408_gemini31flashlitepreview_text_baseline`
LLM provider/model: Google / gemini-3.1-flash-lite-preview
Mode: text-only, 10 parallel workers, 32,047 docs enriched, 0 errors, ~68 min
Cost: ~$0.70
Additional features: llm_condition, llm_floor, llm_total_floors, llm_furnishing, llm_view, llm_quality_tier, llm_bright, llm_quiet, llm_sea_proximity

### Sales (apartment, mt_remax)

| Metric | Value | vs Baseline |
|--------|-------|-------------|
| Samples | 2,292 | |
| MAPE | 23.2% | **-4.0pp** |
| R2 | 0.5805 | **+0.059** |
| MAE | 134,068 EUR | **-12.1%** |
| Median AE | 63,401 EUR | **-14.4%** |
| Within 5% | 16.1% | +0.7pp |
| Within 10% | 31.5% | +2.8pp |
| Within 15% | 45.2% | +5.3pp |
| Within 20% | 55.8% | **+5.7pp** |
| Within 25% | 65.1% | **+5.7pp** |

### Rents (apartment, mt_remax)

| Metric | Value | vs Baseline |
|--------|-------|-------------|
| Samples | 9,395 | |
| MAPE | 22.3% | **-4.1pp** |
| R2 | 0.5676 | **+0.151** |
| MAE | 364 EUR | **-15.5%** |
| Median AE | 242 EUR | **-18.0%** |
| Within 5% | 15.9% | +2.8pp |
| Within 10% | 32.1% | **+6.3pp** |
| Within 15% | 45.9% | +8.2pp |
| Within 20% | 57.2% | **+8.1pp** |
| Within 25% | 66.5% | **+7.7pp** |

---

## After LLM + distance + OSM features - 2026-04-08

Added: dist_coast_km, dist_cbd_km (Valletta), dist_school_km, dist_bus_km, dist_supermarket_km, dist_restaurant_km, dist_hospital_km, dist_pharmacy_km, dist_park_km, dist_worship_km, poi_count_500m, dining_count_500m
OSM data: 2,305 POIs across 10 categories from Overpass API (cached in data/osm_cache/)

### Sales (apartment, mt_remax)

| Metric | Value | vs Baseline | vs LLM-only |
|--------|-------|-------------|-------------|
| MAPE | 23.5% | -3.7pp | +0.3pp |
| R2 | 0.5605 | +0.039 | -0.020 |
| MAE | 136,810 EUR | -10.2% | +2.0% |
| Within 10% | 32.7% | +4.0pp | +1.2pp |
| Within 20% | 55.8% | +5.7pp | 0 |

### Rents (apartment, mt_remax)

| Metric | Value | vs Baseline | vs LLM-only |
|--------|-------|-------------|-------------|
| MAPE | 21.6% | **-4.8pp** | **-0.7pp** |
| R2 | 0.5828 | **+0.166** | **+0.015** |
| MAE | 355 EUR | **-17.6%** | **-2.5%** |
| Within 10% | 32.8% | +7.0pp | +0.7pp |
| Within 20% | 58.0% | +8.9pp | +0.8pp |

Note: OSM distance features benefit the rent model more than sales. Renters are more sensitive to transit, dining, and supermarket proximity.

---

## After LLM enrichment (with images) + dist + OSM + premium zone - 2026-04-09

LLM run: `images_gemini31flash`
LLM provider/model: Google / gemini-3.1-flash-lite-preview
Mode: with-images (up to 6 photos per listing), 10 parallel workers, 31,960 docs enriched
Additional features over text-only: llm_interior_score, llm_renovation_era, llm_photo_view
Also includes: dist_coast_km, dist_cbd_km, 10 OSM distance/density features, is_premium_zone

### Sales (apartment, mt_remax)

| Metric | Value | vs Baseline | vs text-only |
|--------|-------|-------------|-------------|
| MAPE | 23.3% | **-3.9pp** | -0.1pp |
| R2 | 0.6143 | **+0.092** | **+0.033** |
| MAE | 129,027 EUR | **-15.4%** | -3.8% |
| Within 5% | 17.1% | +1.7pp | +1.0pp |
| Within 10% | 33.5% | **+4.8pp** | +2.0pp |
| Within 20% | 56.6% | **+6.5pp** | +0.8pp |

### Rents (apartment, mt_remax)

| Metric | Value | vs Baseline | vs text-only |
|--------|-------|-------------|-------------|
| MAPE | 20.9% | **-5.5pp** | **-1.4pp** |
| R2 | 0.6306 | **+0.214** | **+0.063** |
| MAE | 337 EUR | **-21.8%** | **-7.4%** |
| Within 5% | 17.0% | +3.9pp | +1.1pp |
| Within 10% | 33.5% | **+7.7pp** | +1.4pp |
| Within 20% | 59.9% | **+10.8pp** | +2.7pp |

---

## V2 expanded features (26 LLM fields) + images + dist + OSM - 2026-04-09

LLM run: `v2_expanded_images`
LLM provider/model: Google / gemini-3.1-flash-lite-preview
Mode: with-images (up to 20 photos), 20 parallel workers, 32,051 docs, 0 errors, ~96 min
New text features: parking_type, outdoor_space, outdoor_sqm, floor_category, building_units, kitchen_type, orientation, is_investment, is_new_build, has_storage, ceiling_height, noise_exposure, lease_type
New image features: kitchen_score, bathroom_score, flooring_type, exterior_condition, street_quality
Total features in model: 61

### Sales (apartment, mt_remax)

| Metric | Value | vs Baseline | vs v1 images |
|--------|-------|-------------|-------------|
| MAPE | 23.1% | **-4.1pp** | -0.2pp |
| R2 | 0.6024 | **+0.080** | -0.012 |
| MAE | 131,610 EUR | **-13.7%** | +2.0% |
| Within 5% | 18.0% | **+2.6pp** | +0.9pp |
| Within 10% | 31.6% | +2.9pp | -1.9pp |
| Within 20% | 54.4% | +4.3pp | -2.2pp |

### Rents (apartment, mt_remax)

| Metric | Value | vs Baseline | vs v1 images |
|--------|-------|-------------|-------------|
| MAPE | 20.3% | **-6.1pp** | **-0.6pp** |
| R2 | 0.6485 | **+0.232** | **+0.018** |
| MAE | 328 EUR | **-23.9%** | **-2.7%** |
| Within 5% | 17.7% | +4.6pp | +0.7pp |
| Within 10% | 34.4% | **+8.6pp** | +0.9pp |
| Within 20% | 61.4% | **+12.3pp** | **+1.5pp** |

---

## Stratified spatial CV + LightGBM native categorical encoding - 2026-04-09

Changes: (1) Stratified spatial CV that distributes Gozo across all folds instead of isolating it. (2) Replaced target encoding of locality/province with LightGBM native categorical feature support (label encoding + `categorical_feature` parameter). LightGBM learns optimal municipality groupings rather than collapsing each to a mean-price number. Added `is_gozo` boolean feature.

### Sales (apartment, mt_remax)

| Metric | Value | vs Baseline |
|--------|-------|-------------|
| MAPE | **17.9%** | **-9.3pp** |
| R2 | 0.6168 | **+0.095** |
| MAE | 118,483 EUR | **-22.3%** |
| Within 5% | 20.6% | +5.2pp |
| Within 10% | 38.8% | **+10.1pp** |
| Within 20% | 65.2% | **+15.1pp** |
| Within 25% | 75.5% | **+16.1pp** |

After adding dist_beach_km, dist_marina_km, dist_airport_km, dist_sliema_km, dist_stjulians_km:

### Sales (apartment, mt_remax) -- CURRENT BEST

| Metric | Value | vs Baseline |
|--------|-------|-------------|
| MAPE | **17.0%** | **-10.2pp** |
| R2 | 0.6339 | **+0.112** |
| MAE | 113,333 EUR | **-25.7%** |
| Within 5% | 21.4% | +6.0pp |
| Within 10% | 39.1% | **+10.4pp** |
| Within 20% | 67.2% | **+17.1pp** |
| Within 25% | 78.1% | **+18.7pp** |

### Rents (apartment, mt_remax) -- CURRENT BEST

| Metric | Value | vs Baseline |
|--------|-------|-------------|
| MAPE | **18.2%** | **-8.2pp** |
| R2 | 0.6480 | **+0.231** |
| MAE | 317 EUR | **-26.5%** |
| Within 5% | 18.2% | +5.1pp |
| Within 10% | 35.1% | **+9.3pp** |
| Within 20% | 63.7% | **+14.6pp** |
| Within 25% | 74.5% | **+15.7pp** |

---

## Geocoded location references - 2026-04-09

LLM run: `v3_with_locref` (added `location_reference` field to extraction prompt)
Geocoding: 185/1339 unique references geocoded via Nominatim, covering ~3,500 docs
Refined coordinates: 183 sale docs (8%), 471 rent docs (5%)

### Sales (apartment, mt_remax) -- CURRENT BEST

| Metric | Value | vs Baseline |
|--------|-------|-------------|
| MAPE | **16.2%** | **-11.0pp** |
| R2 | 0.6450 | **+0.123** |
| MAE | 112,244 EUR | **-26.4%** |
| Within 5% | 21.5% | +6.1pp |
| Within 10% | 41.6% | **+12.9pp** |
| Within 20% | 71.3% | **+21.2pp** |
| Within 25% | 80.1% | **+20.7pp** |

### Rents (apartment, mt_remax)

| Metric | Value | vs Baseline | Note |
|--------|-------|-------------|------|
| MAPE | 18.8% | -7.6pp | Slight regression vs v2 (18.2%) -- geocoded coords may add noise for rents |
| R2 | 0.6067 | +0.190 | |
| Within 20% | 62.2% | +13.1pp | |

Note: For rents, the v2_expanded_images run without geocoding (MAPE 18.2%) remains the best model.
