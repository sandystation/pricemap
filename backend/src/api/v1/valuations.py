import math
import shutil
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.core.auth import resolve_client
from src.core.database import get_db
from src.schemas.valuation import (
    EnrichedValuationJobResponse,
    EnrichedValuationStatusResponse,
    ValuationRequest,
    ValuationResponse,
)
from src.services.valuation_job_store import (
    check_global_daily_cap,
    count_active_jobs,
    get_job_status,
    increment_rate_limit,
    release_abuse_budget,
    set_job_status,
)
from src.services.valuation_service import ValuationService
from src.tasks.valuation import process_enriched_valuation

router = APIRouter()


@router.post("/estimate", response_model=ValuationResponse)
async def estimate_value(
    request: ValuationRequest,
    db: AsyncSession = Depends(get_db),
):
    """Estimate property value based on address and characteristics."""
    if not request.address and not (request.lat and request.lon):
        raise HTTPException(
            status_code=400, detail="Provide either address or lat/lon coordinates"
        )

    service = ValuationService(db)
    result = await service.estimate(request)
    return result


def _form_value(form, key: str, default=None):
    value = form.get(key, default)
    if value == "":
        return default
    return value


def _client_identifier(request: Request) -> str:
    """Resolve the rate-limit identity from trusted-proxy headers only.

    X-Forwarded-For is client-controllable: a caller can prepend arbitrary
    tokens, and the trusted proxy only APPENDS the real peer to the right. So we
    never trust the left-most (client-supplied) token. Preference order:
      1. X-Real-IP (nginx sets this to the real peer $remote_addr), else
      2. the trusted_proxy_count-th entry from the RIGHT of X-Forwarded-For
         (the hop the trusted proxy actually observed), else
      3. the direct socket peer.
    This is only sound when the app is reachable exclusively via the proxy — do
    not publish the app port directly to untrusted networks.
    """
    real_ip = request.headers.get("x-real-ip")
    if real_ip and real_ip.strip():
        return real_ip.strip()
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        hops = [hop.strip() for hop in forwarded_for.split(",") if hop.strip()]
        if hops:
            index = min(max(settings.trusted_proxy_count, 1), len(hops))
            return hops[-index]
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


async def _enforce_abuse_limits(request: Request, user_id: str | None = None) -> None:
    # Rate-limit per authenticated user when present, else per client IP.
    identifier = f"user:{user_id}" if user_id else _client_identifier(request)
    try:
        active_jobs = await count_active_jobs()
        if active_jobs >= settings.valuation_max_active_jobs:
            raise HTTPException(
                status_code=429,
                detail="Too many enriched valuations are currently queued. Try again shortly.",
            )

        allowed, message = await increment_rate_limit(identifier)
        if not allowed:
            raise HTTPException(status_code=429, detail=message)

        global_allowed, global_message = await check_global_daily_cap()
        if not global_allowed:
            raise HTTPException(status_code=429, detail=global_message)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="Rate limit service is unavailable",
        ) from exc


def _float_value(form, key: str, *, required: bool = False, ge=None, gt=None, le=None):
    value = _form_value(form, key)
    if value is None:
        if required:
            raise HTTPException(status_code=400, detail=f"{key} is required")
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=f"{key} must be a number") from exc
    if not math.isfinite(parsed):
        raise HTTPException(status_code=400, detail=f"{key} must be a finite number")
    if ge is not None and parsed < ge:
        raise HTTPException(status_code=400, detail=f"{key} must be at least {ge}")
    if gt is not None and parsed <= gt:
        raise HTTPException(status_code=400, detail=f"{key} must be greater than {gt}")
    if le is not None and parsed > le:
        raise HTTPException(status_code=400, detail=f"{key} must be at most {le}")
    return parsed


def _int_value(form, key: str, *, ge=None, le=None):
    value = _form_value(form, key)
    if value is None:
        return None
    try:
        parsed = int(str(value))
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=f"{key} must be an integer") from exc
    if ge is not None and parsed < ge:
        raise HTTPException(status_code=400, detail=f"{key} must be at least {ge}")
    if le is not None and parsed > le:
        raise HTTPException(status_code=400, detail=f"{key} must be at most {le}")
    return parsed


