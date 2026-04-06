# Scraping Lessons Learned

Practical findings from building and running scrapers against Malta and Bulgaria real estate sites. Useful for adding new scrapers (Cyprus, Croatia) or debugging existing ones.

## Anti-Scraping Defenses Encountered

| Site | Defense | Result | Workaround |
|------|---------|--------|------------|
| RE/MAX Malta | None | Full access via JSON API | — |
| MaltaPark | None | Full access via HTML | — |
| Imot.bg | Cloudflare (light) | Accessible with 2s delay | Standard browser User-Agent |
| PropertyMarket.com.mt | Custom WAF | 403 on all listing pages | Needs Playwright |
| Frank Salt | Cloudflare WAF | 403 on property pages | Needs Playwright + stealth |
| Dhalia | Cloudflare managed challenge | JS challenge page | Needs Playwright + stealth |
| Malta PPR | Auth + Imperva WAF | 401 without login | Requires paid subscription |

**Lesson**: Start with the easiest sources first. Don't waste time fighting anti-bot when there's an open API returning 32K listings.

## JSON APIs Are Gold

RE/MAX Malta exposes a complete REST API at `/api/properties` with no authentication. This wasn't documented anywhere — we discovered it by inspecting the site. The API returns structured JSON with GPS coordinates, which no HTML scraper can match.

**Always check for hidden APIs** before writing an HTML scraper:
- Look at Network tab in browser DevTools for XHR/fetch calls
- Check `/api/`, `/rest/`, `/graphql/` paths
- Inspect `<script>` tags for API base URLs
- Check the site's JavaScript bundle for endpoint strings

## JSON-LD Is the Second Best Source

Imot.bg detail pages include `<script type="application/ld+json">` with structured Offer data: price, currency, images, seller info, SKU. This is machine-readable and more reliable than parsing HTML.

**Always check for JSON-LD** before writing CSS selectors:
```python
for script in soup.select('script[type="application/ld+json"]'):
    data = json.loads(script.string)
    if data.get("@type") == "Offer":
        # price, images, seller — all structured
```

## Character Encoding Gotchas

Imot.bg uses `windows-1251` (Bulgarian Cyrillic), not UTF-8. Without setting `resp.encoding = "windows-1251"`, all Cyrillic text becomes garbled. The encoding is declared in a `<meta>` tag, not in the HTTP headers.

**Always check the meta charset** tag for non-English sites.

## Price Parsing Pitfalls

MaltaPark's price element sometimes contains phone numbers or reference IDs instead of actual prices. A simple `[\d,]+` regex extracted €9,988,777,000 for a "Large Garage" — clearly a phone number.

Imot.bg shows prices in both EUR and BGN on the same line: `"119 000 €\n232 743.77 лв."`.

**Lessons**:
- Don't trust price fields blindly — validate against reasonable ranges for the market
- Look for multiple currency formats in the same text
- Log outliers for human review rather than silently dropping them
- A hard price cap (e.g. €50M) is wrong — legitimate development sites can exceed that

## Image Download Strategy

Each scraper downloads up to 5 images per property to `data/images/{source}/{external_id}_{n}.jpg`. This adds significant time and disk space:

- 1,404 properties × ~3 images avg = 4,200 images = 280 MB in the first run
- At 32K properties with 2 images each, expect ~3 GB

**Lessons**:
- Skip download if file already exists (idempotent)
- Limit to 2-3 images per property for bulk runs
- Image CDN URLs are stable — can re-download later if needed
- Store both `image_urls` (remote) and `image_local_paths` (local) so remote URLs survive even if images are cleaned up

## Pagination Patterns

| Site | Pattern | Items/page |
|------|---------|------------|
| RE/MAX API | `?Take=100&Skip=N` | 100 |
| MaltaPark | `?page=N` | ~48 |
| Imot.bg | `/p-{N}` suffix | 40 |

All three stop returning data when you go past the end — no explicit "last page" indicator needed, just check for empty results.

**For APIs**: Use the `TotalSearchResults` field to know when to stop.
**For HTML**: Check if the parse returns 0 listings.

## Staleness vs Skip-Existing

Original scrapers skipped properties already in the database:
```python
if existing:
    continue  # NEVER re-scrapes, can't detect changes
```

This prevents change detection. The fix is a staleness check:
```python
if not coll.is_stale(doc_id, hours=20):
    continue  # Skip if seen within 20 hours
```

This means: on the first run each day, every property gets re-scraped and diffed. Within the same day, duplicates are skipped. This balances change detection against unnecessary HTTP requests.

## Data Fields by Source

What each source actually provides (tested, not theoretical):

| Field | RE/MAX API | MaltaPark HTML | Imot.bg HTML+JSON-LD |
|-------|-----------|----------------|---------------------|
| Price | 99% (string) | 100% (some garbage) | 100% (EUR+BGN) |
| GPS lat/lon | 94% | 0% | 0% |
| Area sqm | 97% | ~0% (in description) | ~0% (in description) |
| Bedrooms | yes | yes | from title |
| Bathrooms | yes | sometimes | no |
| Description | 0% (empty in API) | 100% | 100% |
| Images | 100% | 98% | 100% |
| Agent name | 0% | 100% (username only) | 100% |
| Agent phone | 0% | 0% | 100% |
| Agent company | 0% | 0% | 93% |
| Property type | yes | yes | from title (Bulgarian) |
| Condition | no | sometimes | no |
| Construction | no | no | sometimes |
| Listing date | yes | no | sometimes |

**Key insight**: No single source has everything. RE/MAX has GPS+area but no descriptions. MaltaPark has descriptions but no GPS. Imot.bg has descriptions+agent info but no GPS/area. Cross-source matching could fill gaps.

## Scraper Performance

| Source | Method | Speed | Full run estimate |
|--------|--------|-------|-------------------|
| RE/MAX | API (100/batch, 2s delay) | ~50 listings/sec | 32K in ~12 min (no images) |
| MaltaPark | HTML (1 detail page per listing, 2s delay) | ~0.3 listings/sec | 4K in ~4 hours |
| Imot.bg | HTML (1 detail + images, 2s delay) | ~0.2 listings/sec | depends on city count |

**RE/MAX is 100x faster** because it's a JSON API — no detail page fetches needed. HTML scrapers are bottlenecked by the per-listing detail page fetch.
