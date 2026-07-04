# Checking domain availability (reliably)

How to check whether a domain is free to register, from the command line, without a
paid API — and without getting fooled by the many ways naive checks lie. Used when
naming/branding the product; kept here for later reference.

**TL;DR:** use `scripts/check_domains.py` (calibrated, handles all TLD types):

```bash
python scripts/check_domains.py --names valura pretio cadastra --tlds com eu homes app io
```

It prints, per TLD, a calibration line plus `AVAILABLE` / `taken` per name. If a TLD's
calibration fails, its results are marked `unverified` (don't trust them).

---

## Why naive checks lie (the traps we hit)

- **`rdap.org` is ambiguous.** It returns HTTP **404 for both** "domain available" **and**
  "this TLD has no RDAP service." So querying an unsupported TLD makes *every* name look
  free. (This is what falsely showed `.io`/`.co` as wide open, including `google.io`.)
- **Some ccTLDs aren't in the IANA RDAP bootstrap at all** (`.io`, `.co`, `.eu`). There's
  no authoritative RDAP server to hit — you must fall back to DNS.
- **EURid's `.eu` RDAP** (`rdap.eu`) is frequently unreachable / GDPR-restricted from a
  given network (we got connection timeouts).
- **A missing A record ≠ available.** Registered domains often have no apex `A` (MX-only,
  parked, `www`-only), so `socket.gethostbyname` "fails" on live registrations.
- **DNS `SERVFAIL` (Status 2) ≠ available.** It means a *registered* domain whose DNS is
  broken (e.g. DNSSEC failure). Only **`NXDOMAIN` (Status 3)** means available.
  (`cadastra.eu` returned SERVFAIL on two resolvers → registered, not free.)

## The reliable method

1. **Bootstrapped gTLDs → authoritative RDAP.** Look up the TLD's RDAP server in the IANA
   bootstrap (`https://data.iana.org/rdap/dns.json`), then query `{base}domain/{fqdn}`.
   **HTTP 404 = available, 200 = taken.** Works for `.com`, `.app`, `.homes`, `.xyz`,
   `.realestate`, `.dev`, and most gTLDs.
2. **Non-bootstrapped TLDs (ccTLDs) → DNS-over-HTTPS NS lookup.** Query
   `https://dns.google/resolve?name={fqdn}&type=NS`. **Status 3 (NXDOMAIN) = available;
   Status 0 (delegated) or 2 (SERVFAIL) = registered.** Works for `.io`, `.co`, `.eu`.
3. **Always calibrate the TLD first.** `nic.<tld>` (registry-owned, always registered)
   must read **taken** and a random label must read **available**. If either fails, the
   method can't be trusted for that TLD in this environment — mark results unverified.

## Ad-hoc one-liners (no script)

```bash
# .com (and .net) — Verisign RDAP: 404 available, 200 taken
curl -sL -o /dev/null -w "%{http_code}\n" https://rdap.verisign.com/com/v1/domain/NAME.com

# Find any gTLD's authoritative RDAP server, then query it
curl -s https://data.iana.org/rdap/dns.json | python3 -c \
  "import json,sys;d=json.load(sys.stdin);print([u for t,u in ((s[0],s[1]) for s in d['services']) if 'homes' in t])"
curl -sL -o /dev/null -w "%{http_code}\n" https://rdap.centralnic.com/homes/domain/NAME.homes

# ccTLD (.io/.co/.eu) — DNS-over-HTTPS NS delegation; read the "Status" field
curl -s "https://dns.google/resolve?name=NAME.eu&type=NS" | python3 -m json.tool | grep '"Status"'
#   Status 3 = AVAILABLE (NXDOMAIN);  0 or 2 = registered
```

## Interpreting results

| Signal | Meaning |
|--------|---------|
| RDAP HTTP **404** | Available |
| RDAP HTTP **200** | Registered (taken) |
| DoH **Status 3** (NXDOMAIN) | Available |
| DoH **Status 0** (NS/SOA answers) | Registered (delegated) |
| DoH **Status 2** (SERVFAIL, both resolvers) | Registered, DNS broken — **not** available |
| `rdap.org` 404 | **Ambiguous** — available *or* unsupported TLD. Don't use it alone. |

## Caveats

- This is a strong **registry-level** signal, not a purchase guarantee. A registrar still
  determines **premium pricing**, registry **reserved/blocked** names, and **trademark**
  conflicts. Confirm at Cloudflare Registrar / Namecheap before buying.
- ccTLDs may have registration **eligibility rules** (e.g. `.eu` requires an EU presence;
  `.mt` has local requirements). RDAP/DNS won't tell you that — check the registry policy.
- DoH gives *delegation* status; a just-registered domain can briefly lack NS delegation
  (would read available for minutes). Re-check if a result looks surprising.