def _bool_value(form, key: str):
    value = _form_value(form, key)
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    normalized = str(value).lower()
    if normalized in {"true", "1", "yes", "on"}:
        return True
    if normalized in {"false", "0", "no", "off"}:
        return False
    raise HTTPException(status_code=400, detail=f"{key} must be a boolean")


def _cleanup_upload_dir(upload_dir: Path | None) -> None:
    if upload_dir and upload_dir.exists():
        shutil.rmtree(upload_dir, ignore_errors=True)


async def _store_image_uploads(form, job_id: str) -> tuple[list[str], Path | None]:
    uploads = [upload for upload in form.getlist("images") if getattr(upload, "filename", "")]
    if len(uploads) > settings.valuation_max_upload_images:
        raise HTTPException(
            status_code=400,
            detail=f"Upload at most {settings.valuation_max_upload_images} images",
        )

    for upload in uploads:
        filename = getattr(upload, "filename", "") or ""
        content_type = getattr(upload, "content_type", "") or ""
        suffix = Path(filename).suffix.lower()
        if suffix not in {".jpg", ".jpeg", ".png", ".webp"} or content_type not in {
            "image/jpeg",
            "image/png",
            "image/webp",
        }:
            raise HTTPException(status_code=400, detail="Images must be jpg, png, or webp")

    if not uploads:
        return [], None

    upload_dir = Path(settings.valuation_upload_dir) / job_id
    image_paths = []
    total_bytes = 0
    try:
        upload_dir.mkdir(parents=True, exist_ok=True)
        for index, upload in enumerate(uploads):
            filename = getattr(upload, "filename", "") or ""
            suffix = Path(filename).suffix.lower()
            data = await upload.read()
            size = len(data)
            total_bytes += size
            if size > settings.valuation_max_upload_bytes:
                raise HTTPException(status_code=400, detail="Each image must be under 8MB")
            if total_bytes > settings.valuation_max_upload_total_bytes:
                raise HTTPException(status_code=400, detail="Total image upload must be under 40MB")
            path = upload_dir / f"image_{index}{suffix}"
            path.write_bytes(data)
            image_paths.append(str(path))
    except Exception:
        _cleanup_upload_dir(upload_dir)
        raise

    return image_paths, upload_dir


