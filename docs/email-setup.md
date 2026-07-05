# Email infrastructure runbook — transactional (Resend) + human inbox (Google Workspace)

A reusable setup for hosting **both** on one domain, without paying for extra
Workspace seats. Worked example: `casaval.eu`. For a new project, swap the domain
and re-read the exact records from the two dashboards — the structure and the
gotchas are identical.

## The mental model (read this first)

**Outbound and inbound are independent**, controlled by *different* DNS records,
so two providers coexist on one domain with zero conflict:

| Concern | Provider | Authenticated by |
|---|---|---|
| **Outbound** transactional mail (verification, reset, receipts) | **Resend** (API) | DKIM on `resend._domainkey` + a MAIL-FROM subdomain (`send.<domain>`: MX + SPF) |
| **Inbound** + human read/reply (`hello@`, `support@`) | **Google Workspace** | apex `MX` + apex SPF + DKIM on `google._domainkey` |

The trick: Resend lives on the **`send.` subdomain** (+ its own DKIM selector),
Google owns the **apex** (MX/SPF + its own DKIM selector). Different hosts →
they never collide. **Never put two `v=spf1` records on the same host.**

## Canonical DNS record map (`casaval.eu`)

| Host | Type | Value | Owner / purpose |
|---|---|---|---|
| `@` | MX | `smtp.google.com` (priority 1) | Workspace inbound |
| `@` | TXT | `v=spf1 include:_spf.google.com ~all` | SPF for mail sent *from* Workspace |
| `@` | TXT | `google-site-verification=…` | Workspace domain ownership |
| `google._domainkey` | TXT | `v=DKIM1; k=rsa; p=…` | Workspace DKIM (generate + enable in Admin) |
| `send` | MX | `feedback-smtp.<region>.amazonses.com` (10) | Resend/SES MAIL-FROM (bounces) |
| `send` | TXT | `v=spf1 include:amazonses.com ~all` | Resend/SES MAIL-FROM SPF |
| `resend._domainkey` | TXT | `p=…` | Resend DKIM |
| `@` A / `api` A | A | server IP | the app itself (unrelated to mail) |

`_dmarc` TXT (e.g. `v=DMARC1; p=none; rua=mailto:you@domain`) is optional but
recommended once both senders are green.

## Setup steps

### A. Resend (outbound) — do first
1. Resend → **Domains → Add** the apex domain (`casaval.eu`).
2. Add every record Resend lists (DKIM `resend._domainkey`, and the `send`
   subdomain MX + SPF). Use the **exact** values from the dashboard.
3. Click **Verify DNS Records**. Wait until the domain badge reads **Verified**.

### B. Google Workspace (inbound + human send/receive) — free via a domain *alias*
1. Admin console → **Account → Domains → Manage domains → Add a domain**.
   Choose **domain alias** (of your existing primary domain) — an alias is
   **free** and adds `@casaval.eu` addresses to existing users. A *secondary
   domain* or a *new user* costs a seat.
2. Verify ownership via the `google-site-verification` TXT.
3. **Activate Gmail** → add the MX record it shows (`smtp.google.com`, pri 1).
4. Add apex SPF `v=spf1 include:_spf.google.com ~all`.
5. Admin → **Apps → Google Workspace → Gmail → Authenticate email (DKIM)** →
   generate the key, add the `google._domainkey` TXT, then **Start authentication**.
6. Give yourself the address: add `hello@casaval.eu` as an **email alias** on your
   user (Users → user → Add alternate emails), or set a **catch-all** route
   (Apps → Gmail → Routing). Now you read/reply natively in Gmail.

### C. No Workspace? Free alternatives for inbound
- **Forwarder** (ImprovMX / Cloudflare Email Routing): point the **apex** MX at
  it, forward `hello@` → your personal Gmail; reply *as* `hello@` via Gmail
  "Send mail as" using **Resend SMTP** (`smtp.resend.com:465`, user `resend`,
  password = a Resend API key). Coexists with Resend the same way (apex vs `send.`).
