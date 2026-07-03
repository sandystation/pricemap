"""Resolve a geocoder-returned locality to a model encoder key.

The valuation encoders key locality by anglicized RE/MAX names (Sliema,
"Gozo - Victoria"). Nominatim returns Maltese endonyms (Tas-Sliema, Ix-Xaghra,
San Giljan) that never match, so without this locality_enc silently drops to
NaN — and Gozo (locally called Rabat, and sharing names like Zebbug with the
main island) is mis-resolved. Resolution order:

  1. island partition by latitude (Gozo is north of 36.0), so a Gozo request
     only ever matches Gozo keys and vice-versa;
  2. exact / prefix-stripped / article-normalized name match;
  3. fuzzy match (difflib) on normalized names;
  4. nearest training centroid by coordinates — the guaranteed non-NaN fallback.
"""
import difflib
import json
import math
import re
import unicodedata
from pathlib import Path

# Maltese special letters -> ASCII (h-bar/dotted letters don't NFKD-decompose).
_MALTESE = str.maketrans({
    "ġ": "g", "Ġ": "g", "ħ": "h", "Ħ": "h",
    "ż": "z", "Ż": "z", "ċ": "c", "Ċ": "c",
})

# Maltese definite-article / locative prefixes to strip (NOT san/santa/st).
_ARTICLE_PREFIXES = (
    "tas-", "tal-", "tad-", "taz-", "ta'-", "ta' ", "ta-",
    "il-", "l-", "is-", "ix-", "iz-", "in-", "ir-", "id-", "it-", "ic-", "ig-",
    "hal-", "hal ", "haz-", "haz ", "had-", "had ",
)

# Structural aliases where the Maltese name differs from the anglicized key
# beyond article/diacritic differences. Keys are normalize()'d Maltese forms.
_ALIASES = {
    "san giljan": "St Julian's",
    "san pawl il bahar": "St Paul's Bay",
    "bugibba": "St Paul's Bay",
    "qawra": "St Paul's Bay",
    "furjana": "Floriana",
    "bormla": "Cospicua",
    "birgu": "Vittoriosa",
    "citta vittoriosa": "Vittoriosa",
    "isla": "Senglea",
    "citta invicta": "Senglea",
    "belt valletta": "Valletta",
    "citta umilissima": "Cospicua",
}

_FUZZY_CUTOFF = 0.82
_CENTROIDS_PATH = Path(__file__).resolve().parent / "mt_locality_centroids.json"

_centroids_cache: dict[str, list[float]] | None = None


def _centroids() -> dict[str, list[float]]:
    global _centroids_cache
    if _centroids_cache is None:
        try:
            _centroids_cache = json.loads(_CENTROIDS_PATH.read_text())
        except (OSError, ValueError):
            _centroids_cache = {}
    return _centroids_cache


def normalize(name: str) -> str:
    """Lowercase, transliterate Maltese letters, strip article prefixes/punct."""
    if not name:
        return ""
    s = name.strip().translate(_MALTESE)
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = s.lower().replace("’", "'")
    changed = True
    while changed:
        changed = False
        for art in _ARTICLE_PREFIXES:
            if s.startswith(art):
                s = s[len(art):]
                changed = True
                break
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def is_gozo(lat: float | None) -> bool:
    """Gozo (and Comino) lie north of latitude 36.0; Malta's main island below."""
    return lat is not None and lat > 36.0


def _haversine_km(lat1, lon1, lat2, lon2) -> float:
    r = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    )
    return r * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _nearest_centroid(lat: float, lon: float, candidates: set[str]) -> str | None:
    best, best_km = None, math.inf
    for key, (clat, clon) in _centroids().items():
        if key not in candidates:
            continue
        km = _haversine_km(lat, lon, clat, clon)
        if km < best_km:
            best, best_km = key, km
    return best


def _norm_map(candidates: set[str]) -> dict[str, str]:
    # Strip the "Gozo - " prefix so Gozo village names match their bare endonym.
    out: dict[str, str] = {}
    for key in candidates:
        base = key[len("Gozo - "):] if key.startswith("Gozo - ") else key
        out.setdefault(normalize(base), key)
    return out


def resolve_locality(
    name: str | None,
    lat: float | None,
    lon: float | None,
    encoder_keys,
) -> str | None:
    """Return the encoder key best matching the geocoder locality, or None."""
    keys = set(encoder_keys)
    if not keys:
        return None

    # 1. Partition by island so Gozo/Malta name collisions (Zebbug, Rabat) can't cross.
    if lat is not None:
        gozo_keys = {k for k in keys if k.startswith("Gozo")}
        candidates = gozo_keys if is_gozo(lat) else (keys - gozo_keys)
        if not candidates:
            candidates = keys
    else:
        candidates = keys

    # 2. Exact match (fast path for already-anglicized names).
    if name and name in candidates:
        return name

    norm = normalize(name or "")
    if norm:
        if norm in _ALIASES and _ALIASES[norm] in candidates:
            return _ALIASES[norm]
        nmap = _norm_map(candidates)
        if norm in nmap:
            return nmap[norm]
        close = difflib.get_close_matches(norm, list(nmap), n=1, cutoff=_FUZZY_CUTOFF)
        if close:
            return nmap[close[0]]

    # 3. Geographic fallback — always yields a sensible locality when coords exist.
    if lat is not None and lon is not None:
        return _nearest_centroid(lat, lon, candidates)
    return None
