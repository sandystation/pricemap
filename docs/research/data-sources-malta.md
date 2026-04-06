# Malta -- Data Sources

## Tested & Working

### RE/MAX Malta API (Primary — 32K+ listings)
- **Endpoint**: `https://remax-malta.com/api/properties`
- **Method**: JSON REST API, no auth required
- **Pagination**: `?Take=100&Skip=N&TransactionTypeId=0` (for sale)
- **Total available**: 32,105 listings (as of 2026-04-06)
- **Response**: `{"data": {"Properties": [...], "TotalSearchResults": N}}`
- **Fields per property**: MLS, Price (string), PropertyType, Town, Zone, Province, TotalSqm, TotalIntArea, TotalExtArea, TotalRooms, TotalBedrooms, TotalBathrooms, Coordinates (lat/lon), Image URL, InsertionDate, Status, PropertyIncludesGarage, AvailabilityText, LastModified
- **Image CDN**: `https://jade.uptech.mt/Image/Download/width_{size}/RemaxMalta/Fusion/Listings/LowRes/{id}_{date}_{hash}.jpeg`
- **Rate limit**: ~2s delay sufficient, no blocking observed
- **Known issues**:
  - `Description` field is empty in the list endpoint (returns `""`) — need to fetch individual detail pages for descriptions
  - `Price` is a string, sometimes comma-separated (e.g. `"1,250,000"`)
  - Some properties have no coordinates
  - Property types not in our original TYPE_MAP: `Land`, `Land for Development`, `Agriculture Land`, `Garage (Residential)`, `Restaurant`, `Bar`, `Warehouse`
- **Additional endpoints discovered**: `/api/localities`, `/api/get_static_types`, `/api/branches`, `/api/agents`, `/api/currencies`

### MaltaPark (Secondary — ~4K listings)
- **URL**: `https://www.maltapark.com/listings/category/248` (Property for Sale)
- **Method**: Server-rendered HTML, no anti-bot blocking
- **Pagination**: `?page=N`, ~48 items per page, ~86 pages total
- **Detail pages**: `https://www.maltapark.com/item/details/{item_id}`
- **Fields**: title, price, property type, bedrooms, locality, description, images, seller username, condition/finish level
- **Image URLs**: `https://www.maltapark.com/asset/itemphotos/{id}/{id}_{n}.jpg`
- **HTML selectors**:
  - Listing card: `div.item[data-itemid]`
  - Price: `span.price > span`
  - Detail fields: `div.item-details span.item` with `<b>` labels
  - Images: `a.fancybox` or `a[data-fancybox]` href
  - Description: `div.readmore-wrapper`
- **Known issues**:
  - No area/sqm in structured fields — sometimes in description text only
  - Price parser can pick up phone numbers as prices (e.g. €9,988,777,000 for a "Large Garage")
  - Only seller username, no phone/email (behind contact forms)

## Tested & Blocked

### PropertyMarket.com.mt (38K listings — blocked)
- Returns **403 Forbidden** on all listing/search pages for direct HTTP requests
- Homepage returns 200 but property pages are blocked
- WordPress custom plugin (`property-market`), no REST API for property data
- **URL patterns**: `/for-sale/?pc=-1&pt=0&pp=N`, `/view/{slug}-{id}`
- **Detail page data**: price in `<h2>`, specs as inline text (not structured HTML), images at `/wp-content/plugins/property-market/files/{agent_code}/listings/`
- **Fix needed**: Playwright with realistic browser headers, or rotating residential proxies

### Frank Salt (franksalt.com.mt — blocked)
- 403 Forbidden on property pages, Cloudflare WAF
- Not scrapeable without headless browser + anti-bot evasion

### Dhalia (dhalia.com — blocked)
- Cloudflare managed challenge page requiring JavaScript execution
- Not scrapeable without Cloudflare bypass

### Malta PPR (ppr.propertymalta.org — behind auth)
- React SPA at `ppr-app.propertymalta.org`, not server-rendered HTML
- REST API behind cookie-based authentication with MFA
- **Requires paid subscription** (EUR 95-150/user/month) or 7-day free trial
- Imperva WAF with rate limiting (~1000 requests per 5 minutes)
- **API endpoints discovered**: `/Authentication/Login`, `/FilterOptions/GetAllFilterOptions`, `/Geomap/GetPropertiesWithoutShape`, `/Geomap/GetPropertiesWithinRadius`, `/Reports/GetReportData`
- Developed by PwC Malta for the Property Malta Foundation
- Actual transaction prices since 2018 — the only source of real sale prices in Malta

## Official Government Data

### National Statistics Office (NSO)
- **URL**: https://nso.gov.mt/property/
- **Data**: Quarterly RPPI, base 2015=100, latest Q3 2025 at 174.63 (+5.7% YoY)
- **Coverage**: 1,000+ transactions/quarter, separate indices for apartments, maisonettes, houses
- Not yet imported into our system

## Data Strategy (Updated)

1. **Primary**: RE/MAX API — 32K listings with GPS, area, bedrooms (no descriptions yet)
2. **Secondary**: MaltaPark — 4K listings with descriptions, images, agent info
3. **Together**: These two cover the vast majority of the Malta market
4. **Blocked sources**: PropertyMarket.com.mt is the biggest gap (38K listings) — revisit with Playwright
5. **PPR transaction data**: Would be gold standard but requires paid subscription
6. **Price adjustment**: RE/MAX data can be cross-referenced with MaltaPark to identify the same properties at different prices
