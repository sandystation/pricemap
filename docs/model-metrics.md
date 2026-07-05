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

---

## Combined RE/MAX + MaltaPark training - 2026-04-09

Collections: mt_remax + mt_maltapark (2,619 samples vs 2,292 RE/MAX-only)
LLM runs: v3_with_locref (RE/MAX) + maltapark_v1_images (MaltaPark)
MaltaPark: geocoded via RE/MAX town centroids + Nominatim (97.5% coverage)

### Sales (apartment, combined)

| Metric | Value | vs RE/MAX-only best |
|--------|-------|---------------------|
| MAPE | 17.1% | +0.9pp |
| R2 | 0.6003 | -0.045 |
| MAE | 110,509 EUR | -1.5% |
| Within 20% | 67.6% | -3.7pp |

Note: Combined model slightly worse on MAPE/R2 due to MaltaPark's town-level-only coordinates and 22.8% area coverage. RE/MAX-only model (MAPE 16.2%) remains the best for sales. MaltaPark would benefit from property-level geocoding via location_reference + Nominatim.

---

## Bulgaria (bg_imot) apartment sales - 2026-04-10

Collection: bg_imot (9,805 docs, 6,569 trainable apartments after filtering)
Geocoding: 84.4% coverage via Nominatim (neighborhood + city → coordinates)
LLM run: bg_imot_v1_images (gemini-3.1-flash-lite-preview, with images, 9,751 enriched)

### Baseline (no LLM features)

| Metric | Value |
|--------|-------|
| Samples | 6,569 |
| MAPE | 27.1% |
| R2 | 0.5152 |
| MAE | 34,408 EUR |
| Within 10% | 25.4% |
| Within 20% | 48.7% |

### With LLM features

| Metric | Value | vs Baseline |
|--------|-------|-------------|
| MAPE | **23.7%** | **-3.4pp** |
| R2 | 0.5573 | +0.042 |
| MAE | 31,153 EUR | **-9.5%** |
| Within 10% | 31.7% | **+6.3pp** |
| Within 20% | 56.3% | **+7.6pp** |

### With stratified CV by locality -- CURRENT BEST

| Metric | Value | vs Baseline |
|--------|-------|-------------|
| MAPE | **12.9%** | **-14.2pp** |
| R2 | 0.8012 | **+0.286** |
| MAE | 18,747 EUR | **-45.5%** |
| Within 5% | 27.9% | +16.4pp |
| Within 10% | 50.6% | **+25.2pp** |
| Within 20% | 79.4% | **+30.7pp** |
### With stratified CV + city prefix + ppsqm filter -- CURRENT BEST

| Metric | Value | vs Baseline |
|--------|-------|-------------|
| MAPE | **12.6%** | **-14.5pp** |
| R2 | 0.8218 | **+0.307** |
| MAE | 18,107 EUR | **-47.4%** |
| Within 5% | 28.2% | +16.7pp |
| Within 10% | 52.0% | **+26.6pp** |
| Within 20% | 80.1% | **+31.4pp** |
| Within 25% | 88.0% | **+30.0pp** |

---

## Malta sales -- CURRENT BEST (2026-04-10)

Stratified CV by locality, price/sqm outlier filter (>30K or <100 EUR/sqm), geocoded location references

| Metric | Value | vs Baseline |
|--------|-------|-------------|
| MAPE | **12.1%** | **-15.1pp** |
| R2 | 0.7887 | **+0.267** |
| MAE | 83,573 EUR | **-45.2%** |
| Within 5% | 37.5% | +22.1pp |
| Within 10% | 59.3% | **+30.6pp** |
| Within 20% | 81.2% | **+31.1pp** |
| Within 25% | 87.0% | **+27.6pp** |

---

## Bulgaria (bg_imot) with full LLM enrichment + precise map coordinates - 2026-04-12

