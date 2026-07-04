# Branding & domain candidates

Working shortlist for naming the product (currently "PriceMap"). Availability below
was **verified on 2026-07-04** with `scripts/check_domains.py` (calibrated RDAP + DoH —
see [domain-availability-checks.md](domain-availability-checks.md)). **Re-verify before
buying** — availability changes, and a registrar still confirms premium pricing,
reserved names, trademark, and ccTLD eligibility.

Re-check any time:
```bash
python scripts/check_domains.py --names kemm franka dar --tlds com homes eu mt
```

## Leading candidate: `kemm`
Maltese for **"how much?"** — literally the question a valuation answers. Short,
brandable, works internationally, distinctly Maltese without locking to Malta.
- **`kemm.homes`** ✅ (on-theme TLD) · **`kemmvalue.com`** ✅ · `kemmworth.com` ✅ ·
  `kemmly.com` ✅ · `kemm.mt` ✅ (eligibility — see caveats). *(`kemm.com`/`kemm.eu` taken.)*

## Maltese-rooted options (verified free)
| Word | Meaning | Free domains |
|------|---------|--------------|
| **kemm** | "how much?" | kemm.homes, kemmvalue.com, kemmworth.com, kemmly.com, kemm.mt |
| **franka** | globigerina limestone Malta is built from | franka.homes, franka.mt |
| **dar** | house / home | darvalue.com, darhomes.eu, darvista.{homes,eu,mt} |
| **bejt** | roof / rooftop | bejt.homes, bejt.eu, bejt.mt |
| **ġebla** | stone | gebla.homes |
| **valur** | value | valur.homes; valurja.{com,homes,eu} (coined) |
| **belt** | city (il-Belt = Valletta) | belt.homes, belt.mt |
| **xemx** | sun | xemx.homes |
| blend | dar+value / bejt+value | bejtvalue.com, darcasa.{homes,eu} |

## Pan-European coined options (verified free)
Better fit if keeping the multi-country (MT/BG/CY/HR) ambition over a Malta-first signal.
- **Matching `.com` + `.eu` pairs:** `valugeo` (value+geo — on-theme), `valplot`,
  `valunda`, `valonda`, `domvalor` — all free on **both** `.com` and `.eu`.
- **`.eu` only:** propvalor.eu (property+value), valquo.eu, pretora.eu, estivo.eu,
  valstra.eu, valbase.eu, comptra.eu.
- **`.app`:** pretio.app.

## "Nice" names — bare `.com`/`.eu` taken, but usable forms free
The strong single words (valura, pretio, cadastra, comparo, estima, valoria) are all
squatted on `.com`/`.eu`. Options that keep the name:
- **On `.homes` (all free):** valura.homes, cadastra.homes, pretio.homes, comparo.homes,
  estima.homes, valoria.homes.
- **Prefixed `.com` (free):** getcadastra.com, cadastrahq.com, usecadastra.com,
  usevalura.com, valuraapp.com, getpretio.com, pretiohq.com, comparohq.com, estimahq.com,
  valoriahq.com.
- Note: **"cadastra"** = coined from *cadastre* (the land/property register; Greek→Italian
  *catasto*→Portuguese *cadastro*). Pan-European, **not** a Maltese word.

## Caveats
- **`.mt` eligibility:** registering a `.mt` domain generally requires a Maltese
  presence/registrant (check NIC Malta / registrar). Good as a local redirect if you have
  a Malta entity; not a quick self-serve grab otherwise.
- **Convention:** frontend on the apex, backend on `api.<domain>` (what the deploy config
  assumes: `API_DOMAIN` / `CORS_ORIGINS` / `NEXT_PUBLIC_API_URL`).
- A Maltese name reads **Malta-first**; a coined/Latin name reads **pan-EU**. `kemm` is
  short enough to work either way.

## Recommendation
1. **`kemm`** — `kemm.homes` + `kemmvalue.com` (the brand *is* the question the product
   answers; local story, global-friendly).
2. **`franka.homes`** — if you want a premium, architectural, unmistakably-Maltese brand.
3. **`valugeo.com` + `valugeo.eu`** — if you'd rather stay pan-European and keep `.com`.
