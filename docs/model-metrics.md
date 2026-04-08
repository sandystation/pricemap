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

## After LLM enrichment (with images) - TBD

Additional features over text-only: llm_interior_score, llm_renovation_era, llm_photo_view

### Sales (apartment, mt_remax)

_To be filled._

### Rents (apartment, mt_remax)

_To be filled._
