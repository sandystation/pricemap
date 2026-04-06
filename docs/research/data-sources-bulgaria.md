# Bulgaria -- Data Sources

## Tested & Working

### Imot.bg (Primary — thousands of listings across 35 cities)
- **URL**: `https://www.imot.bg/obiavi/prodazhbi/grad-{city-slug}`
- **Method**: HTML scraping + JSON-LD structured data on detail pages
- **Encoding**: `windows-1251` (not UTF-8) — must decode with `resp.encoding = "windows-1251"`
- **Pagination**: `/p-{N}` suffix, 40 listings per page
- **Search URL pattern**: `https://www.imot.bg/obiavi/prodazhbi/grad-{city}/p-{page}`
- **Detail URL pattern**: `https://www.imot.bg/obiava-{id}-{slug}`
- **CDN**: Behind Cloudflare, but accessible with standard headers and 2s delay

#### HTML Structure (Search Results)
- Listing container: `div.item` (regular) or `div.nova-sgrada` (new construction promo)
- Title link: `a.title.saveSlink`
- Price: `div.price div` — contains EUR and BGN on separate lines (e.g. "119 000 €\n232 743.77 лв.")
- Info line: `div.info` — comma-separated: area, floor, construction type, amenities, phone
- Images: `div.photo .big img.pic` (main), `div.photo .small img` (thumbnails)
- Agency: `div.seller .name a` and `div.seller .location`
- Price-up indicator: `div.price.UP`
- Element ID: `div.item[id="ida{listing_id}"]`

#### JSON-LD (Detail Pages — Best Structured Data)
Each detail page has `<script type="application/ld+json">` with:
```json
{
  "@type": "Offer",
  "priceCurrency": "EUR",
  "price": 119000,
  "itemOffered": {
    "@type": "Product",
    "name": "...",
    "description": "65 кв.м, Етажна 5, Тух.строит.",
    "image": ["url1", "url2"],
    "sku": "1b176839608204609"
  },
  "seller": {
    "@type": "RealEstateAgent",
    "name": "Агенция Name",
    "url": "https://agency.imot.bg"
  }
}
```

#### Detail Page HTML Selectors
- Parameters: `div.adParams div` — area, floor, construction type
- Description: `div.moreInfo .text`
- Amenities: `div.carExtri .items div`
- Phone: `div.phone` or `div.dealer2023 .phone`
- Agency: `div.dealer2023 .infoBox .name`
- Images: `.owl-carousel img.carouselimg` with `data-src` (lazy loaded)
- Publication date: `div.adPrice .info`

#### Cities Scraped (35 total)
**Major**: Sofia, Plovdiv, Varna, Burgas, Ruse, Stara Zagora
**Medium**: Pleven, Sliven, Dobrich, Shumen, Blagoevgrad, Veliko Tarnovo, Vratsa, Gabrovo, Haskovo, Kardzhali, Kyustendil, Lovech, Montana, Pazardzhik, Pernik, Razgrad, Silistra, Smolyan, Targovishte, Vidin, Yambol
**Resort/tourist**: Bansko, Sandanski, Pomorie, Nesebar, Sozopol, Sveti Vlas, Sunny Beach (`KK-slanchev-bryag`), Golden Sands (`KK-zlatni-pyasatsi`)

URL slugs: cities use `grad-{name}`, resort complexes use `KK-{name}`.

#### Known Issues
- **Area extraction unreliable**: `div.adParams` often doesn't have area in a parseable format. Fallback: parse from `div.info` text on search results or from JSON-LD description
- **No GPS coordinates**: Detail pages don't expose lat/lon in HTML or JSON-LD. Map section exists (`a[name="map"]`) but coordinates may be loaded via AJAX. Need batch geocoding via Nominatim
- **Mixed listings**: Sales results page sometimes includes promoted rentals. Title contains "Дава под Наем" (For Rent) vs "Продава" (For Sale)
- **Bulgarian property types**: 1-стаен=studio, 2/3/4-стаен=apartment, многостаен=apartment, мезонет=maisonette, къща=house, вила=villa, етаж от къща=house

#### Agent/Contact Data
- Agent name: 100% coverage
- Agent company: 93% coverage
- Agent phone: 100% coverage
- Agent website URL: 93% coverage
- No email (hidden behind contact forms)

## Official Government Data

### NSI HPI
- Quarterly, regional breakdown (Sofia, Plovdiv, Varna, Burgas)
- FRED series: `QBGN628BIS`
- Not yet imported into our system

### Bulgarian Cadastre (IKAR)
- Free access at `kais.cadastre.bg/en`
- Property type, boundaries, ownership info
- Not yet integrated

## Data Quality Notes

- **Asking vs transaction gap**: ~5-10% (asking prices higher)
- **Currency**: BGN to EUR fixed rate 1.95583 BGN/EUR (Bulgaria joining eurozone)
- **Price ranges observed**: €61K–€1.35M (avg €174K across 121 initial properties)
- **Regional variation**: Sofia significantly more expensive than other cities