- Do **not** use the registrar's built-in email forwarding if it forces an
  either/or "mail mode" that evicts your Resend `send` MX (Namecheap does this —
  see gotchas).

## App wiring (this repo: `frontend/src/lib/email.ts`)

Runtime env on the server (frontend container reads these; not `NEXT_PUBLIC_*`):

| Var | Value | Notes |
|---|---|---|
| `RESEND_API_KEY` | `re_…` | send-scoped key is fine for the app |
| `EMAIL_FROM` | `Casaval <noreply@casaval.eu>` | **must be set** — see gotcha #1 |
| `EMAIL_REPLY_TO` | `hello@casaval.eu` | replies to auth emails land in your Workspace inbox |

After changing any of these in `.env`, **recreate** the container to pick them up
(they're runtime, not build-time): `docker compose -f docker-compose.prod.yml up -d --force-recreate frontend`.

## Gotchas (each of these cost real time — learned on casaval.eu)

1. **Empty/missing `EMAIL_FROM` → Resend `422 "The domain is invalid"`.** An empty
   `from` has no domain, which Resend reports with the *same* error as an
   unverified domain — very misleading. Always verify `EMAIL_FROM` is actually set.
2. **One `v=spf1` record per host.** Resend SPF goes on `send.`, Google SPF on the
   apex — different hosts, both fine. Two SPF records on the *same* host is invalid.
3. **Domain *alias* = free; new user / secondary domain = a paid seat.** For "use my
   existing Workspace account for another domain," always choose *alias*.
4. **Registrar "mail mode" can be either/or.** Namecheap's dropdown is *Custom MX*
   **or** *Email Forwarding* — and its built-in forwarding evicts custom MX. Keep
   it on **Custom MX** so both the Google apex MX and the Resend `send` MX can
   coexist. (Its built-in forwarding conflicts with Resend; don't use it.)
5. **You can't point MX at personal Gmail** — that needs Workspace (paid) or a
   forwarder. Personal `@gmail.com` is not a valid MX target for a custom domain.
6. **Local DNS resolvers cache NEGATIVE lookups.** If you `dig` a record before it
   exists, the box caches "no such record" and keeps returning empty even after
   you add it. **Verify against the authoritative nameserver or a public resolver**,
   not a machine that queried earlier:
   ```
   dig +short @dns1.registrar-servers.com TXT send.casaval.eu   # authoritative
   dig +short @1.1.1.1 TXT send.casaval.eu                       # public
   ```
7. **A Resend domain that drops to "failed" needs a manual "Verify DNS Records"
   click** — it does not auto-recover, even once the DNS is correct again.
8. **Send-only Resend API keys can't read domain status** (`GET /domains` → 401
   `restricted_api_key`). To debug verification programmatically, use a full-access
   key; otherwise read the dashboard's per-record status.

## Verify / test commands

```bash
# 1) Authoritative DNS (ground truth — bypasses local caches)
NS=dns1.registrar-servers.com   # your registrar's nameserver
for h in "MX @" "TXT @" "MX send" "TXT send" "TXT resend._domainkey" "TXT google._domainkey"; do
  set -- $h; echo "$2 $1: $(dig +short @$NS $1 ${2/@/}.casaval.eu 2>/dev/null || dig +short @$NS $1 casaval.eu)"
done

# 2) Outbound: Resend accepts a send (returns a message id) — from a VERIFIED domain
curl -s -X POST https://api.resend.com/emails \
  -H "Authorization: Bearer $RESEND_API_KEY" -H "Content-Type: application/json" \
  -d '{"from":"Casaval <noreply@casaval.eu>","to":["hello@casaval.eu"],"subject":"test","text":"test"}'
# -> {"id":"..."} = accepted;  422 "domain is invalid" = empty/unverified from-domain

# 3) Inbound: from an EXTERNAL account, email hello@<domain> and confirm it lands
#    in the Workspace inbox. (Can't be verified purely from the server.)
```
