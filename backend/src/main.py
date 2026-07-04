from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from src.api.v1.router import api_v1_router
from src.config import settings
from src.core.database import engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    yield
    # Shutdown
    await engine.dispose()


app = FastAPI(
    title="PriceMap API",
    description="Real estate valuation for underserved EU markets",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    # The enriched flow is unauthenticated form-data (no cookies), so credentials
    # aren't needed; keep methods/headers scoped to what the frontend actually sends.
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

# Reject spoofed Host headers in production (defense-in-depth alongside
# --forwarded-allow-ips). localhost is kept for the container's own healthcheck.
if settings.environment == "production":
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=[settings.api_domain, "localhost", "127.0.0.1"],
    )

app.include_router(api_v1_router, prefix=settings.api_v1_prefix)
