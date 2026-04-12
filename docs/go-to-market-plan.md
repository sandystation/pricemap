# PriceMap -- Go-to-Market Plan

*April 2026*

---

## Executive Summary

PriceMap is an ML-powered automated property valuation (AVM) tool targeting the four EU countries with no existing automated valuation solutions: **Malta, Bulgaria, Cyprus, and Croatia**. These markets represent ~367K property transactions/year and EUR 20B+ in transaction value, yet rely entirely on manual valuations costing EUR 250-700+ each.

PriceMap already has working ML models for Malta (12.1% MAPE -- sales, 18.2% rents) and Bulgaria (12.1% sales, 13.5% rents), trained on 86K+ scraped listings with LLM-enriched features. The production app (Next.js + FastAPI + PostGIS) is scaffolded and needs 2-4 weeks to connect to the existing data pipeline.

**The opportunity**: First-mover advantage in EUR 20B+ of annual real estate transactions with zero credible AVM competition. EU banking regulations (EBA/CRR3) now actively encourage AVM adoption, but banks in these markets have no provider to work with.

---

## 1. Market Analysis

### 1.1 Market Size by Country

| Country | Annual Transactions | Total Value | Avg. Transaction | Outstanding Mortgages | Foreign Buyer % |
|---------|-------------------|-------------|------------------|-----------------------|-----------------|
| Malta | 12,598 | EUR 3.5B | ~EUR 278K | EUR 9.07B (+9% YoY) | 15% |
| Cyprus | 23,900 | EUR 5.71B (record) | ~EUR 239K | Stabilizing | 27% |
| Bulgaria | ~196K (est.) | EUR 8.8B+ | Varies widely | EUR 12.87B (+30% YoY) | Growing 18% YoY |
| Croatia | ~135K (est.) | Not disclosed | ~EUR 2,834/sqm | EUR 3.93B (H1 only) | 9% |
| **Combined** | **~367K** | **~EUR 20B+** | | **EUR 25B+** | |

### 1.2 Revenue Addressable Market (RAM) Estimates

**B2B -- Banks & Mortgage Lenders** (highest value):
- Malta: ~5,200 new mortgages/year x EUR 5-15/AVM = EUR 26K-78K/year
- Bulgaria: ~50K+ new mortgages/year x EUR 3-10/AVM = EUR 150K-500K/year
- Cyprus: ~10K+ mortgages/year x EUR 5-15/AVM = EUR 50K-150K/year
- Croatia: ~30K+ mortgages/year x EUR 5-15/AVM = EUR 150K-450K/year
- **Portfolio revaluation**: Banks must periodically revalue their entire mortgage book. Malta's EUR 9B mortgage portfolio alone represents tens of thousands of properties requiring annual or semi-annual revaluation -- potentially EUR 200K-500K/year per major bank.

**B2B -- Real Estate Agents** (high volume, lower price):
- Estimated 2,000-5,000 active agents across the 4 countries
- EUR 50-200/month subscription = EUR 1.2M-12M/year TAM

**B2C -- Buyers, Sellers, Foreign Investors** (freemium funnel):
- 367K transactions/year, assume 5% conversion to paid reports
- EUR 10-30/report = EUR 180K-550K/year

**Total RAM**: EUR 2-15M/year at maturity across all four countries, depending on penetration and pricing. The bank segment alone (origination + revaluation) could sustain a EUR 1-5M ARR business.

### 1.3 Manual Valuation Costs (What We Displace)

| Country | Manual Valuation Cost | Time | Provider |
|---------|----------------------|------|----------|
| Malta | EUR 250-500+ | 1-2 weeks | Licensed Perit (architect) |
| Cyprus | EUR 285-700+ (+ 19% VAT) | Days to weeks | ETEK-registered valuer (CVA rates) |
| Bulgaria | EUR 100-300 (est.) | Days | Certified appraiser |
| Croatia | EUR 150-400 (est.) | Days | Licensed valuer |

PriceMap delivers an instant estimate for EUR 5-30 -- a 10-50x cost reduction for non-regulatory use cases, and a powerful screening/triage tool even for cases that still require formal valuations.

---

## 2. Competitive Landscape

