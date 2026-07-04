import time

import jwt
import pytest
from fastapi import HTTPException
from starlette.datastructures import Headers

from src.config import settings
from src.core.auth import require_user, resolve_client


class FakeRequest:
    def __init__(self, headers=None):
        self.headers = Headers(headers or {})


def _token(secret, sub="user-123", exp_delta=3600):
    return jwt.encode(
        {"sub": sub, "exp": int(time.time()) + exp_delta}, secret, algorithm="HS256"
    )


def test_require_user_valid(monkeypatch):
    monkeypatch.setattr(settings, "api_jwt_secret", "s3cret")
    req = FakeRequest({"authorization": "Bearer " + _token("s3cret")})
    assert require_user(req) == "user-123"


def test_require_user_missing_token(monkeypatch):
    monkeypatch.setattr(settings, "api_jwt_secret", "s3cret")
    with pytest.raises(HTTPException) as e:
        require_user(FakeRequest())
    assert e.value.status_code == 401


def test_require_user_forged_signature(monkeypatch):
    monkeypatch.setattr(settings, "api_jwt_secret", "s3cret")
    req = FakeRequest({"authorization": "Bearer " + _token("wrong-secret")})
    with pytest.raises(HTTPException) as e:
        require_user(req)
    assert e.value.status_code == 401


def test_require_user_expired(monkeypatch):
    monkeypatch.setattr(settings, "api_jwt_secret", "s3cret")
    req = FakeRequest({"authorization": "Bearer " + _token("s3cret", exp_delta=-10)})
    with pytest.raises(HTTPException) as e:
        require_user(req)
    assert e.value.status_code == 401


def test_resolve_client_anonymous_when_soft(monkeypatch):
    monkeypatch.setattr(settings, "api_jwt_secret", "s3cret")
    monkeypatch.setattr(settings, "require_auth", False)
    assert resolve_client(FakeRequest()) is None


def test_resolve_client_401_when_require_auth(monkeypatch):
    monkeypatch.setattr(settings, "api_jwt_secret", "s3cret")
    monkeypatch.setattr(settings, "require_auth", True)
    with pytest.raises(HTTPException) as e:
        resolve_client(FakeRequest())
    assert e.value.status_code == 401


def test_resolve_client_valid_token(monkeypatch):
    monkeypatch.setattr(settings, "api_jwt_secret", "s3cret")
    req = FakeRequest({"authorization": "Bearer " + _token("s3cret", sub="u9")})
    assert resolve_client(req) == "u9"


def test_resolve_client_bad_token_is_401_not_anonymous(monkeypatch):
    monkeypatch.setattr(settings, "api_jwt_secret", "s3cret")
    monkeypatch.setattr(settings, "require_auth", False)
    req = FakeRequest({"authorization": "Bearer garbage"})
    with pytest.raises(HTTPException) as e:
        resolve_client(req)
    assert e.value.status_code == 401
