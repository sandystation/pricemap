from pathlib import Path
from typing import Any

from src.core.celery_app import celery_app
from src.ml.artifact_predictor import PREDICTOR
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


@celery_app.task(name="valuation.enriched")
def process_enriched_valuation(
    job_id: str,
    payload: dict[str, Any],
    image_paths: list[str],
) -> None:
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
        geo = _geocode(payload)

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
        enriched = LLMEnrichmentService().enrich(payload, image_paths)

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