Collection: bg_imot (54,109 docs)
LLM run: `bg_imot_v2_full` (gemini-3.1-flash-lite-preview, with images, 52,183 enriched)
GPS: 99% precise map coordinates (map_lat/map_lon from imot.bg), fallback to neighborhood geocoding
Coordinate fallback: docs with only map_lat (no neighborhood lat) now included via fallback fix
Rental geocoding: fixed "Наеми в " prefix stripping for 17,470 rental localities

### Sales (apartment, bg_imot) -- CURRENT BEST

| Metric | Value | vs Previous BG Sale |
|--------|-------|---------------------|
| Samples | 7,615 | +1,046 (+16%) |
| MAPE | **12.1%** | -0.5pp |
| R2 | 0.8389 | +0.017 |
| MAE | 16,983 EUR | -6.2% |
| Median AE | 10,807 EUR | |
| Within 5% | 30.0% | +1.8pp |
| Within 10% | 53.8% | +1.8pp |
| Within 15% | 70.2% | |
| Within 20% | 82.0% | +1.9pp |
| Within 25% | 89.1% | +1.1pp |

### Rents (apartment, bg_imot) -- CURRENT BEST

| Metric | Value | vs Previous BG Rent |
|--------|-------|---------------------|
| Samples | 9,170 | +876 (+11%) |
| MAPE | **13.5%** | +0.2pp |
| R2 | 0.7496 | |
| MAE | 94 EUR | |
| Median AE | 57 EUR | |
| Within 5% | 26.0% | |
| Within 10% | 48.1% | |
| Within 15% | 65.8% | |
| Within 20% | 78.0% | |
| Within 25% | 85.8% | |

Note: Sale model improved slightly with 16% more training data from map_lat fallback. Rent model MAPE increased 0.2pp likely from newly included docs in industrial/suburban areas with less predictable rents. Both models now use full LLM enrichment from 52K docs (vs 9.7K in v1).

---

## Malta (mt_remax) serve-consistent retrain - 2026-07-03

LLM run: `mt_remax_v1_reproduce` (gemini-3.1-flash-lite-preview, text-only, 31,964 enriched)
Version: `v20260703` (supersedes `v20260628` via latest-glob; v20260628 retained for rollback)

