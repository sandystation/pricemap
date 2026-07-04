"""Bearer-token auth: the Next.js app (Auth.js) mints a short-lived HS256 JWT
for the logged-in user and sends it as `Authorization: Bearer <jwt>`; this API
verifies it with the shared secret. FastAPI stays a stateless verifier — no DB
connection or session store needed here.
"""
import jwt
from fastapi import HTTPException, Request

from src.config import settings


def _bearer_token(request: Request) -> str | None:
    header = request.headers.get("authorization") or ""
    if header.lower().startswith("bearer "):
        return header[7:].strip() or None
    return None


def _verify(token: str) -> dict:
    if not settings.api_jwt_secret:
        # Misconfiguration: a token was sent but the API can't verify it.
        raise HTTPException(status_code=503, detail="Authentication is not configured")
    try:
        return dict(jwt.decode(token, settings.api_jwt_secret, algorithms=["HS256"]))
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired token") from exc


def require_user(request: Request) -> str:
    """Require a valid Bearer token; return the user id (JWT `sub`)."""
    token = _bearer_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="Authentication required")
    sub = _verify(token).get("sub")
    if not sub:
        raise HTTPException(status_code=401, detail="Invalid token (no subject)")
    return str(sub)


def resolve_client(request: Request) -> str | None:
    """Soft-rollout resolver used by /enriched.

    - Valid token  -> the user id (rate-limited per user).
    - Invalid token -> 401 (a broken token is never treated as anonymous).
    - No token      -> None (anonymous, IP-rate-limited) UNLESS settings.require_auth.
    """
    token = _bearer_token(request)
    if token:
        sub = _verify(token).get("sub")
        if sub:
            return str(sub)
    if settings.require_auth:
        raise HTTPException(status_code=401, detail="Authentication required")
    return None
