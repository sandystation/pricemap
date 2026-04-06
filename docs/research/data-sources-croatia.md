# Croatia -- Data Sources (Phase 2)

## Official Government Data

### Croatian Bureau of Statistics (DZS)
- **Data**: House Price Index, quarterly
- **Latest**: Q4 2025 -- properties +16.1% YoY; new +13.1%, existing +14.3%
- **Regional**: Zagreb +14.2%, Adriatic coast +11.8%, other regions +19.3%
- **Coverage**: Flats, detached houses, terraced houses
- **FRED**: https://fred.stlouisfed.org/series/QHRR628BIS

### Croatian Cadastre (Katastar.hr)
- **URL**: https://katastar.hr/
- **Data**: Free online cadastral viewer -- parcels, buildings, structures, title deeds (informative)
- **Search**: By map or address/cadastral plot number
- **Managed by**: State Geodetic Administration
- **Official documents**: Only at regional offices

### Joint Information System (JIS) -- Land Registers & Cadastre
- **URL**: https://oss.uredjenazemlja.hr/en/
- Single database for real estate registration
- Electronic extracts via e-Citizens (eGradani) platform
- Access for lawyers, notaries, authorized users

### Tax Authority (Porezna uprava)
- Real estate transfer tax: 3%
- Transactions logged through PIN/OIB system
- Not a public dataset but records exist
- **URL**: https://porezna-uprava.gov.hr/en

## Listing Portals

### Njuskalo.hr (Largest)
- 1.5 million+ users/month, 1.5M+ active property ads
- **Anti-scraping**: Platform has protections in place
- **Scraping**: Services available (ScrapeIt); GitHub: franraknic/njuskalo-nekretnine
- **Data**: descriptions, prices (EUR), location, features

### Nekretnine.hr
- Dedicated real estate portal
- Market quotations and analytics
- **URL**: https://www.nekretnine.hr/en/cijene-nekretnina/

### CroReal.com
- 120,000+ aggregated offers
- Has existing price map feature: https://www.croreal.com/pricemap.php
- No public API

## Data Quality

### Asking vs Transaction Prices
- **Gap**: ~7% between asking and actual prices
- **Regional variation**: Smaller discounts in prime coastal/Zagreb locations; larger in high-supply areas
- **Data lag**: Asking prices real-time; official transaction data lags 1-2 quarters

## Key Notes for Phase 2
- 91% home ownership rate (vs 70% EU average) -- large market
- Croatian addresses use Latin script (easier than Bulgarian/Cypriot)
- Njuskalo anti-scraping needs Playwright-based approach
- Strong regional price differentiation: coast vs inland
