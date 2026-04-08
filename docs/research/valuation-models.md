# Real Estate Valuation Models: Research & Techniques

Research compiled April 2026 for PriceMap. Covers ML approaches to automated valuation models (AVMs), feature engineering, spatial modeling, and emerging multimodal techniques.

---

## 1. Model Architectures

### 1.1 Gradient Boosted Trees (Current State of the Art for Tabular Data)

Gradient boosted decision trees remain the dominant approach for structured real estate data. The two leading implementations:

**LightGBM** advantages:
- Native handling of missing values (learns optimal split direction for NaN)
- Native categorical feature support (no need for one-hot encoding)
- Histogram-based splitting is faster on large datasets
- Leaf-wise tree growth can capture more complex patterns

**XGBoost** advantages:
- Stronger regularization (L1/L2 on leaf weights)
- More robust to overfitting on small datasets
- Better handling of imbalanced feature importance

**Ensemble approach**: Combining LightGBM (70%) + XGBoost (30%) is a common pattern that provides model diversity and regularization through averaging. Extra Trees have also shown strong results in some property valuation benchmarks (R2=0.826 in a Hong Kong study with 22K properties).

**Typical performance on property valuation**:
- MAPE 8-15% on well-featured datasets (area, condition, floor, year built all available)
- MAPE 15-25% on sparse datasets (missing key features like condition or floor)
- MAPE 25-35% on asking-price-only datasets without transaction data