### 2.1 Direct Competitors

| Market | Competitor | What They Offer | PriceMap Advantage |
|--------|-----------|-----------------|-------------------|
| Malta | **None** | No AVM exists. Valur.mt has a basic price/sqm calculator (not ML) | First and only ML-based AVM |
| Bulgaria | **None** | BulgarianProperties.com has a lead-gen "instant valuation" form | Real ML model on 54K+ listings vs. simple area averages |
| Cyprus | BuySellCyprus.com AVM | Basic comparables tool, explicitly disclaims accuracy | ML ensemble with LLM-enriched features |
| Cyprus | Realtor.com.cy AVM | Reports for analysts; rudimentary | Deeper data, better model |
| Croatia | **Sprengnetter** (via Crozilla) | Bank-grade AVM, Zagreb office | They're established -- Croatia is our lowest priority |

### 2.2 Adjacent Threats

| Competitor | Current Markets | Threat to PriceMap | Timeframe |
|-----------|----------------|-------------------|-----------|
| Sprengnetter (Scout24) | DE, AT, HR, BA, RS, ME, SI, IT | HIGH for Croatia. Low for MT/CY/BG | Already in HR |
| PriceHubble | CH, FR, DE, AT, UK, BE, CZ, SK | MODERATE -- CZ/SK proximity to BG/HR | 2-3 years |
| Arvio (Slovenia) | SI | MODERATE -- could expand to HR | 1-2 years |
| SonarHome (Poland) | PL, HU, RO | LOW-MODERATE -- RO proximity to BG | 2-3 years |
| CoreLogic/Cotality | US, UK, DE, AU | LOW -- focused on large markets | Unlikely |
| Idealista | ES, IT, PT | LOW -- no Eastern European expansion signals | Unlikely |

### 2.3 Competitive Moat

1. **Data moat**: 86K+ listings already scraped and enriched across MT+BG. Competitors would need months to replicate the scraping infrastructure, LLM enrichment pipeline, and geocoding.
2. **Model moat**: Spatial CV, LLM feature extraction (text + images), ensemble models -- not trivially reproducible.
3. **First-mover in regulation**: EBA/CRR3 now encourage AVM use. Being the first EAA-certifiable AVM in these markets creates a switching-cost moat with banks.
4. **Local data knowledge**: Encoding quirks (windows-1251), hidden APIs (RE/MAX), geocoding hacks (BG neighborhood-to-coordinate mapping) -- hard-won domain knowledge.

---

## 3. Product Strategy

### 3.1 Product Tiers

#### Tier 1: Free Public Tool (Lead Generation)
- **What**: Interactive price heatmap + basic "What's my property worth?" estimator
- **Output**: Price range (e.g., "EUR 180K-240K"), confidence score, comparable listings
- **Limit**: 3 free valuations/month per user, no PDF export
- **Purpose**: SEO traffic, brand awareness, email capture, social proof
- **Status**: Frontend scaffolded (Next.js), needs data pipeline connection

#### Tier 2: Professional Reports (Paid per report)
- **What**: Detailed PDF valuation report with confidence intervals, comparable analysis, market trends, feature importance (SHAP)
- **Output**: Point estimate + 10th/90th percentile range, 5 nearest comparables with photos, price/sqm trends for the locality, feature contribution breakdown
- **Audience**: Individual buyers/sellers, small agents, foreign investors
- **Price**: EUR 9-29 per report (see Pricing section)

#### Tier 3: Agent/Professional Subscription
- **What**: Dashboard with bulk valuations, portfolio monitoring, market analytics, CSV export
- **Features**: Unlimited valuations, price alert notifications, locality trend reports, embed widget for agent websites
- **Audience**: Real estate agencies, property management firms, legal/notarial offices
- **Price**: EUR 49-199/month (see Pricing section)

#### Tier 4: Bank/Institutional API
- **What**: REST API for programmatic AVM access, EBA-compliant reports, portfolio revaluation batch processing
- **Features**: Per-property AVM with confidence score, bulk CSV upload for portfolio revaluation, audit trail and model versioning, SLA guarantees
- **Audience**: Banks, mortgage lenders, insurance companies, institutional investors
- **Price**: Custom annual contracts, EUR 2-10 per AVM call at volume