@router.post("/enriched", response_model=EnrichedValuationJobResponse)
async def create_enriched_valuation(request: Request):
    """Queue an enriched Malta apartment valuation with text/image preprocessing."""
    # Resolve the caller up front (cheap, header-only): a valid Bearer token -> user
    # id, an invalid token -> 401, no token -> anonymous unless require_auth is on.
    user_id = resolve_client(request)
    # Abuse limits are enforced AFTER validation + image storage (below), so that
    # invalid requests (400s) don't consume the per-user/IP rate limit or the global
    # daily spend cap -- only requests that will actually cost a Gemini/Nominatim
    # call do.
    form = await request.form()
    country_code = str(_form_value(form, "country_code", "")).upper()
    property_type = str(_form_value(form, "property_type", "")).lower()
    listing_type = str(_form_value(form, "listing_type", "")).lower()
    description = str(_form_value(form, "description", "")).strip()

    if country_code != "MT" or property_type != "apartment":
        raise HTTPException(
            status_code=400,
            detail="Enriched model valuations currently support Malta apartments only",
        )
    if listing_type not in {"sale", "rent"}:
        raise HTTPException(status_code=400, detail="listing_type must be sale or rent")
    if len(description) < 20:
        raise HTTPException(
            status_code=400,
            detail="Description must be at least 20 characters for LLM enrichment",
        )
    if len(description) > settings.valuation_description_max_chars:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Description must be at most "
                f"{settings.valuation_description_max_chars} characters"
            ),
        )

    area_sqm = _float_value(form, "area_sqm", required=True, gt=0, le=10000)
    address = str(_form_value(form, "address", "")).strip()
    if not address:
        raise HTTPException(status_code=400, detail="Address and area_sqm are required")
    if len(address) < 3 or len(address) > 300:
        raise HTTPException(status_code=400, detail="Address must be 3-300 characters")

    condition = _form_value(form, "condition")
    if condition not in {None, "new", "excellent", "good", "needs_renovation", "shell"}:
        raise HTTPException(status_code=400, detail="Invalid condition")

    total_int_area = _float_value(form, "total_int_area", gt=0, le=10000)
    total_ext_area = _float_value(form, "total_ext_area", ge=0, le=10000)
    if total_int_area is not None and total_int_area > area_sqm:
        raise HTTPException(
            status_code=400,
            detail="total_int_area must not exceed area_sqm",
        )
    floor = _int_value(form, "floor", ge=-2, le=100)
    total_floors = _int_value(form, "total_floors", ge=1, le=100)
    if floor is not None and total_floors is not None and floor > total_floors:
        raise HTTPException(status_code=400, detail="floor must not exceed total_floors")

    # Optional precise location from address autocomplete (both-or-neither). Trust
    # only coordinates inside the Malta bbox; otherwise drop them and let the worker
    # geocode the free-typed address as before.
    lat = _float_value(form, "lat", ge=-90, le=90)
    lon = _float_value(form, "lon", ge=-180, le=180)
    picked_locality = None
    if lat is not None and lon is not None and 35.75 <= lat <= 36.12 and 14.15 <= lon <= 14.62:
        picked_locality = _form_value(form, "locality")
    else:
        lat = lon = None

    payload = {
        "country_code": country_code,
        "listing_type": listing_type,
        "property_type": property_type,
        "address": address,
        "area_sqm": area_sqm,
        "floor": floor,
        "total_floors": total_floors,
        "rooms": _int_value(form, "rooms", ge=1, le=50),
        "bedrooms": _int_value(form, "bedrooms", ge=0, le=20),
        "bathrooms": _int_value(form, "bathrooms", ge=0, le=20),
        "total_int_area": total_int_area,
        "total_ext_area": total_ext_area,
        "year_built": _int_value(form, "year_built", ge=1400, le=2030),
        "condition": condition,
        "has_parking": _bool_value(form, "has_parking"),
        "has_garden": _bool_value(form, "has_garden"),
        "has_pool": _bool_value(form, "has_pool"),
        "has_elevator": _bool_value(form, "has_elevator"),
        "has_balcony": _bool_value(form, "has_balcony"),
        "description": description,
        "lat": lat,
        "lon": lon,
        "locality": picked_locality,
        "user_id": user_id,
    }

    job_id = uuid4().hex
    image_paths, upload_dir = await _store_image_uploads(form, job_id)

    # Only now (valid request, images stored) consume the abuse budget.
    try:
        await _enforce_abuse_limits(request, user_id)
    except HTTPException:
        _cleanup_upload_dir(upload_dir)
        raise

    await set_job_status(
        job_id,
        {
            "job_id": job_id,
            "status": "queued",
            "message": "Queued for enriched valuation",
            "missing_features": [],
        },
    )
    try:
        process_enriched_valuation.delay(job_id, payload, image_paths)
    except Exception as exc:
        # Give the budget back: the request never reached the worker.
        await release_abuse_budget(f"user:{user_id}" if user_id else _client_identifier(request))
        await set_job_status(
            job_id,
            {
                "job_id": job_id,
                "status": "failed",
                "message": "Could not queue enriched valuation",
                "error": str(exc),
                "missing_features": [],
            },
        )
        _cleanup_upload_dir(upload_dir)
        raise HTTPException(
            status_code=503,
            detail="Enriched valuation worker is not available",
        ) from exc
    return EnrichedValuationJobResponse(job_id=job_id, status="queued")


@router.get("/enriched/{job_id}", response_model=EnrichedValuationStatusResponse)
async def get_enriched_valuation(job_id: str):
    status = await get_job_status(job_id)
    if not status:
        raise HTTPException(status_code=404, detail="Valuation job not found")
    return status
