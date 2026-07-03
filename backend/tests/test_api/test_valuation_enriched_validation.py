import asyncio

import pytest
from fastapi import HTTPException
from starlette.datastructures import FormData, Headers

from src.api.v1.valuations import (
    _bool_value,
    _client_identifier,
    _float_value,
    _int_value,
    _store_image_uploads,
)
from src.config import settings
from src.services import valuation_job_store


class FakeUpload:
    def __init__(self, filename: str, content_type: str, data: bytes):
        self.filename = filename
        self.content_type = content_type
        self._data = data

    async def read(self) -> bytes:
        return self._data


class FakeClient:
    def __init__(self, host: str):
        self.host = host


class FakeRequest:
    def __init__(self, headers: dict | None = None, client_host: str | None = None):
        self.headers = Headers(headers or {})
        self.client = FakeClient(client_host) if client_host else None


class FakeRedis:
    """Minimal async Redis stand-in for the global-cap counter."""

    def __init__(self):
        self.store: dict[str, int] = {}
        self.expiries: dict[str, int] = {}

    async def incr(self, key: str) -> int:
        self.store[key] = self.store.get(key, 0) + 1
        return self.store[key]

    async def expire(self, key: str, ttl: int) -> bool:
        self.expiries[key] = ttl
        return True


def test_client_identifier_ignores_spoofed_xff(monkeypatch):
    # Attacker prepends 9.9.9.9; the trusted proxy appends the real peer on the
    # right. With one trusted hop we must read the real peer, not the spoof.
    monkeypatch.setattr(settings, "trusted_proxy_count", 1)
    request = FakeRequest(headers={"x-forwarded-for": "9.9.9.9, 203.0.113.5"})
    assert _client_identifier(request) == "203.0.113.5"


def test_client_identifier_prefers_x_real_ip_over_xff(monkeypatch):
    monkeypatch.setattr(settings, "trusted_proxy_count", 1)
    request = FakeRequest(
        headers={"x-real-ip": "203.0.113.5", "x-forwarded-for": "9.9.9.9"}
    )
    assert _client_identifier(request) == "203.0.113.5"


def test_client_identifier_rotating_xff_maps_to_same_real_peer(monkeypatch):
    # The core of the bypass: rotating the spoofed left token must NOT change the
    # identity, so the per-IP rate limit still bites.
    monkeypatch.setattr(settings, "trusted_proxy_count", 1)
    a = _client_identifier(FakeRequest(headers={"x-forwarded-for": "1.1.1.1, 203.0.113.5"}))
    b = _client_identifier(FakeRequest(headers={"x-forwarded-for": "2.2.2.2, 203.0.113.5"}))
    assert a == b == "203.0.113.5"


def test_client_identifier_falls_back_to_socket_peer():
    request = FakeRequest(client_host="198.51.100.9")
    assert _client_identifier(request) == "198.51.100.9"


def test_global_daily_cap_trips_after_limit(monkeypatch):
    monkeypatch.setattr(settings, "valuation_global_daily_cap", 3)
    fake = FakeRedis()
    monkeypatch.setattr(valuation_job_store, "redis_client", fake)

    results = [asyncio.run(valuation_job_store.check_global_daily_cap()) for _ in range(4)]
    allowed = [ok for ok, _ in results]
    assert allowed == [True, True, True, False]
    # TTL set exactly once, on the first increment.
    assert fake.expiries == {"valuation:globalcap:day": 86400}


def test_numeric_helpers_reject_malformed_values():
    with pytest.raises(HTTPException) as float_exc:
        _float_value(FormData({"area_sqm": "abc"}), "area_sqm")
    assert float_exc.value.status_code == 400
    assert "number" in float_exc.value.detail

    with pytest.raises(HTTPException) as int_exc:
        _int_value(FormData({"floor": "1.5"}), "floor")
    assert int_exc.value.status_code == 400
    assert "integer" in int_exc.value.detail


def test_numeric_helpers_reject_out_of_range_values():
    with pytest.raises(HTTPException) as exc:
        _float_value(FormData({"area_sqm": "-10"}), "area_sqm", gt=0)
    assert exc.value.status_code == 400

    with pytest.raises(HTTPException) as int_exc:
        _int_value(FormData({"bathrooms": "21"}), "bathrooms", ge=0, le=20)
    assert int_exc.value.status_code == 400


def test_bool_helper_rejects_unknown_strings():
    with pytest.raises(HTTPException) as exc:
        _bool_value(FormData({"has_pool": "definitely"}), "has_pool")
    assert exc.value.status_code == 400


def test_upload_rejects_too_many_images_without_creating_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "valuation_upload_dir", str(tmp_path))
    monkeypatch.setattr(settings, "valuation_max_upload_images", 1)
    form = FormData(
        [
            ("images", FakeUpload("a.jpg", "image/jpeg", b"a")),
            ("images", FakeUpload("b.jpg", "image/jpeg", b"b")),
        ]
    )

    with pytest.raises(HTTPException) as exc:
        asyncio.run(_store_image_uploads(form, "job-too-many"))

    assert exc.value.status_code == 400
    assert not (tmp_path / "job-too-many").exists()


def test_upload_rejects_bad_mime_without_creating_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "valuation_upload_dir", str(tmp_path))
    form = FormData([("images", FakeUpload("a.txt", "text/plain", b"a"))])

    with pytest.raises(HTTPException) as exc:
        asyncio.run(_store_image_uploads(form, "job-bad-mime"))

    assert exc.value.status_code == 400
    assert not (tmp_path / "job-bad-mime").exists()


def test_upload_cleans_dir_after_oversized_image(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "valuation_upload_dir", str(tmp_path))
    monkeypatch.setattr(settings, "valuation_max_upload_bytes", 2)
    form = FormData([("images", FakeUpload("a.jpg", "image/jpeg", b"abc"))])

    with pytest.raises(HTTPException) as exc:
        asyncio.run(_store_image_uploads(form, "job-oversized"))

    assert exc.value.status_code == 400
    assert not (tmp_path / "job-oversized").exists()


def test_upload_accepts_valid_images(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "valuation_upload_dir", str(tmp_path))
    monkeypatch.setattr(settings, "valuation_max_upload_bytes", 100)
    monkeypatch.setattr(settings, "valuation_max_upload_total_bytes", 100)
    form = FormData([("images", FakeUpload("a.jpg", "image/jpeg", b"abc"))])

    paths, upload_dir = asyncio.run(_store_image_uploads(form, "job-valid"))

    assert upload_dir == tmp_path / "job-valid"
    assert len(paths) == 1
    assert (tmp_path / "job-valid" / "image_0.jpg").read_bytes() == b"abc"