### 3.2 Feature Roadmap (Prioritized)

#### Phase 1: Malta Launch MVP (Weeks 1-4)
Critical path to first revenue:

| Priority | Feature | Effort | Revenue Impact |
|----------|---------|--------|---------------|
| P0 | Connect DocStore -> PostgreSQL (export_to_postgres.py) | 2 days | Unlocks everything |
| P0 | Wire up valuation API endpoint to trained models | 2 days | Core product |
| P0 | Free heatmap + basic estimator on frontend | 3 days | Lead gen |
| P0 | Stripe integration for paid reports | 2 days | Revenue |
| P1 | PDF report generation (weasyprint or similar) | 3 days | Paid product |
| P1 | User accounts (email/password + Google OAuth) | 2 days | Retention |
| P1 | Comparable properties display (nearest 5) | 2 days | Report value |
| P2 | SHAP feature importance in reports | 1 day | Report value |
| P2 | Locality trend charts | 2 days | Report value |

#### Phase 2: Bulgaria + Agent Tools (Weeks 5-8)
| Priority | Feature | Effort |
|----------|---------|--------|
| P0 | Bulgaria models live on production | 2 days |
| P0 | Agent subscription dashboard | 5 days |
| P1 | Bulk valuation CSV upload | 2 days |
| P1 | Price alert notifications | 3 days |
| P1 | Embeddable widget for agent websites | 3 days |
| P2 | Market analytics dashboard (agent-facing) | 5 days |

#### Phase 3: Cyprus + Bank API (Weeks 9-16)
| Priority | Feature | Effort |
|----------|---------|--------|
| P0 | Cyprus scraper (Bazaraki.com) | 3 days |
| P0 | Cyprus model training | 2 days |
| P0 | REST API with API key management | 3 days |
| P1 | EBA-compliant report format | 5 days |
| P1 | Batch portfolio revaluation endpoint | 3 days |
| P1 | Audit trail and model versioning | 3 days |
| P2 | Croatia scraper (Nekretnine.hr) | 3 days |

### 3.3 Technical Gaps to Close Before Launch

| Gap | Current State | Work Needed | Effort |
|-----|--------------|-------------|--------|
| No export_to_postgres | DocStore (JSONL) not connected to PostgreSQL | Write export script | 1 day |
| No Alembic migrations | Empty versions/ directory | Autogenerate from models | 30 min |
| Valuation API not wired | Endpoint scaffolded but no model loading | Load joblib models, feature pipeline | 2 days |
| Frontend missing types | No commercial/land property types | Add to TypeScript types | 15 min |
| No payment system | Nothing | Stripe Checkout integration | 2 days |
| No user auth | Nothing | NextAuth.js or similar | 2 days |
| No PDF generation | Nothing | WeasyPrint or Puppeteer | 2-3 days |

---

## 4. Pricing Strategy

### 4.1 Pricing Philosophy

- **Anchor against manual valuations** (EUR 250-700), not against other tech tools
- **10-30x cheaper** positions us as a no-brainer for non-regulatory use cases
- **Freemium funnel**: Free heatmap drives awareness; paid reports capture value
- **Usage-based B2B**: Banks pay per AVM call, aligning our revenue with their lending volume

### 4.2 Pricing Table

| Product | Price | Comparison |
|---------|-------|-----------|
| **Free Estimator** | EUR 0 (3/month) | Lead gen |
| **Single Report** | EUR 9 | vs. EUR 250+ manual valuation |
| **5-Pack Reports** | EUR 29 (EUR 5.80 each) | Bulk discount for active buyers |
| **Agent Monthly** | EUR 49/month (50 reports) | EUR 0.98/report -- vs. EUR 200/mo Hometrack |
| **Agent Pro** | EUR 149/month (unlimited + analytics) | Full dashboard, embeds, alerts |
| **Agency Team** | EUR 299/month (5 seats, unlimited) | Multi-agent offices |
| **Bank API** | EUR 3-8/call (volume-tiered) | vs. EUR 5-15 European AVM benchmark |
| **Bank Annual** | From EUR 15K/year | Includes SLA, audit trail, support |

