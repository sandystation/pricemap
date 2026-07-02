# ruff: noqa: E501 - LLM prompt schema strings are intentionally long (must match llm_enrich.py)
import base64
import json
import os
from pathlib import Path
from typing import Any

from src.config import settings

SYSTEM_PROMPT = (
    "You are a real estate analyst. Extract structured features from property "
    "listings. Return ONLY valid JSON, no explanation."
)

TEXT_FIELDS_SCHEMA = """\
Return a JSON object with these fields:
- "condition" (int 1-5): 1=shell/unfinished, 2=needs renovation, 3=good/standard, 4=excellent/high finish, 5=luxury/premium
- "floor" (int or null): floor number if mentioned in description
- "total_floors" (int or null): total building floors if mentioned
- "furnishing" (string): "furnished", "partly_furnished", "unfurnished", or "unknown"
- "view" (string): primary view - "sea", "harbour", "valley", "city", "garden", "pool", "none", or "unknown"
- "construction_status" (string): "completed", "under_construction", "off_plan", or "unknown"
- "quality_tier" (string): "luxury", "premium", "standard", or "budget"
- "bright" (bool or null): true if good natural light is mentioned
- "quiet" (bool or null): true if quiet/peaceful location is mentioned
- "sea_proximity" (bool): true if near sea/coast/beach is mentioned
- "parking_type" (string): "double_garage", "garage", "car_space", "street", "none", or "unknown"
- "outdoor_space" (string): best outdoor space - "roof_terrace", "terrace", "garden", "yard", "balcony", "none", or "unknown"
- "outdoor_sqm" (int or null): outdoor space size in sqm if mentioned
- "floor_category" (string): "ground", "low", "mid", "high", "penthouse_level", or "unknown"
- "building_units" (int or null): total units in the building/block if mentioned
- "kitchen_type" (string): "open_plan", "separate", "kitchenette", or "unknown"
- "orientation" (string): "south", "east", "west", "north", or "unknown"
- "is_investment" (bool): true if described as investment/rental opportunity or already tenanted
- "is_new_build" (bool): true if new development/construction, not resale
- "has_storage" (bool or null): true if storage room/boxroom mentioned
- "ceiling_height" (string): "double", "high", "normal", or "unknown"
- "noise_exposure" (string): "quiet", "moderate", "busy", or "unknown"
- "lease_type" (string): "freehold", "leasehold", or "unknown"
- "location_reference" (string or null): the most specific location mentioned in the description
- "actual_living_area" (int or null): actual/net/clean living area if different from listed area
- "is_house_floor" (bool): true if the property is a floor/level of a house
- "area_includes_extra" (bool): true if listed area includes non-living space
- "data_quality_note" (string or null): any concern about data accuracy, or null."""

IMAGE_FIELDS_SCHEMA = """
- "interior_score" (int 1-5): overall interior quality visible in photos
- "renovation_era" (string): "modern", "recent", "dated", or "unknown"
- "photo_view" (string): view visible in photos - "sea", "urban", "countryside", "none", or "unknown"
- "kitchen_score" (int 1-5): kitchen quality/modernity from photos, null if no kitchen visible
- "bathroom_score" (int 1-5): bathroom quality from photos, null if no bathroom visible
- "flooring_type" (string): "marble", "tiles", "wood", "concrete", or "unknown"
- "exterior_condition" (int 1-5 or null): building exterior condition from photos
- "street_quality" (int 1-5 or null): neighborhood/street quality visible in photos"""

