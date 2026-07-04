#!/usr/bin/env python3
"""Check domain availability across TLDs, reliably, with per-TLD calibration.

Standalone (stdlib only) — runs from anywhere, no repo imports.

WHY THIS EXISTS — naive checks lie:
  - rdap.org returns HTTP 404 for BOTH "available" AND "this TLD has no RDAP
    service", so an unsupported TLD looks like every name is free.
  - Several popular ccTLDs (.io, .co, .eu) are NOT in the IANA RDAP bootstrap.
  - EURid's .eu RDAP is frequently unreachable / GDPR-restricted.
  - A missing A record != available (parked / MX-only / DNSSEC-broken domains).
  - DNS SERVFAIL (Status 2) means a REGISTERED domain with broken DNS, NOT free.

METHOD:
  - TLDs in the IANA RDAP bootstrap (https://data.iana.org/rdap/dns.json): query
    the *authoritative* RDAP server. HTTP 404 = available, 200 = taken.
  - Other TLDs (ccTLDs): DNS-over-HTTPS NS lookup via dns.google.
    Status 3 (NXDOMAIN) = available; 0 (delegated) or 2 (SERVFAIL) = registered.
  - CALIBRATE every TLD before trusting it: `nic.<tld>` must read "taken" and a
    random label must read "available". If calibration fails, results for that
    TLD are marked UNVERIFIED (the environment can't check it reliably).

USAGE:
  python check_domains.py --names valura pretio cadastra --tlds com eu homes app
  python check_domains.py --names valugeo --tlds com eu

This is a strong signal, not gospel — always confirm at a registrar (which also
gives premium/pricing and trademark status) before buying.
"""
import argparse
import json
import random
import string
import urllib.error
import urllib.request

IANA_BOOTSTRAP = "https://data.iana.org/rdap/dns.json"
_bootstrap_cache = None


def _get(url, timeout=12):
    req = urllib.request.Request(
        url, headers={"Accept": "application/rdap+json, application/json"}
    )
    return urllib.request.urlopen(req, timeout=timeout)


def rdap_base(tld):
    """Authoritative RDAP base URL for a TLD from the IANA bootstrap, or None."""
    global _bootstrap_cache
    if _bootstrap_cache is None:
        _bootstrap_cache = json.load(_get(IANA_BOOTSTRAP))
    for tlds, urls in ((s[0], s[1]) for s in _bootstrap_cache.get("services", [])):
        if tld in tlds:
            base = urls[0]
            return base if base.endswith("/") else base + "/"
    return None


def check_rdap(fqdn, base):
    try:
        _get(f"{base}domain/{fqdn}")
        return "taken"
    except urllib.error.HTTPError as e:
        return "available" if e.code == 404 else f"error({e.code})"
    except Exception:
        return "error"


def check_doh(fqdn):
    try:
        d = json.load(_get(f"https://dns.google/resolve?name={fqdn}&type=NS"))
    except Exception:
        return "error"
    status = d.get("Status")
    if status == 3:            # NXDOMAIN
        return "available"
    if status in (0, 2):       # delegated, or registered-but-DNS-broken (SERVFAIL)
        return "taken"
    return "inconclusive"


def _rand_label():
    return "zz" + "".join(random.choice(string.ascii_lowercase) for _ in range(12))


def method_for(tld):
    base = rdap_base(tld)
    return ("rdap", base) if base else ("doh", None)


def check_one(name, tld, method, base):
    fqdn = f"{name}.{tld}"
    return check_rdap(fqdn, base) if method == "rdap" else check_doh(fqdn)


def calibrate(tld, method, base):
    """nic.<tld> should read 'taken'; a random label should read 'available'."""
    known = check_one("nic", tld, method, base)
    freeish = check_one(_rand_label(), tld, method, base)
    return (known == "taken" and freeish == "available"), known, freeish


def main():
    ap = argparse.ArgumentParser(description="Calibrated domain availability check.")
    ap.add_argument("--names", nargs="+", required=True)
    ap.add_argument("--tlds", nargs="+", default=["com"])
    args = ap.parse_args()

    for tld in args.tlds:
        method, base = method_for(tld)
        ok, known, freeish = calibrate(tld, method, base)
        src = f"RDAP {base}" if method == "rdap" else "DoH dns.google"
        flag = "" if ok else "  [!] CALIBRATION FAILED -> results UNVERIFIED"
        print(f"\n.{tld}  (via {src}){flag}")
        print(f"    calibration: nic.{tld}={known}  random={freeish}")
        for name in args.names:
            result = check_one(name, tld, method, base)
            mark = {"available": "AVAILABLE", "taken": "taken"}.get(result, result)
            if not ok:
                mark += " (unverified)"
            print(f"    {name}.{tld:12} {mark}")


if __name__ == "__main__":
    main()
