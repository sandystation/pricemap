# PriceMap -- System Architecture

## System Overview

```
                         +------------------+
                         |   Next.js 15     |
                         |   Frontend       |
                         |  (react-leaflet) |
                         +--------+---------+
                                  |
                                  | REST/JSON
                                  v
                         +--------+---------+
                         |    FastAPI        |
                         |    Backend API    |
                         |  (GeoAlchemy2)   |
                         +--+-----+------+--+
                            |     |      |
               +------------+     |      +-------------+
               |                  |                     |
               v                  v                     v
    +----------+---+    +---------+--------+   +--------+--------+
    |  PostgreSQL  |    |  Valuation       |   |  Redis          |
    |  + PostGIS   |    |  Engine          |   |  (cache/broker) |
    |              |    |  (LightGBM)      |   |                 |
    +--------------+    +------------------+   +---------+-------+
                                                         |
                                               +---------+-------+
                                               |  Celery Workers  |
                                               |  (scraping,      |
                                               |   retraining)    |
                                               +--------+---------+
                                                        |
                                               +--------+---------+
                                               |  Scrapy Spiders  |
                                               +------------------+
```

## Tech Stack

| Layer | Technology | Rationale |
|-------|-----------|-----------|
| Frontend | Next.js 15 + TypeScript | SSR for SEO, App Router, API routes as BFF |
| UI Framework | Tailwind CSS + shadcn/ui | Rapid, consistent, accessible components |
| Maps | react-leaflet + Leaflet.js | Free OSM tiles (no Mapbox billing at any scale) |
| Backend | Python 3.12 + FastAPI | Async, auto OpenAPI docs, ML ecosystem access |
| ORM | SQLAlchemy + GeoAlchemy2 | PostGIS integration, spatial queries in Python |
| Database | PostgreSQL 16 + PostGIS 3.4 | Spatial indexing (GiST), geography types, ST_DWithin |
| Cache/Broker | Redis 7 | API cache, geocoding cache, Celery broker |
| Task Queue | Celery | Scraping orchestration, model retraining |
| Scraping | Scrapy + scrapy-playwright | Production crawling with JS rendering support |
| ML | LightGBM + scikit-learn | Best for tabular data with limited rows |
| Explainability | SHAP | Show users which features drive the price |
| Containers | Docker Compose | Single-server VPS deployment |

## Key Design Decisions

### Why LightGBM over Deep Learning
With limited data (tens of thousands of records), gradient boosted trees consistently outperform neural networks for tabular data. LightGBM trains fast, handles missing values natively, and provides feature importance.

### Why Leaflet over Mapbox
Zero cost at any scale. Mapbox charges per map load after free tier. OSM tiles are sufficient; Leaflet's plugin ecosystem (heatmap, marker clustering) covers all needs.

### Why Scrapy over requests/BeautifulSoup
Production-grade crawling needs: built-in concurrency, retry logic, item pipelines, middleware for proxies/user-agents, scrapy-playwright for JS-heavy sites.

### Why PostGIS over Separate Geospatial Service
Collocating spatial logic with transactional data avoids network hops for latency-sensitive queries. GiST indexes make ST_DWithin and ST_Distance queries efficient at hundreds of thousands of rows.

### Why Separate pipeline/ and ml/ Directories
Different lifecycles: pipeline runs daily (scraping), ML training runs monthly. Different dependencies. Backend only needs inference (loads serialized model artifact).

## Valuation Approach

### Hedonic Pricing Model
Features:
- **Structural**: area_sqm, property_type, rooms, floor, year_built, condition, amenities
- **Spatial**: distance_coast, distance_center, distance_transit, POI_density, neighborhood_median
- **Temporal**: quarter, year, national HPI trend
- **Market**: listing_density_1km, median_price_1km, days_on_market

### Confidence Scoring (0-100)
- Data density within 2km/12mo (40%)
- Feature completeness from user input (20%)
- Prediction interval width (25%)
- Data freshness (15%)

### Asking-to-Transaction Adjustment
Per (country, property_type, region) correction factor:
- Malta: derived from PPR vs listing prices
- Bulgaria: 0.92-0.95 default, calibrated against NSI HPI

## API Design

Core endpoints:
- `POST /api/v1/valuations/estimate` -- main valuation
- `GET /api/v1/properties/search` -- spatial bounding box search
- `GET /api/v1/geocode` -- address to coordinates (Redis-cached)
- `GET /api/v1/stats/{country}/{region}` -- market statistics
- `GET /api/v1/heatmap/{country}` -- GeoJSON price heatmap

## Deployment

- Docker Compose on VPS (Hetzner/DigitalOcean)
- Nginx reverse proxy with SSL (Let's Encrypt)
- GitHub Actions CI/CD
- Celery Beat for scheduled scraping