### 4.3 Pricing by Market

Adjust for purchasing power:

| Market | Single Report | Agent Monthly | Rationale |
|--------|-------------|---------------|-----------|
| Malta | EUR 15 | EUR 99/month | High property values, small market, premium positioning |
| Cyprus | EUR 15 | EUR 99/month | Similar to Malta -- high foreign buyer demand |
| Bulgaria | EUR 5 | EUR 29/month | Lower property values, higher volume |
| Croatia | EUR 9 | EUR 49/month | Mid-range market |

### 4.4 Revenue Projections (Conservative, Year 1)

Assuming Malta launch Month 1, Bulgaria Month 2, Cyprus Month 5:

| Revenue Stream | Monthly by Month 6 | Monthly by Month 12 | Notes |
|---------------|--------------------|--------------------|-------|
| Single reports (B2C) | EUR 500 | EUR 2,000 | 30-130 reports/month |
| Agent subscriptions | EUR 1,500 | EUR 6,000 | 10-40 agents |
| Report packs | EUR 300 | EUR 1,000 | Buyers doing due diligence |
| Bank pilots | EUR 0 | EUR 3,000 | 1-2 bank pilots by month 10 |
| **Total MRR** | **EUR 2,300** | **EUR 12,000** | |
| **ARR run rate** | **EUR 28K** | **EUR 144K** | |

These are conservative. A single bank contract for portfolio revaluation could add EUR 50-200K/year.

---

## 5. Go-to-Market: Launch Sequence

### 5.1 Phase 1: Malta Launch (Month 1-2)

**Why Malta first:**
- Zero competition (no AVM exists at all)
- Small market = fast feedback loops (12K transactions/year vs. 196K in Bulgaria)
- Highest average transaction value (EUR 278K) = highest willingness to pay
- 15% foreign buyers who can't easily commission local valuers
- Strong English-language market (no localization needed)
- Data already mature: 32K+ RE/MAX listings, 12.1% MAPE model

**Launch checklist:**
1. Ship production app with free heatmap + paid reports
2. Launch landing page: "Malta's first AI property valuation"
3. Submit to Malta tech press (MaltaToday, Times of Malta, The Shift News)
4. Post in Malta expat Facebook groups (50K+ members)
5. Cold-email 20 Malta real estate agencies with free trial offer
6. List on Product Hunt
7. Run Google Ads: "property value malta", "house price malta" (low competition keywords)

**Week 1 targets:**
- 500 free estimations
- 10 paid reports
- 3 agent trial signups
- 1 press mention

### 5.2 Phase 2: Bulgaria Launch (Month 2-3)

**Why Bulgaria second:**
- Data already collected (54K+ listings) and models trained (12.1% MAPE)
- Massive mortgage growth (+30% YoY) = hungry bank segment
- High transaction volume (196K/year) = large funnel
- Growing foreign buyer segment

