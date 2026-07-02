import asyncio

import pytest
from fastapi import HTTPException
from starlette.datastructures import FormData

from src.api.v1.valuations import (
    _bool_value,
    _float_value,
    _int_value,
    _store_image_uploads,
)
from src.config import settings


class FakeUpload:
    def __init__(self, filename: str, content_type: str, data: bytes):
        self.filename = filename
        self.content_type = content_type
        self._data = data

    async def read(self) -> bytes:
        return self._data


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