**Why:** the audit found the v20260628 models were trained with features that are
always `NaN` at serve time (the public form never provides them): `listing_age_days`
(the #1 feature), `listing_score`, `listing_year`, `city_population(_log)`,
`rental_density_2km`, `construction_type`, `province_enc`, and 10 RE/MAX-only
amenity booleans (`has_ac`, `has_ensuite`, ...). This train/serve skew made the
reported CV MAPE optimistic vs real production accuracy. The serve-consistent
models exclude those 18 features (98 -> 79) so CV metrics reflect what the form
actually delivers, trained via `--serve-consistent`.

### Sales (apartment, mt_remax) -- serve-consistent

| Metric | v20260703 (serve-consistent) | v20260628 (inflated CV) |
|--------|------------------------------|-------------------------|
| Samples | 2,179 | 2,179 |
| Features | 79 | 97 |
| MAPE | **12.2%** (honest) | 11.8% (relied on serve-absent features) |
| R2 | 0.776 | 0.774 |
| Within 10% | 59.2% | 61.7% |
| Within 20% | 81.3% | 82.2% |

### Rents (apartment, mt_remax) -- serve-consistent

| Metric | v20260703 (serve-consistent) | v20260628 (inflated CV) |
|--------|------------------------------|-------------------------|
| Samples | 9,470 | 9,470 |
| Features | 79 | 97 |
| MAPE | **18.2%** (honest) | 16.2% (relied on serve-absent features) |
| R2 | 0.662 | 0.704 |
| Within 10% | 36.4% | 40.6% |
| Within 20% | 65.1% | 69.8% |

Note: The serve-consistent CV numbers are the honest production estimate -- every
feature is available at inference. Sale is unchanged in practice (12.2% vs 11.8%),
confirming the dropped features added little real value. Rent MAPE rises ~2pp on
paper (16.2% -> 18.2%), but this reflects *removing an illusion*: the audit measured
the old model's real serve-time rent within-10% at ~37%, essentially identical to
the new model's honest 36.4% -- production was already at ~this level; the old 16.2%
just hid it. The new models also carry no `province_enc` confidence penalty at serve.
Follow-up to recover accuracy honestly: collect the dropped amenities in the form,
or compute `city_population`/`rental_density_2km` server-side, then re-add them.

---

## Malta improvement exploration - 2026-07-03

Explored improvement levers for the serve-consistent v20260703 models (5-avenue
analysis + measured each with `train_valuation.py --eval-only`). Outcome:

**Training levers — no material accuracy gain (rent is at its noise floor).**
Measured (rent, honest serve-consistent CV): baseline L2 18.2% / R2 0.662 / within10 36.4%;
+has_area 18.2% (inert); L1 objective 18.1% but R2 drops to 0.623; L1+monotone impossible
in LightGBM; Huber overflows. Sale: baseline 12.2%; monotone 12.4% (slightly worse MAPE,
+0.005 R2). Within-locality rent price CV is ~0.5-0.6, so rent CV MAPE will not fall much
below ~16% from feature/loss changes. Area imputation explicitly rejected (rent area 20%
coverage is genuine scarcity; area explains only ~7% of residual variance beyond
locality x bedrooms). Kept `--eval-only/--objective/--monotone/--drop-features` as tooling;
did NOT change the production model.

**The real win was a serve-side bug, invisible to CV:** Nominatim returns Maltese endonyms
(Tas-Sliema, San Giljan, Ix-Xaghra) that never matched the anglicized encoder keys, so
`locality_enc` (the top categorical) was silently NaN for most real requests, and `is_gozo`
(name-prefix based) was always 0 for Gozo (~0.64x price). Added `backend/src/ml/locality_resolver.py`
(endonym normalization + aliases + fuzzy + nearest-centroid fallback) and derived `is_gozo`
from latitude (>36.0). Validated on real data: nearest-centroid top-1 locality recovery
100% (in-sample; proves geographic separability), is_gozo-by-latitude 100.00%. No retrain
needed — it makes serve inputs match what v20260703 already learned.

### Second-wave levers explored (measured, not adopted) - 2026-07-03

Measured with `--eval-only` on the serve-consistent feature set. Results (MAPE / R2 / within10):

| Config | Rent | Sale |
|--------|------|------|
| baseline (v20260703) | 18.2 / 0.662 / 36.4 | 12.2 / 0.776 / 59.2 |
| locality target-encoding | 18.2 / 0.660 / 36.4 | 12.0 / 0.771 / 60.2 |
| winsorize price [P1,P99] | 18.0 / 0.680 / 36.2 | 11.9 / 0.809 / 60.0 |
| te + winsorize | 18.0 / 0.681 / 35.9 | 11.8 / 0.799 / 60.0 |

- **condition/year_built (B4): rejected** — 0% coverage in RE/MAX training data, nothing to learn.
- **Locality target-encoding (leakage-safe per-fold): inert for rent, -0.2pp for sale.** Not worth the
  serve-side plumbing (a target-encoded model can't be served without a locality->mean map lookup).
- **Ensemble-weight sweep: 0.7/0.3 is already near-optimal** for the production label-encoded model
  (sale baseline optimum 0.75); the 0.25 seen under target-encoding is config-dependent CV noise.
- **Winsorizing the price tail is the only genuine lever** (sale MAPE -0.3pp / R2 +0.033; rent -0.2pp /
  R2 +0.017). Trade-off: it caps the top ~1% of prices, under-valuing genuine high-end (luxury Sliema/
  St Julian's) properties — a real downside for a professional tool. Not adopted by default; available
  via `train_valuation.py --winsorize` if the aggregate-accuracy/high-end trade-off is acceptable.

Conclusion: the big wins already landed (serve-consistent honest model + serve-side locality/Gozo fix).
Second-wave feature/loss tuning offers only marginal gains; production model kept at v20260703.

---

## v20260705 — Durable monotone retrain + serve-side condition (task #18) - 2026-07-05

Follow-up to the PR #10 serve-side recalibration. Two durable changes: (1) retrained
both models with **monotonic size constraints**, (2) wired the form's `condition`
dropdown into the model at serve time.

### Retrain (monotonic constraints)

`train_valuation.py --serve-consistent --monotone` for sale + rent. Price is constrained
monotonically increasing in `{area_sqm, area_sqm_log, bedrooms, bathrooms, rooms,
total_int_area, total_ext_area}` (applied to both LGB `monotone_constraints` and XGB).
Ensemble weights 0.85/0.15 (LGB/XGB, from PR #10). Categoricals never constrained.

| Model | v20260703 (baseline) | v20260705 (monotone) |
|-------|----------------------|----------------------|
| Sale MAPE / R2 / within10 | 12.2 / 0.776 / 59.2 | **11.8 / 0.802 / 60.6** |
| Rent MAPE / R2 / within10 | 18.2 / 0.662 / 36.4 | **18.6 / 0.640 / 35.4** |

The monotone constraint **improved sale** (regularizes the size axis: -0.4pp MAPE, +0.026 R2)
and left rent ~flat (within noise; rent is dominated by locality×bedrooms, area is scarce).
Contradicts the earlier `--eval-only` note that monotone cost +0.2pp — that test predated the
0.85/0.15 weight change; monotone + LGB-heavy weights is a net win.

### Monotonicity eval (the primary QA FAIL — now fixed)

Total price is now strictly increasing with size in every locality, both holding bedrooms
constant (pure area) and along a realistic beds-grow-with-size ladder. Example (sale, bare):

| Locality | 55m² | 75m² | 100m² | 150m² | 220m² | monotonic? |
|----------|------|------|-------|-------|-------|-----------|
| Sliema (bed=2) | 390k | 450k | 503k | 622k | 893k | YES |
| Bugibba (bed=2) | 290k | 324k | 372k | 451k | 781k | YES |
| Gozo (bed=2) | 250k | 262k | 283k | 308k | 562k | YES |

**Residual tail caveats** (data-sparse extrapolation, not ordering bugs): a 35m² studio still
prints a high €/m² (Sliema ~€10.5k/m²) because <35m² units are rare in training; and €/m² ticks
up at 220m² in cheap areas (large units rare there). Total price stays correctly ordered; the
wide "Low"-confidence band covers the tail. Most real inputs (55–150m²) are unaffected.

### Serve-side: `condition` dropdown now moves the estimate

RE/MAX has no structured condition field, so the model only ever learned condition via the
LLM-extracted `llm_condition` (1–5) from listing text. The form's `condition` dropdown was
therefore **inert with no description**. Fix (`artifact_predictor._fill_enriched`): map the
dropdown → `llm_condition` (`new/excellent→5, good→4, needs_renovation→2, shell→1`); real LLM
output still overrides. We deliberately do **not** impute the other `llm_*` features to
modal/neutral values — doing so biased the sparse estimate **down ~28%** (regressing the
already-calibrated bare case); the model handles genuinely-missing `llm_*` natively as NaN.

### Sparse-vs-full calibration (Sliema 90m², comp median €520k / €5,889/m²)

| Input | Estimate | €/m² | vs comp median |
|-------|----------|------|----------------|
| bare (no condition) | €584k | 6,490 | +10% |
| condition=shell | €582k | 6,470 | +10% |
| condition=new | €610k | 6,782 | +15% |
| LLM: luxury + sea view | €864k | 9,600 | high-end |
| LLM: budget + shell | €538k | 5,983 | +2% |

Bare calibration preserved from PR #10 (+10%, well within the ±35% QA tolerance); the dropdown
now shifts the estimate sensibly (shell < good < new); a real description with luxury/sea-view
features still drives the estimate up as expected.

Both models deployed at v20260705; v20260703 retained for rollback.