**Localization needed:**
- Bulgarian language UI (critical -- most buyers/agents don't use English for property)
- BGN currency display (with EUR equivalent)
- Bulgarian city/neighborhood names

**Launch approach:**
- Partner with 1-2 Bulgarian real estate portals or agencies for distribution
- Target the Sofia market first (highest value, best data coverage)
- Bulgarian tech press: Capital.bg, Dnevnik.bg
- Facebook/Instagram ads targeting Bulgarian property searchers

### 5.3 Phase 3: Cyprus (Month 5-6)

**Why Cyprus third:**
- Highest foreign buyer % (27%) = most likely to pay for English-language tool
- Record EUR 5.71B transaction market in 2024
- Existing competitors are rudimentary (BuySellCyprus AVM disclaims its own accuracy)
- Requires new scraper (Bazaraki.com -- Apify actor already exists)

### 5.4 Phase 4: Croatia (Month 9-12)

**Why Croatia last:**
- Sprengnetter already has presence via Crozilla partnership
- Requires differentiation strategy: focus on consumer/agent segment (Sprengnetter is bank-focused)
- Highest population and transaction volume -- biggest opportunity if we can compete

---

## 6. Customer Acquisition Strategy

### 6.1 Channel Strategy by Segment

#### B2C: Individual Buyers & Sellers

| Channel | Tactic | Cost | Expected CAC |
|---------|--------|------|-------------|
| **SEO** | "Property value [city]" content pages per locality | Time only | EUR 0 (organic) |
| **Google Ads** | "Malta property value", "imot cena sofia" etc. | EUR 0.50-3/click | EUR 5-15/paid report |
| **Facebook/Instagram** | Carousel ads showing heatmap + "Find your property's value" | EUR 1-5/click | EUR 10-25/report |
| **Expat communities** | Malta/Cyprus expat Facebook groups, forums, Reddit r/malta | Free | EUR 0 |
| **Content marketing** | "Malta Property Market Q2 2026" quarterly reports (free) | Time only | Email capture |
| **Referral** | "Share and get 1 free report" | EUR 9/referral | EUR 9 |

**SEO is the #1 long-term channel.** People searching "how much is my apartment worth in Sliema" or "цена на апартамент в София" (apartment price Sofia) have immediate purchase intent. There are currently NO authoritative pages ranking for these queries with actual data-driven answers.

#### B2B: Real Estate Agents

| Channel | Tactic | Expected CAC |
|---------|--------|-------------|
| **Direct outreach** | Cold email to agents listed on RE/MAX, Century21, Engel & Volkers Malta | EUR 50-100 |
| **Free trial** | 30-day free Agent Pro trial, no credit card required | Conversion cost |
| **Agent association events** | Malta Real Estate Association meetings, chamber of commerce | EUR 100-200 |
| **Referral from agents** | Commission per referred subscription | EUR 30-50 |
| **LinkedIn** | Target "real estate agent malta/bulgaria/cyprus" | EUR 20-50 |

**The agent pitch:** "Your clients ask 'is this a fair price?' You currently guess or spend EUR 250 on a Perit. With PriceMap, give them an instant, data-backed answer for under EUR 1/property. Embed our widget on your website and look like the most sophisticated agency in Malta."

#### B2B: Banks & Mortgage Lenders

| Channel | Tactic | Timeline |
|---------|--------|----------|
| **Direct approach** | Target Head of Lending / Chief Risk Officer at major banks | Month 4-6 |
| **Regulatory angle** | "EBA/CRR3 now requires AVM capability -- we're the only provider in Malta" | Ongoing |
| **Industry events** | Malta Finance Forum, banking conferences | Annual |
| **Pilot program** | Free 90-day pilot: validate our AVM against their manual valuations | Month 6-9 |
| **Warm intro via agents** | Agents who use PriceMap introduce us to their banking contacts | Organic |

**Target banks (Malta):**
- Bank of Valletta (largest, 48% market share)
- HSBC Malta
- APS Bank
- BNF Bank
- Lombard Bank
- MeDirect

**The bank pitch:** "You process ~5,200 mortgages/year. Each requires a EUR 250+ manual valuation that takes 1-2 weeks. PriceMap gives you an instant AVM for EUR 5-10 per property. Use it for pre-screening (instant go/no-go), portfolio revaluation (EBA-compliant), and monitoring (automated alerts on collateral value changes). We're the only AVM provider in Malta."

### 6.2 Content & SEO Strategy

**High-intent keywords to target** (all currently underserved):

| Keyword (English) | Keyword (Local) | Search Intent | Content |
|-------------------|-----------------|---------------|---------|
| "property value malta" | -- | Valuation | Free estimator landing page |
| "house prices sliema" | -- | Research | Locality price page with stats |
| "apartment price sofia" | "цена апартамент софия" | Valuation | Free estimator (Bulgarian) |
| "how much is my property worth cyprus" | -- | Valuation | Free estimator landing page |
| "malta property market 2026" | -- | Research | Quarterly market report (gated PDF) |
| "bulgaria real estate investment" | -- | Investment | Market analysis + free tool |

**Content calendar:**
- **Weekly**: Locality spotlight (price trends, new listings stats for one area)
- **Monthly**: Market report (Malta and Bulgaria price trends, new supply, demand signals)
- **Quarterly**: Deep-dive report (gated PDF, email capture -- "Malta Property Market Q2 2026")
- **Ongoing**: Agent success stories, "how we built the AVM" technical blog posts

### 6.3 Partnership Strategy

| Partner Type | Examples | What They Get | What We Get |
|-------------|---------|--------------|-------------|
| Real estate portals | MaltaPark, Imot.bg | "Powered by PriceMap" estimated values on their listings | Distribution, data access |
| Property lawyers/notaries | Malta/Cyprus conveyancing firms | Quick price check for due diligence | Referrals to buyers/sellers |
| Mortgage brokers | Independent Malta/CY brokers | Pre-qualification tool | Bank introductions |
| Relocation agencies | Malta expat relocation firms | "Fair price?" tool for clients | Foreign buyer segment |
| Property developers | Malta/BG developers | Market positioning data | Bulk subscription revenue |

**Priority partnership: MaltaPark**. They have 4K+ listings but no valuation tool. A "PriceMap Estimate" badge on each listing would give us massive distribution in exchange for enhancing their platform. We already scrape their data.

---

## 7. Outreach Plan (First 30 Days)

### Week 1: Pre-launch
- [ ] Ship Malta MVP (free heatmap + paid reports)
- [ ] Create landing page with clear value proposition
- [ ] Set up Stripe, basic analytics (Plausible or PostHog), email capture
- [ ] Write 3 blog posts: "Malta's First AI Property Valuation", "How Accurate Is Our Model?", "Sliema vs St Julian's: Price Comparison"
- [ ] Prepare press kit (screenshots, founder quote, model accuracy stats)

### Week 2: Soft Launch
- [ ] Post in Malta expat Facebook groups (Malta Pair Up, Expats Malta, Moving to Malta -- combined 60K+ members)
- [ ] Submit to r/malta, r/realestate
- [ ] Email 20 Malta real estate agencies with personalized pitch + free trial
- [ ] Reach out to 3 Malta tech/property journalists
- [ ] Launch Google Ads (EUR 20/day budget): "property value malta", "house price calculator malta"

### Week 3: Press & Partnerships
- [ ] Product Hunt launch
- [ ] Pitch MaltaPark partnership (add estimated values to their listings)
- [ ] Contact Malta Real Estate Association about presenting at next meeting
- [ ] Email 5 Malta mortgage brokers
- [ ] Post technical blog: "How We Built Malta's First Property AI" (Hacker News, LinkedIn)

### Week 4: Iterate & Expand
- [ ] Analyze first 500 free valuations: which localities, which property types, drop-off points
- [ ] A/B test report pricing (EUR 9 vs EUR 15 vs EUR 19)
- [ ] Follow up on all agent trial signups
- [ ] Ship Bulgaria on production
- [ ] Plan Bulgaria soft launch

---

## 8. Pricing Experiments to Run

### 8.1 First Month Tests

| Test | Variants | Success Metric |
|------|----------|---------------|
| Free limit | 1 vs 3 vs 5 free/month | Conversion to paid |
| Report price | EUR 9 vs EUR 15 vs EUR 19 | Revenue per visitor |
| Report format | Basic (price + range) vs Full (comparables + SHAP) | Willingness to pay |
| Agent trial | 14-day vs 30-day free trial | Trial-to-paid conversion |
| Annual discount | Monthly vs annual (20% discount) | LTV improvement |

### 8.2 Key Metrics to Track

| Metric | Target (Month 1) | Target (Month 6) |
|--------|------------------|------------------|
| Free valuations/day | 20 | 100 |
| Paid reports/month | 10 | 100 |
| Agent subscriptions | 3 | 20 |
| Free-to-paid conversion | 2% | 5% |
| Report NPS | 40+ | 50+ |
| Churn (agent monthly) | <15% | <10% |

---

## 9. Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| **Model accuracy questioned** | HIGH | HIGH | Be transparent about MAPE (12%). Show confidence intervals. Compare to "no tool at all" baseline. Publish methodology. |
| **Legal challenge** ("your valuation cost me money") | MEDIUM | HIGH | Prominent disclaimers: "estimate only, not a formal valuation." Terms of service limiting liability. Consider professional indemnity insurance. |
| **Sprengnetter expands to Malta/BG** | LOW | HIGH | Move fast. Lock in agent relationships and bank pilots before they arrive. Our local data depth is 12+ months ahead. |
| **Data source blocked** (RE/MAX changes API) | MEDIUM | MEDIUM | Diversify sources. MaltaPark + PropertyMarket (Playwright) as fallbacks. Retrain models regularly. |
| **Low willingness to pay** | MEDIUM | MEDIUM | Start with aggressive pricing (EUR 5-9). Optimize funnel before raising prices. The free tier ensures traffic regardless. |
| **Regulatory requirement for certified AVM** | LOW | MEDIUM | Pursue EAA membership once banks express interest. The cert process takes 6-12 months but our model quality is approaching eligibility. |
| **Bulgaria needs local language** | HIGH | MEDIUM | Prioritize Bulgarian translation early. Use AI-assisted translation for UI strings. |

---

## 10. Scaling Roadmap (12-24 Months)

### Month 1-3: Prove Product-Market Fit
- Launch Malta MVP
- Launch Bulgaria
- Target: 50 paid reports/month, 10 agent subscriptions
- Revenue target: EUR 2K MRR

### Month 4-6: Agent Distribution
- Agent dashboard with bulk tools
- Embeddable widget
- First partnership deal (MaltaPark or similar)
- Target: 30 agent subscriptions, 200 reports/month
- Revenue target: EUR 8K MRR

### Month 7-9: Bank Pilots & Cyprus
- Launch Cyprus
- Begin 2 bank pilot programs (Malta + Bulgaria)
- API documentation and developer portal
- Target: 2 bank pilots, 50 agents, 500 reports/month
- Revenue target: EUR 15K MRR

### Month 10-12: Bank Contracts & Croatia
- Convert bank pilots to paid contracts
- Launch Croatia
- Apply for EAA membership
- Target: 1 bank contract, 80 agents, 1000 reports/month
- Revenue target: EUR 30K MRR (EUR 360K ARR)

### Month 13-18: Scale B2B
- Expand to more banks in each country
- Add insurance company segment (property insurance valuations)
- Portfolio monitoring product (automated alerts)
- Target: EUR 80K MRR (EUR 960K ARR)

### Month 19-24: New Markets or Deepen
- Option A: Add 2-3 more underserved EU markets (Latvia, Lithuania, Romania)
- Option B: Deepen existing markets with transaction data access, premium features
- Option C: White-label AVM for European banking platforms
- Target: EUR 150K+ MRR

---

## 11. Key Strategic Decisions

### 11.1 Launch as B2C or B2B First?

**Recommendation: B2C first, then B2B.**

B2C (free tool + paid reports) provides:
- Fast feedback on product quality and market demand
- SEO traffic and brand awareness
- Social proof and testimonials for B2B sales conversations
- Revenue from day 1 (even if small)

B2B (agent subscriptions, bank API) provides:
- Higher revenue per customer
- Recurring revenue
- But: longer sales cycles (banks: 3-6 months), requires more features

**Sequence**: Launch free tool + paid reports (Week 1) --> Add agent subscriptions (Month 2) --> Begin bank outreach (Month 4) --> Close first bank deal (Month 8-10).

### 11.2 Build for Malta Only or Multi-Country from Day 1?

**Recommendation: Malta-first, but architect for multi-country.**

The production app should handle country selection from day 1 (the frontend already has a country selector). But marketing, partnerships, and customer support should focus on Malta exclusively for the first 6-8 weeks. Bulgaria launches as soon as localization is ready.

### 11.3 Transparency vs. Black Box?

**Recommendation: Maximum transparency.**

In markets with no AVM history, trust is the #1 barrier. Publish:
- Model accuracy metrics (MAPE, within-10%, within-20%)
- Methodology (LightGBM + XGBoost ensemble, spatial CV, what features matter)
- Data sources (RE/MAX Malta, MaltaPark -- public data, clearly attributed)
- Confidence scores on every valuation

This positions us as the credible, scientific alternative to guesswork. It also makes it harder for competitors to enter without similar transparency.

### 11.4 Brand Positioning

**"The first data-driven property valuation for [country]."**

Not: "AI-powered" (overused, triggers skepticism)
Not: "Instant valuation" (sounds like a gimmick)
Yes: "Data-driven" (credible, specific)
Yes: "Malta's first" (novelty, first-mover)
Yes: "12% accuracy" (concrete, verifiable)

**Tagline options:**
- "Know the real value." (simple, direct)
- "Every property. Fairly priced." (aspirational)
- "The price map for markets that don't have one." (descriptive, explains the gap)

---

## 12. Immediate Next Steps (This Week)

1. **Ship the Malta MVP** -- Connect DocStore to PostgreSQL, wire up the valuation endpoint, deploy
2. **Set up Stripe** -- Single report purchase + agent subscription flows
3. **Create the landing page** -- Clear value prop, free estimator above the fold, "Malta's First AI Property Valuation"
4. **Write the first blog post** -- "We Analyzed 32,000 Malta Properties. Here's What We Found."
5. **Prepare 20 agent emails** -- Personalized cold outreach with free trial offer
6. **Set up Google Ads** -- EUR 20/day on "property value malta" keywords
7. **Legal**: Add disclaimers to all valuation outputs, draft Terms of Service

---

## Appendix A: Model Accuracy Context

### Current Performance vs. Benchmarks

| Model | MAPE | Context |
|-------|------|---------|
| **PriceMap Malta Sales** | **12.1%** | Asking prices, 2.3K samples, spatial CV |
| **PriceMap Malta Rents** | **18.2%** | Asking prices, 9.4K samples, spatial CV |
| **PriceMap Bulgaria Sales** | **12.1%** | Asking prices, 7.6K samples, spatial CV |
| **PriceMap Bulgaria Rents** | **13.5%** | Asking prices, 9.2K samples, spatial CV |
| Zillow Zestimate (US) | 7.3% | Transaction prices, millions of samples |
| HouseCanary (US) | 5-8% | 6-model ensemble, massive dataset |
| Academic AVMs (typical) | 10-25% | Asking prices, limited features |
| GPBoost German apartments | 8-12% | 1.5M listings |

**Our models are competitive with academic benchmarks and approaching professional AVM quality**, especially considering we use asking prices (not transactions) and have relatively small datasets. The 12.1% MAPE on Malta sales means that for a EUR 300K property, our estimate is typically within EUR 36K of the asking price -- useful for any buyer, seller, or agent trying to gauge fair value.

### Accuracy Improvement Path

| Improvement | Expected MAPE Reduction | Timeline |
|------------|------------------------|----------|
| Distance to beach/marina/airport | Already included | Done |
| More MaltaPark data (with geocoding) | 0.5-1pp | 1 week |
| Transaction price data (Malta PPR) | 2-4pp | Requires subscription |
| 2x more training data (ongoing scraping) | 1-2pp | Ongoing |
| GPBoost spatial random effects | 1-2pp | 2 weeks |

Target: 10% MAPE on Malta sales within 6 months.

## Appendix B: Competitor Quick Reference

| Competitor | URL | Market | Type | Threat |
|-----------|-----|--------|------|--------|
| Valur.mt | valur.mt/calculator | Malta | Basic calculator | Low |
| BuySellCyprus AVM | buysellcyprus.com/avm | Cyprus | Rudimentary AVM | Low-Med |
| Realtor.com.cy | realtor.com.cy/avm | Cyprus | AVM reports | Low-Med |
| HomeValues.com.cy | homevalues.com.cy | Cyprus (Nicosia) | Basic estimator | Low |
| BulgarianProperties | bulgarianproperties.com | Bulgaria | Lead-gen calculator | Low |
| CroReal Price Map | croreal.com/pricemap.php | Croatia | Area averages | Low |
| Sprengnetter | sprengnetter.net | Croatia (+ DE, AT, SI, BA, RS, ME) | Bank-grade AVM | High (HR only) |
| Arvio | arvio.ai | Slovenia | ML AVM | Med (potential HR) |
| PriceHubble | pricehubble.com | CH, FR, DE, AT, UK, BE, CZ, SK | ML AVM + analytics | Med (expansion) |
| SonarHome | sonarhome.pl | PL, HU, RO | AVM + lead gen | Low-Med |
