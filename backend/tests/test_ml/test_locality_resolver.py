import json
from pathlib import Path

import pytest

from src.ml.locality_resolver import is_gozo, normalize, resolve_locality

CENTROIDS = json.loads(
    (Path(__file__).resolve().parents[2] / "src" / "ml" / "mt_locality_centroids.json").read_text()
)
KEYS = list(CENTROIDS.keys())


def coord(key):
    return CENTROIDS[key][0], CENTROIDS[key][1]


def test_normalize_strips_maltese_articles_and_diacritics():
    assert normalize("Tas-Sliema") == "sliema"
    assert normalize("Il-Gżira") == "gzira"
    assert normalize("Iż-Żejtun") == "zejtun"
    assert normalize("Birżebbuġa") == "birzebbuga"
    assert normalize("Il-Mellieħa") == "mellieha"


def test_is_gozo_by_latitude():
    assert is_gozo(36.04) is True
    assert is_gozo(35.91) is False
    assert is_gozo(None) is False


@pytest.mark.parametrize(
    "endonym,expected",
    [
        ("Tas-Sliema", "Sliema"),
        ("Il-Gżira", "Gzira"),
        ("Iż-Żejtun", "Zejtun"),
        ("Il-Mellieħa", "Mellieha"),
        ("Birżebbuġa", "Birzebbuga"),
        ("San Ġiljan", "St Julian's"),          # alias
        ("San Pawl il-Baħar", "St Paul's Bay"),  # alias
        ("Bugibba", "St Paul's Bay"),            # alias (sub-locality)
        ("Il-Furjana", "Floriana"),              # alias
        ("Bormla", "Cospicua"),                  # alias
        ("L-Imsida", "Msida"),                   # fuzzy (Im- euphonic)
    ],
)
def test_maltese_endonyms_resolve_to_encoder_keys(endonym, expected):
    lat, lon = coord(expected)
    assert resolve_locality(endonym, lat, lon, KEYS) == expected


def test_gozo_malta_name_collision_resolved_by_latitude():
    # "Zebbug" exists on both islands; latitude must disambiguate.
    mlat, mlon = coord("Zebbug")
    glat, glon = coord("Gozo - Zebbug")
    assert resolve_locality("Iż-Żebbuġ", mlat, mlon, KEYS) == "Zebbug"
    assert resolve_locality("Iż-Żebbuġ", glat, glon, KEYS) == "Gozo - Zebbug"
    # Gozo's Victoria is locally called Rabat, colliding with main-island Rabat.
    rlat, rlon = coord("Rabat")
    vlat, vlon = coord("Gozo - Victoria")
    assert resolve_locality("Ir-Rabat", rlat, rlon, KEYS) == "Rabat"
    assert resolve_locality("Ir-Rabat", vlat, vlon, KEYS) == "Gozo - Victoria"


def test_unknown_name_falls_back_to_nearest_centroid():
    lat, lon = coord("Sliema")
    # Garbage name -> geographic fallback still yields the right locality.
    assert resolve_locality("Zzz Unknown Place", lat, lon, KEYS) == "Sliema"


def test_no_match_without_coords_returns_none():
    assert resolve_locality("Totally Unknown", None, None, KEYS) is None
