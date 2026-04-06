# Malta -- Data Sources

## Official Government Data

### Property Price Registry (PPR)
- **URL**: https://ppr.propertymalta.org/
- **Data**: Verified residential property sales from 2018 onwards, updated every 6 months
- **Coverage**: Historical transaction data from registered contracts
- **Access**: Free information for citizens; professional subscriptions for agents/banks
- **Features**: Advanced analytics, geospatial mapping, interactive dashboards with price benchmarks by locality
- **Priority**: CRITICAL -- this is the only source of actual transaction prices

### National Statistics Office (NSO)
- **URL**: https://nso.gov.mt/property/
- **Data**: Quarterly Residential Property Price Index (RPPI)
- **Methodology**: Laspeyres-type formula, base period 2015=100
- **Latest**: Q3 2025 RPPI at 174.63 (up 5.7% YoY)
- **Coverage**: 1,000+ transactions per quarter
- **Breakdown**: Separate indices for apartments, maisonettes, houses
- **Eurostat**: Also reported as house sales indicators (total number and value)

## Listing Portals

### PropertyMarket.com.mt
- **URL**: https://www.propertymarket.com.mt/
- **Data**: 37,000+ properties for sale, 19,000+ for rent
- **Features**: Property Price Index based on live listings, pricing trends by location
- **API**: No public API; custom scraping required
- **Priority**: HIGH -- largest listing dataset for asking prices

### Other Portals
- frank.com.mt
- remax-malta.com
- No documented APIs; custom scraping needed

## Geospatial & Open Data

### Malta GeoHub
- **URL**: https://geohub.gov.mt/
- **Data**: Geospatial data and mapping resources
- **Use**: Location features, boundaries, zoning

### Land Registry Plans
- **URL**: https://landregistryplans.gov.mt/
- **Data**: Property site plans
- **Use**: Property boundary verification

### National Data Portal
- **URL**: https://mita.gov.mt/en/nationaldatastrategy/Pages/National-Data-Portal-Page.aspx
- **Data**: Central open data repository

### Public Registry & Land Registry
- All transactions must be registered; registries open to public inspection
- **Searches Unit**: https://identita.gov.mt/searches-main-page/
- Can request purchase/sale contract info (may require fee)

## Data Strategy for Malta

1. **Primary**: Scrape PPR for transaction prices (2018-present) -- gold standard
2. **Secondary**: Scrape PropertyMarket.com.mt for current asking prices and property features
3. **Indices**: Import NSO RPPI quarterly for temporal adjustment
4. **Spatial**: Malta GeoHub + OpenStreetMap for location features
5. **Adjustment**: Compare PPR transactions vs PropertyMarket asking prices to derive asking-to-transaction factor

## Key Advantages
- PPR provides real transaction data (rare among our 4 target countries)
- Small geography (316 sq km) -- complete coverage feasible
- English co-official -- no address transliteration needed
- EUR currency -- no conversion
