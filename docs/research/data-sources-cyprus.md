# Cyprus -- Data Sources (Phase 2)

## Official Government Data

### House Price Index (HPI)
- **Source**: Department of Lands and Surveys + Central Bank of Cyprus
- **Latest**: Q1 2025 -- 2.0% annual change
- **Averages**: New apartments EUR 281,000, new houses EUR 461,000
- **URL**: https://www.gov.cy/en/economy-and-finance/house-price-index-hpi1st-quarter-2025/

### Cyprus Statistical Service (CYSTAT)
- **URL**: https://www.cystat.gov.cy/en/default
- **Data**: Building permits, floor area statistics, HPI
- **Recent**: 14,401 new homes approved (36.1% YoY increase Q1 2026)

### Department of Lands and Surveys (DLS)
- **Portal**: https://portal.dls.moi.gov.cy/
- **Data**: Source for all house price indices, provides valuation services
- **Limitation**: Property ownership data NOT open; requires legitimate interest

## Listing Portals

### BuySell Cyprus
- **URL**: https://www.buysellcyprus.com/
- **Coverage**: 106,000+ property listings, ~97% market share
- **Access**: Mobile apps, website, daily updates
- **API**: No public API

### Bazaraki.com
- Classifieds portal including real estate
- **Scraping**: Apify actor available (apify.com/sashkavasa/bazaraki-scrapper)
- **Automation**: GitHub bot (lounah/bazaraki-scrapper-bot) polls every 5 minutes
- **Priority**: Best scraping target due to existing tools

### Other Portals
- Zyprus.com, 4buy&sell.com

## Geospatial Data

### Cyprus Geoportal
- **URL**: https://www.geoportal.gov.cy/
- **Data**: Parcels, buildings, plans, aerophotos, town planning zones
- **Access**: Free, real-time

### National Open Data Portal
- **URL**: https://data.gov.cy/en
- **Coverage**: 1,200+ datasets from 94 organizations

## Key Notes for Phase 2
- Greek addresses need transliteration handling
- Property ownership data restricted
- Bazaraki has the most accessible scraping infrastructure
- DLS is the authoritative data source but limited public access