Sources: [LightGBM vs XGBoost comparison](https://neptune.ai/blog/xgboost-vs-lightgbm), [Hong Kong ensemble study](https://link.springer.com/article/10.1007/s00168-025-01365-7), [Melbourne land valuation](https://www.sciencedirect.com/science/article/pii/S0264275124003299)

### 1.2 Spatial Models

Standard tree-based models treat lat/lon as regular numeric features, which ignores spatial autocorrelation (nearby properties have correlated residuals). Several approaches address this:

**GPBoost (Gaussian Process Boosting)**:
- Combines LightGBM tree-boosting with a spatial Gaussian process for residuals
- The tree part captures nonlinear feature effects; the GP part captures spatial correlation
- Tested on 1.5M German apartment listings with improvements over standard LightGBM
- Open source: [github.com/fabsig/GPBoost](https://github.com/fabsig/GPBoost)
- Practical downside: GP computation scales O(n^3) without approximations; needs inducing points or Vecchia approximation for large datasets

**Geographically Weighted Regression (GWR)**:
- Fits separate local regressions weighted by distance to each prediction point
- Captures spatial heterogeneity (e.g., different price drivers in urban vs rural areas)
- Studies show R2 improvement from 0.70 to 0.88 vs standard OLS on Calgary housing data
- Not directly compatible with tree models but the concept (local models) can be approximated by including spatial features

**Spatial Autoregressive (SAR) Models**:
- Add a spatial lag term: price_i depends on prices of nearby properties
- Classic econometric approach but hard to integrate with ML pipelines
- Kriging/regression-kriging is the geostatistical equivalent

Sources: [GPBoost paper](https://arxiv.org/html/2004.02653v7), [GPBoost for real estate](https://onlinelibrary.wiley.com/doi/10.1111/1540-6229.70030), [Tree-Boosting for Spatial Data](https://towardsdatascience.com/tree-boosting-for-spatial-data-789145d6d97d/), [GWR for housing](https://www.mdpi.com/2220-9964/9/6/380)

### 1.3 Graph Neural Networks

Recent work models housing markets as graphs where properties are nodes and edges connect geographically similar properties:

**PD-TGCN (Transformer Graph Convolutional Network)**:
- k-Nearest Similar House Sampling (KNHS) builds edges based on geographic + feature similarity
- Transformer-based attention weighs importance of different neighbors
- On 225K Santiago properties: MAPE 0.204 vs XGBoost 0.212 (modest improvement)
- Two-hop neighborhoods capture indirect spatial relationships

GNNs are most valuable when explicit neighborhood relationships matter (e.g., properties in the same building or street) but add significant complexity for marginal gains over well-tuned gradient boosting.

Sources: [Scalable Property Valuation via Graph-based Deep Learning](https://arxiv.org/html/2405.06553v1), [GNN for house price prediction](https://link.springer.com/article/10.1007/s41060-024-00682-y)

### 1.4 Deep Learning / Neural Networks

Standard deep learning approaches for tabular real estate data generally underperform gradient boosting. However, deep learning excels in two scenarios:

1. **Multimodal fusion** (see Section 3): processing images, text, and structured data jointly
2. **Very large datasets** (>1M samples): neural networks can capture interactions that trees miss

Typical architectures: multi-input networks with separate branches for structured features, text (BERT/SBERT), and images (ResNet/CLIP), fused via concatenation or attention layers.

Sources: [Multi-Modal House Price Prediction](https://arxiv.org/html/2409.05335v1), [Optimization of house price model](https://journals.plos.org/plosone/article/file?id=10.1371/journal.pone.0335722&type=printable)

---

## 2. Feature Engineering

### 2.1 Feature Importance Hierarchy

Across multiple studies, features consistently rank in this order of importance for price prediction:

**Tier 1 - Strongest predictors** (each alone explains 20-40% of variance):
- **Location** (lat/lon, or locality/neighborhood encoding)
- **Size** (area_sqm / total living area)
- **Property type** (apartment vs house vs villa)

**Tier 2 - Strong predictors** (5-15% each):
- **Bedrooms / rooms** count
- **Condition / quality** (new, renovated, needs work)
- **Floor level** (for apartments: higher floors command premium, except ground floor with garden)
- **Year built / renovated**
- **Distance to city center** or CBD

**Tier 3 - Moderate predictors** (1-5% each):
- **Bathrooms** count
- **Amenities**: parking, elevator, balcony, pool, A/C
- **Energy efficiency** rating
- **Distance to coast/sea** (in coastal markets like Malta)
- **Distance to transit** (train station, bus stop)
- **View quality** (sea view, city view, garden view)
- **Total floors** in building
- **Exterior area** (terrace, garden sqm)

**Tier 4 - Weak but measurable** (<1% each):
- **Furnishing** status
- **Orientation** (south-facing premium)
- **Noise level** / proximity to busy roads
- **School quality** in catchment area
- **Listing age** (time on market as proxy for overpricing)

Sources: [Systematic review of ML for house prices](https://link.springer.com/10.1007/s10614-025-10983-4), [Interpretable cadastral models](https://arxiv.org/html/2506.15723v3), [Hedonic pricing development](https://www.mdpi.com/2073-445X/11/3/334)

### 2.2 Distance & POI Features

Points of Interest (POI) distances are among the most impactful engineered features. Commonly computed from OpenStreetMap or Google Maps:

| Feature | Computation | Typical Impact |
|---------|-------------|----------------|
| Distance to city center | Haversine or road network distance to CBD | High |
| Distance to coast/sea | Nearest coastline point | High (coastal markets) |
| Distance to nearest school | OSM amenity=school | Moderate |
| Distance to nearest transit | OSM railway/bus_stop | Moderate |
| Distance to nearest supermarket | OSM shop=supermarket | Low-moderate |
| POI density (500m radius) | Count of restaurants, shops, cafes | Moderate |
| Distance to negative POIs | Industrial zones, landfills, highways | Moderate (negative) |

**Best practice**: Use Gaussian proximity `exp(-dist^2 / 2*beta^2)` rather than raw distance. The decay parameter beta should be tuned per market (typically 20-50m for urban, 200-500m for suburban).

An alternative approach is **areal embedding**: discretize the area into a grid, build a road-network graph, and use Node2Vec to learn spatial embeddings that capture connectivity patterns.

Sources: [POI integration for appraisal](https://ar5iv.labs.arxiv.org/html/2311.11812), [Improving hedonic models with accessibility indices](https://www.sciencedirect.com/science/article/pii/S0957417423015610)

### 2.3 Encoding High-Cardinality Categorical Features

Locality/neighborhood names typically have 50-500+ unique values, making one-hot encoding impractical. Recommended approaches:

**Target encoding (smoothed/regularized)**:
- Map each category to the mean target value, smoothed toward the global mean
- Formula: `enc(cat) = (n * mean_cat + m * global_mean) / (n + m)` where m is the smoothing parameter (typically 5-20)
- Must be applied inside cross-validation folds to prevent target leakage
- Studies show regularized target encoding outperforms one-hot, frequency, and hash encoding for high-cardinality features

**K-fold target encoding**:
- Train-set values are encoded using out-of-fold means (similar to stacking)
- More robust than simple hold-out target encoding

**Entity embeddings** (deep learning):
- Learn dense vector representations jointly with the model
- Best when you have sufficient data (>10K samples) and use neural network models

**Geospatial alternatives**:
- H3 hexagonal grid cells at resolution 7-9 (each hex ~0.5-5 km^2)
- Encode as target-encoded hex IDs for fine-grained spatial resolution

Sources: [Regularized target encoding](https://link.springer.com/article/10.1007/s00180-022-01207-6), [High cardinality encoding methods](https://towardsdatascience.com/4-ways-to-encode-categorical-features-with-high-cardinality-1bc6d8fd7b13/)

### 2.4 Temporal Features

Real estate prices change over time. Useful temporal features:
- **Listing month/quarter**: captures seasonality (spring premium in many markets)
- **Days on market**: proxy for overpricing (long-listed = likely overpriced)
- **Market trend index**: rolling median price for the locality over past 3-6 months
- **Price history**: number of price drops, total discount from original price

---

## 3. Multimodal Approaches (Images + Text + Structured)

### 3.1 Computer Vision Features

Property images contain information about quality, condition, and style that structured data misses. Three image sources have been studied:

**Interior/exterior property photos**:
- Pre-trained CNNs (ResNet, EfficientNet) extract feature vectors from listing photos
- Fine-tuned models can predict condition scores (C1-C6 ratings)
- A CNN trained on 25K images achieved 4.98% median error, outperforming Zillow's Zestimate (7.3%)
- CLIP embeddings (256-dim) capture both visual style and quality

**Street view images** (Google Street View):
- Semantic segmentation (DeepLabv3+) extracts view indices:
  - Building View Index (BVI): 53.4% feature importance in one study
  - Vegetation View Index (VVI): correlates with neighborhood quality
  - Sky View Index (SVI): proxy for building density
- Panoramic images at 50m intervals within 1km radius of property

**Satellite/remote sensing**:
- NDVI (vegetation), NDBI (built-up density), NDWI (water proximity)
- Landsat 8 or Sentinel-2 imagery
- Captures neighborhood-level environmental quality

**Impact**: Adding all image sources improved R2 from 0.809 to 0.826 in a Hong Kong study. Interior photos contributed most to individual property valuation; street view contributed most to neighborhood-level quality assessment.

Sources: [Multi-source image fusion](https://pmc.ncbi.nlm.nih.gov/articles/PMC12088074/), [Property condition scoring](https://www.swishappraisal.com/articles/en/computer-vision-property-condition), [Real estate pricing via textual and visual features](https://link.springer.com/article/10.1007/s00138-023-01464-5)

### 3.2 NLP / Text Features from Listing Descriptions

Property descriptions contain implicit quality signals that structured fields miss (e.g., "recently renovated kitchen", "panoramic sea views", "needs TLC").

**Approaches ranked by effectiveness**:

1. **Domain-trained TF-IDF + gradient boosting**: Simple, fast, effective. TF-IDF on property descriptions with domain-specific vocabulary. Reduces MAPE by 5-17% depending on market.
2. **Sentence-BERT (SBERT) embeddings**: 128-dim dense vectors from property descriptions. Best balance of quality and computational cost.
3. **Fine-tuned BERT for regression**: End-to-end price prediction from description alone. MAPE ~30% from text only (no structured features). Useful as an ensemble member.
4. **LLM feature extraction**: GPT/Claude extracts structured features from descriptions (condition, renovation year, view quality, noise level). Recent 2025 study showed LLM-extracted features improved RMSE by 24.3% and MAPE by 15.3%.

**Key finding**: Text features help more for rental predictions (17.1% error reduction) than sales (5.7%), likely because rental descriptions emphasize amenities and condition more heavily.

Sources: [LLM features for AVM](https://www.tandfonline.com/doi/full/10.1080/08965803.2025.2587313), [BERT for property descriptions](https://medium.com/ilb-labs-publications/fine-tuning-bert-for-a-regression-task-is-a-description-enough-to-predict-a-propertys-list-price-cf97cd7cb98a), [Automated valuation with descriptions](https://www.sciencedirect.com/science/article/abs/pii/S0957417422021650), [Multi-modal approach](https://arxiv.org/html/2409.05335v1)

### 3.3 Multimodal Fusion Architecture

The state-of-the-art approach combines all modalities:

```
Structured features (area, beds, lat/lon, amenities)
    |
    v
[Feature vector] --+
                    |
Text description -> [SBERT encoder] -> [128-dim embedding] --+
                                                              |---> [Concatenation] -> [LightGBM / XGBoost]
Property images -> [CLIP encoder]  -> [256-dim embedding] --+
                                                              |
Spatial context -> [GSNE / Node2Vec] -> [64-dim embedding] --+
```

Best results from the MHPP framework on Australian data:
- Structured only: MAE baseline
- + Spatial embeddings: -8% MAE
- + Text embeddings: -15% MAE
- + Image embeddings: -23% MAE
- All combined: **-27% MAE** (LightGBM as final regressor)

---

## 4. Cross-Validation for Spatial Data

Standard k-fold CV overestimates model performance on spatial data because nearby properties leak into both train and test sets. Spatial CV approaches:

### 4.1 Geographic Fold Splits
Sort by latitude (or longitude) and create contiguous geographic strips. Each strip becomes a test fold. Simple and effective for elongated geographies.

### 4.2 Spatial Block CV
Divide the study area into rectangular or hexagonal blocks. Assign entire blocks to folds. Better for compact geographies (islands, cities).

### 4.3 Buffered CV
Standard k-fold but exclude training samples within a buffer distance (e.g., 1km) of test samples. Prevents spatial leakage while maintaining random fold assignment.

### 4.4 Temporal + Spatial CV
Split by time first (train on past, test on future), then apply spatial blocking within each temporal split. Most realistic for production deployment.

**Rule of thumb**: Spatial CV metrics are typically 5-15 percentage points worse than standard CV, but they are more honest about real-world performance. Always report spatial CV metrics.

---

## 5. Performance Benchmarks

### 5.1 Industry AVMs

| System | Market | MAPE | Notes |
|--------|--------|------|-------|
| Zillow Zestimate | US national | 7.3% median | Massive dataset, transaction data |
| Zillow vs NYC assessments | NYC | 32.6% mean / 17.5% median | Asking vs assessed gap |
| HouseCanary | US national | ~5-8% | 6 sub-model ensemble |
| Redfin Estimate | US national | ~6-9% | Transaction-trained |

### 5.2 Academic Models (Recent Studies)

| Study | Market | Model | MAPE | Data Size |
|-------|--------|-------|------|-----------|
| Hong Kong images (2025) | HK | Extra Tree + images | 4.98% median | 22K sales |
| German apartments (2024) | Germany | GPBoost | ~8-12% | 1.5M listings |
| Santiago GNN (2024) | Chile | PD-TGCN | 20.4% | 225K properties |
| Melbourne land (2024) | Australia | XGBoost | 13.9% | Land parcels |
| Commercial RE (2023) | US | Interpretable ML | 8.6-12.5% | Commercial |
| Russian cadastral (2025) | Russia | Regression-kriging | 19.2% | 26K flats |
| Multimodal MHPP (2024) | Australia | LightGBM + SBERT + CLIP | ~11% | Multi-city |

### 5.3 What Drives the Gap?

The gap between industry AVMs (5-8%) and academic models (10-25%) is primarily due to:
1. **Transaction data**: Industry AVMs train on actual sale prices; academic models often use asking prices (5-15% noisier)
2. **Data volume**: Zillow has millions of transactions; academic datasets are typically 10K-200K
3. **Feature richness**: Industry AVMs have tax records, mortgage data, permit history, MLS details
4. **Temporal density**: Repeat sales and frequent updates reduce staleness

---

## 6. Practical Recommendations for PriceMap

### 6.1 Quick Wins (Current Data)

These improvements can be made with existing RE/MAX + MaltaPark data:

1. **Add distance features**: Compute distance to coast, distance to Valletta (capital/CBD), distance to nearest hospital/school using OpenStreetMap. These are Tier 2 features that require only lat/lon.
2. **Extract text features from descriptions**: Use TF-IDF (simple) or SBERT embeddings on the `description` field. Particularly impactful for rent predictions (~17% error reduction in literature).
3. **Use LLM to extract structured features from descriptions**: Parse condition, renovation status, view quality, furnishing status from text. The 2025 LLM-AVM study showed 15-24% improvement.
4. **Add listing age feature**: `days_since_listing = now - listing_date`. Long-listed properties are likely overpriced.
5. **Price history features**: Number of price drops, total discount from original price (available in DocStore history).

### 6.2 Medium-Term Improvements

6. **GPBoost instead of standard LightGBM**: Add spatial Gaussian process to capture neighborhood effects beyond what lat/lon alone provides.
7. **Image-based features**: Extract condition/quality scores from downloaded property photos using a pre-trained CNN. We already have images in `data/images/mt_remax/`.
8. **Satellite view features**: NDVI (greenness) and NDBI (built-up density) from Sentinel-2 around each property location.
9. **Temporal CV**: Split train/test by listing date to evaluate how well the model predicts future prices.

### 6.3 Longer-Term / Research

10. **Multimodal fusion**: Combine structured features + text embeddings + image embeddings as input to the final model.
11. **Graph neural network**: Model properties as a spatial graph to capture neighborhood pricing dynamics.
12. **Transaction price calibration**: When Malta PPR (Property Purchase Registry) data becomes available, train on actual transaction prices for a significant accuracy boost.

### 6.4 Feature Priority Matrix for PriceMap

Based on the research, here's what would most improve our current models, ordered by expected impact and feasibility:

| Priority | Feature | Expected Impact | Effort | Data Available? |
|----------|---------|----------------|--------|-----------------|
| 1 | Distance to coast | High | Low | Yes (lat/lon + coastline shapefile) |
| 2 | Distance to Valletta CBD | High | Low | Yes (lat/lon) |
| 3 | Text features from description | High (rents) | Medium | Yes (description field) |
| 4 | LLM-extracted condition/view | High | Medium | Yes (description field) |
| 5 | Listing age (days on market) | Medium | Low | Yes (listing_date field) |
| 6 | Price drop count/magnitude | Medium | Low | Yes (history events) |
| 7 | Image quality/condition score | Medium | High | Yes (downloaded photos) |
| 8 | POI density (schools, shops) | Medium | Medium | Yes (OpenStreetMap) |
| 9 | GPBoost spatial effects | Medium | Medium | Yes (lat/lon) |
| 10 | Satellite vegetation index | Low | Medium | Needs Sentinel-2 download |

---

## 7. PriceMap LLM Enrichment Pipeline

### What it does

`scripts/llm_enrich.py` sends property descriptions (and optionally photos) to an LLM API to extract structured features that are missing from the scraped data. These features are stored as `llm_*` fields in DocStore and automatically consumed by `train_valuation.py`.

### Features extracted

**From text** (10 features): condition (1-5 scale), floor number, total_floors, furnishing status, view type, construction status, quality tier, brightness, quietness, sea proximity.

**From images** (3 additional features, with `--with-images`): interior quality score (1-5), renovation era, view from photos.

### Multi-provider support

| Provider | Default Model | Text-only (16K docs) | With Images |
|----------|---------------|---------------------|-------------|
| Anthropic | claude-haiku-4-5 | ~$16 | ~$80 |
| OpenAI | gpt-5.4-mini | ~$8 | ~$40 |
| Google | gemini-2.5-flash | ~$2 | ~$10 |

### Expected impact

Based on the 2025 LLM-AVM study, LLM-extracted features should improve MAPE by 15-24%. Our current models lack condition (0% coverage), floor (0%), and view quality (0%) -- all of which are frequently mentioned in descriptions. The text-only approach is the highest ROI improvement available.

### Metrics tracking

Baseline and post-enrichment metrics are logged in `docs/model-metrics.md`. The trained model metadata JSON includes `llm_enrichment` with provider, model, and coverage info for full traceability.

### How to run

```bash
cd scripts
# Set up API keys
cp .env.example .env  # then edit with your keys

# Text-only (cheapest, ~90 min for 16K docs)
python llm_enrich.py --provider google --model gemini-2.5-flash

# With images (downloads all photos, ~3-5 hours)
python llm_enrich.py --provider anthropic --model claude-haiku-4-5-20251001 --with-images

# Check coverage
python llm_enrich.py --stats

# Retrain with LLM features
python train_valuation.py --listing-type sale
python train_valuation.py --listing-type rent
```

---

## 8. Key Papers & References

### Foundational
- [Machine Learning, Deep Learning, and Hedonic Methods for Real Estate Price Prediction](https://arxiv.org/abs/2110.07151) - Comprehensive comparison of ML vs hedonic approaches
- [The Research Development of Hedonic Price Model-Based Real Estate Appraisal in the Era of Big Data](https://www.mdpi.com/2073-445X/11/3/334) - Evolution of hedonic pricing with ML

### Spatial Modeling
- [Gaussian Process Boosting (GPBoost)](https://arxiv.org/html/2004.02653v7) - Combining tree-boosting with spatial GPs
- [Explainable Spatial ML for Hedonic Real Estate](https://onlinelibrary.wiley.com/doi/10.1111/1540-6229.70030) - GPBoost applied to German housing
- [Tree-Boosting for Spatial Data](https://towardsdatascience.com/tree-boosting-for-spatial-data-789145d6d97d/) - Practical guide

### Multimodal
- [Multi-Modal Deep Learning for House Price Prediction (MHPP)](https://arxiv.org/html/2409.05335v1) - SBERT + CLIP + GSNE fusion
- [Real Estate Valuation with Multi-Source Image Fusion](https://pmc.ncbi.nlm.nih.gov/articles/PMC12088074/) - Street view + satellite + photos in Hong Kong
- [Incorporating LLMs in Automated Real Estate Valuation (2025)](https://www.tandfonline.com/doi/full/10.1080/08965803.2025.2587313) - LLM-extracted features boost AVM by 15-24%

### Graph Neural Networks
- [Scalable Property Valuation via Graph-based Deep Learning](https://arxiv.org/html/2405.06553v1) - PD-TGCN architecture
- [Improving Real Estate Appraisal with POI Integration](https://ar5iv.labs.arxiv.org/html/2311.11812) - Areal embeddings + POI features

### Feature Engineering
- [How Much Is the View from the Window Worth?](https://www.sciencedirect.com/science/article/pii/S014829632200039X) - View quality as ML feature
- [Improving Hedonic Models with Optimal Accessibility Indices](https://www.sciencedirect.com/science/article/pii/S0957417423015610) - Travel cost features
- [Modern Approaches to Interpretable Property Market Models](https://arxiv.org/html/2506.15723v3) - RuleFit, regression-kriging for cadastral valuation

### Encoding & Methods
- [Regularized Target Encoding Outperforms Traditional Methods](https://link.springer.com/article/10.1007/s00180-022-01207-6) - Evidence for target encoding on high-cardinality features
- [Spatial Prediction of Apartment Rent Using Regression](https://arxiv.org/pdf/2107.12539) - Rental-specific spatial models

### Industry
- [HouseCanary AVM Architecture](https://www.housecanary.com/blog/automated-valuation-model) - 6 sub-model ensemble approach
- [Zillow Zestimate vs NYC Assessments](https://acr-journal.com/article/zestimate-vs-reality-benchmarking-automated-valuations-against-new-york-city-assessments-1510/) - Real-world AVM accuracy benchmark
