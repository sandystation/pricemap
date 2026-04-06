# Bulgaria -- Data Sources

## Official Government Data

### National Statistical Institute (NSI)
- **URL**: https://www.nsi.bg/en/content/13025/housing-price-statistics
- **Data**: House Price Index (HPI) quarterly, new and existing dwellings
- **Latest**: Q2 2025 -- new dwellings +14.88% YoY, existing +16.01% YoY
- **Project**: "Real Estate Indicators" (started Oct 2020) improving HPI through cadastral data integration
- **Coverage**: Regional data by major cities (Sofia, Plovdiv, Varna, Burgas)
- **Metadata**: https://www.nsi.bg/en/metadata/house-price-index-hpi-227

### Bulgarian Cadastre (IKAR)
- **URL**: https://kais.cadastre.bg/en
- **Managed by**: Agency of Geodesy, Cartography and Cadastre
- **Free access** to property information:
  - Part A: identification number, type, boundaries, location, purpose
  - Part B: ownership rights and related documents
- Semantic and graphic data available where digitized
- Electronic extracts available to third parties; official documents only to owners

### ECB / Eurostat / FRED Data
- ECB Data Portal: residential property price indices for Bulgaria
- FRED: https://fred.stlouisfed.org/series/QBGN628BIS (BIS data)
- Long-run historical price series available

## Listing Portals

### Imot.bg (Primary Target)
- Largest and oldest real estate platform (since 2000)
- Covers apartments, houses, land, offices, retail
- **Scraping**: Multiple third-party services available (RealDataAPI, ScrapeIt, RetailScrape)
- **Data points**: listings, prices, sqm, neighborhood, photos, sale history
- **API**: No official API; web scraping required
- **Priority**: HIGH -- most comprehensive listing data

### Secondary Portals
- **Homes.bg** -- top 5 Bulgarian RE portal
- **OLX.bg** -- classifieds with property listings; Apify scraper available
- **Imoti.net, Indomio.bg** -- smaller portals

## Geocoding & Address Data

### Resources
- **GitHub**: github.com/yurukov/Bulgaria-geocoding -- standardized address formatting + GPS coordinates
- **Address format**: PostGrid guide for Bulgarian address standardization
- **Postcode mapping** data available

## Data Quality

### Asking vs Transaction Prices
- **Gap**: Asking prices typically 5% above actual transaction prices
- **Extended listings**: Overpriced homes see 8-10% discounts after market exposure
- **Negotiation**: Sellers anchor high; buyers negotiate on condition, repairs, documentation

### Official Data Cross-checks
- NSI/Eurostat HPI cross-checked against BIS indices for consistency
- Regional variations significant -- Sofia prices diverge from rural areas

## Data Strategy for Bulgaria

1. **Primary**: Scrape Imot.bg for listings (asking prices + property features)
2. **Indices**: Import NSI HPI quarterly for market trend baseline
3. **Cadastre**: Query IKAR for property characteristics where available
4. **Spatial**: OpenStreetMap + Bulgaria-geocoding for location features
5. **Adjustment**: Apply 0.92-0.95 asking-to-transaction factor (calibrate against HPI)
6. **Currency**: BGN to EUR conversion (fixed rate: 1 EUR = 1.95583 BGN, Bulgaria joining eurozone)

## Key Challenges
- No public transaction-level data (unlike Malta's PPR)
- Must rely on asking prices with statistical adjustment
- Cyrillic addresses need transliteration for geocoding
- Regional price variation is extreme (Sofia vs rural)