TEXT_FIELDS = {
    "condition": int,
    "floor": (int, type(None)),
    "total_floors": (int, type(None)),
    "furnishing": str,
    "view": str,
    "construction_status": str,
    "quality_tier": str,
    "bright": (bool, type(None)),
    "quiet": (bool, type(None)),
    "sea_proximity": bool,
    "parking_type": str,
    "outdoor_space": str,
    "outdoor_sqm": (int, type(None)),
    "floor_category": str,
    "building_units": (int, type(None)),
    "kitchen_type": str,
    "orientation": str,
    "is_investment": bool,
    "is_new_build": bool,
    "has_storage": (bool, type(None)),
    "ceiling_height": str,
    "noise_exposure": str,
    "lease_type": str,
    "location_reference": (str, type(None)),
    "actual_living_area": (int, type(None)),
    "is_house_floor": bool,
    "area_includes_extra": bool,
    "data_quality_note": (str, type(None)),
}

IMAGE_FIELDS = {
    "interior_score": int,
    "renovation_era": str,
    "photo_view": str,
    "kitchen_score": (int, type(None)),
    "bathroom_score": (int, type(None)),
    "flooring_type": str,
    "exterior_condition": (int, type(None)),
    "street_quality": (int, type(None)),
}


def build_user_prompt(payload: dict[str, Any], with_images: bool) -> str:
    prompt = (
        f"Property: {payload.get('listing_type', 'sale')} | "
        f"{payload.get('address', 'unknown location')} | "
        f"{payload.get('bedrooms') or '?'} bed | "
        f"{payload.get('area_sqm')} sqm\n\n"
        f"Description:\n{payload.get('description', '')}\n\n"
    )
    if with_images:
        prompt += "Photos of the property are attached.\n\n"
    prompt += TEXT_FIELDS_SCHEMA
    if with_images:
        prompt += IMAGE_FIELDS_SCHEMA
    return prompt


def parse_enrichment_response(text: str, with_images: bool) -> dict[str, Any] | None:
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None

    if not isinstance(data, dict):
        return None

    result: dict[str, Any] = {}
    fields = dict(TEXT_FIELDS)
    if with_images:
        fields.update(IMAGE_FIELDS)

    for key in fields:
        if key in data:
            result[key] = data[key]

    for key in (
        "condition",
        "interior_score",
        "kitchen_score",
        "bathroom_score",
        "exterior_condition",
        "street_quality",
    ):
        if isinstance(result.get(key), int):
            result[key] = max(1, min(5, result[key]))

    return result or None


def _load_images_base64(paths: list[str], max_images: int = 20) -> list[dict[str, str]]:
    images = []
    for path in paths[:max_images]:
        p = Path(path)
        if not p.exists():
            continue
        media_type = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".webp": "image/webp",
        }.get(p.suffix.lower())
        if not media_type:
            continue
        data = base64.standard_b64encode(p.read_bytes()).decode("utf-8")
        images.append({"data": data, "media_type": media_type})
    return images


def _load_scripts_env_if_needed() -> None:
    if os.environ.get("GOOGLE_API_KEY"):
        return
    scripts_env = Path(__file__).resolve().parents[3] / "scripts" / ".env"
    if not scripts_env.exists():
        return
    try:
        from dotenv import load_dotenv
    except ModuleNotFoundError:
        return
    load_dotenv(scripts_env)


class LLMEnrichmentService:
    def enrich(self, payload: dict[str, Any], image_paths: list[str]) -> dict[str, Any]:
        if settings.llm_provider != "google":
            raise RuntimeError("Only Google Gemini runtime enrichment is configured")

        _load_scripts_env_if_needed()
        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise RuntimeError("GOOGLE_API_KEY is not configured")

        from google import genai
        from google.genai import types

        images = _load_images_base64(
            image_paths,
            max_images=settings.valuation_max_upload_images,
        )
        prompt = build_user_prompt(payload, with_images=bool(images))

        contents = []
        for image in images:
            contents.append(
                types.Part.from_bytes(
                    data=base64.standard_b64decode(image["data"]),
                    mime_type=image["media_type"],
                )
            )
        contents.append(prompt)

        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=settings.llm_model,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                max_output_tokens=4096,
            ),
        )

        parsed = parse_enrichment_response(response.text or "", with_images=bool(images))
        if not parsed:
            raise RuntimeError("LLM enrichment returned invalid JSON")
        return parsed
