import time
from pathlib import Path
from typing import Any

from src.core.celery_app import celery_app
from src.core.telemetry import capture_event
from src.ml.artifact_predictor import PREDICTOR
from src.schemas.geocode import GeocodeResponse
from src.schemas.valuation import ValuationResponse
from src.services.geocoding_service import GeocodingService
from src.services.llm_enrichment_service import LLMEnrichmentService
from src.services.valuation_job_store import set_job_status_sync


def _label(score: float) -> str:
    if score >= 75:
        return "High"
    if score >= 50:
        return "Moderate"
    return "Low"


def _confidence(missing_features: list[str], image_paths: list[str]) -> float:
    score = 82.0
    high_impact = {
        "locality_enc",
        "province_enc",
        "total_int_area",
        "total_ext_area",
        "llm_condition",
        "llm_quality_tier",
    }
    for feature in set(missing_features):
        score -= 5.0 if feature in high_impact else 2.0
    if not image_paths:
        score -= 6.0
    return round(max(30.0, min(95.0, score)), 1)


def _geocode(payload: dict[str, Any]):
    return GeocodingService().geocode_sync(
        address=str(payload["address"]),
        country_code=str(payload["country_code"]),
    )


def _resolve_location(payload: dict[str, Any]):
    """Use the exact coordinates the user picked from address autocomplete when
    present (skips a redundant geocode); otherwise geocode the free-typed address.
    """
    lat, lon = payload.get("lat"), payload.get("lon")
    if lat is not None and lon is not None:
        return GeocodeResponse(
            lat=float(lat),
            lon=float(lon),
            display_name=str(payload.get("address") or ""),
            locality=payload.get("locality"),
            confidence=1.0,
        )
    return _geocode(payload)


@celery_app.task(name="valuation.enriched")
def process_enriched_valuation(
    job_id: str,
    payload: dict[str, Any],
    image_paths: list[str],
) -> None:
    started = time.monotonic()
    user_id = str(payload.get("user_id") or "") or None
    distinct_id = user_id or "anonymous"
    try:
        set_job_status_sync(
            job_id,
            {
                "job_id": job_id,
                "status": "running",
                "message": "Geocoding address",
                "missing_features": [],
            },
        )
        geo = _resolve_location(payload)

        set_job_status_sync(
            job_id,
            {
                "job_id": job_id,
                "status": "running",
                "message": "Running LLM enrichment",
                "lat": geo.lat,
                "lon": geo.lon,
                "missing_features": [],
            },
        )
        # LLM enrichment is best-effort: skip it when there's nothing to enrich
        # (no description + no images), and never let an enrichment failure fail
        # the valuation — the model handles missing llm_* features as NaN.
        description = str(payload.get("description") or "").strip()
        if description or image_paths:
            try:
                enriched = LLMEnrichmentService().enrich(payload, image_paths)
            except Exception:
                enriched = {}
        else:
            enriched = {}

        set_job_status_sync(
            job_id,
            {
                "job_id": job_id,
                "status": "running",
                "message": "Building model features",
                "lat": geo.lat,
                "lon": geo.lon,
                "enriched_features": enriched,
                "missing_features": [],
            },
        )
        prediction = PREDICTOR.predict(
            payload=payload,
            enriched=enriched,
            lat=geo.lat,
            lon=geo.lon,
            locality=geo.locality,
        )

        confidence_score = _confidence(prediction["missing_features"], image_paths)
        area = float(enriched.get("actual_living_area") or payload["area_sqm"])
        result = ValuationResponse(
            estimate_eur=prediction["estimate"],
            confidence_low=prediction["low"],
            confidence_high=prediction["high"],
            confidence_score=confidence_score,
            confidence_label=_label(confidence_score),
            price_per_sqm=round(prediction["estimate"] / area, 2) if area else 0,
            comparables=[],
            feature_importance=prediction["feature_importance"],
            model_version=prediction["model_version"],
            data_freshness=None,
            method="model",
        )

        set_job_status_sync(
            job_id,
            {
                "job_id": job_id,
                "status": "complete",
                "message": "Valuation complete",
                "result": result.model_dump(),
                "lat": geo.lat,
                "lon": geo.lon,
                "enriched_features": enriched,
                "missing_features": prediction["missing_features"],
                "model_version": prediction["model_version"],
            },
        )

        capture_event(
            distinct_id,
            "valuation_completed",
            {
                "user_id": user_id,
                "authenticated": user_id is not None,
                "country_code": payload.get("country_code"),
                "listing_type": payload.get("listing_type"),
                "property_type": payload.get("property_type"),
                "area_sqm": payload.get("area_sqm"),
                "estimate_eur": result.estimate_eur,
                "price_per_sqm": result.price_per_sqm,
                "confidence_score": confidence_score,
                "model_version": prediction["model_version"],
                "comparables_count": len(result.comparables),
                "has_images": bool(image_paths),
                "image_count": len(image_paths),
                "geocode_ok": geo.lat is not None and geo.lon is not None,
                "llm_ok": bool(enriched),
                "enriched_feature_count": len(enriched or {}),
                "missing_feature_count": len(prediction["missing_features"]),
                "duration_ms": round((time.monotonic() - started) * 1000),
            },
        )
    except Exception as exc:
        set_job_status_sync(
            job_id,
            {
                "job_id": job_id,
                "status": "failed",
                "message": "Enriched valuation failed",
                "error": str(exc),
                "missing_features": [],
            },
        )
        capture_event(
            distinct_id,
            "valuation_failed",
            {
                "user_id": user_id,
                "authenticated": user_id is not None,
                "country_code": payload.get("country_code"),
                "error": str(exc),
                "duration_ms": round((time.monotonic() - started) * 1000),
            },
        )
        raise
    finally:
        # Remove the whole per-job upload directory, not just the files, so no
        # empty {job_id} dirs accumulate on the shared uploads volume.
        dirs = {Path(p).parent for p in image_paths}
        for path in image_paths:
            try:
                Path(path).unlink(missing_ok=True)
            except OSError:
                pass
        for d in dirs:
            try:
                d.rmdir()
            except OSError:
                pass
