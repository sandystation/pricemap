"""
LLM-based feature extraction for property listings.

Extracts structured features (condition, floor, view, furnishing, etc.) from
property descriptions and optionally photos using Claude, OpenAI, or Gemini.

Each run saves results to data/llm_enrichments/<run_id>/ with a metadata JSON
for experiment tracking. Use --llm-run <run_id> in train_valuation.py to train
with a specific enrichment dataset.

Usage (run from scripts/ directory):
    python llm_enrich.py                                          # text-only, default provider
    python llm_enrich.py --with-images                             # text + photos
    python llm_enrich.py --provider openai --model gpt-5.4-mini
    python llm_enrich.py --provider google --model gemini-2.5-flash
    python llm_enrich.py --max 50                                  # test on 50 docs
    python llm_enrich.py --run-name my_experiment                  # custom run name
    python llm_enrich.py --parallel 10                             # parallel API calls
    python llm_enrich.py --stats                                   # show enrichment runs
"""

import argparse
import base64
import json
import logging
import os
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import orjson
from dotenv import load_dotenv

from docstore import DocStore
from scraper_base import download_images, get_client

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Provider config
# ---------------------------------------------------------------------------
PROVIDERS = {
    "anthropic": {
        "models": [
            "claude-haiku-4-5-20251001",
            "claude-sonnet-4-6",
            "claude-opus-4-6",
        ],
        "default": "claude-haiku-4-5-20251001",
        "env_key": "ANTHROPIC_API_KEY",
        "sdk": "anthropic",
    },
    "openai": {
        "models": [
            "gpt-5.4-nano",
            "gpt-5.4-mini",
            "gpt-5.4",
        ],
        "default": "gpt-5.4-mini",
        "env_key": "OPENAI_API_KEY",
        "sdk": "openai",
    },
    "google": {
        "models": [
            "gemini-2.5-flash-lite",
            "gemini-2.5-flash",
            "gemini-2.5-pro",
            "gemini-3.1-flash-lite-preview",
            "gemini-3.1-pro-preview",
        ],
        "default": "gemini-2.5-flash",
        "env_key": "GOOGLE_API_KEY",
        "sdk": "google-genai",
    },
}

# ---------------------------------------------------------------------------
# Run storage
# ---------------------------------------------------------------------------
ENRICHMENTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "llm_enrichments")


def generate_run_id(provider: str, model: str, with_images: bool) -> str:
    """Generate a run ID like '20260408_gemini31flashlite_text'."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")
    model_short = model.replace("-", "").replace(".", "").replace("preview", "")[:25]
    mode = "images" if with_images else "text"
    return f"{ts}_{model_short}_{mode}"


class RunWriter:
    """Writes enrichment results to a run directory."""

    def __init__(self, run_id: str):
        self.run_id = run_id
        self.run_dir = os.path.join(ENRICHMENTS_DIR, run_id)
        os.makedirs(self.run_dir, exist_ok=True)
        self._jsonl_path = os.path.join(self.run_dir, "enrichments.jsonl")
        self._meta_path = os.path.join(self.run_dir, "metadata.json")
        self._file = open(self._jsonl_path, "ab")  # append mode
        self._count = 0

    def write(self, doc_id: str, features: dict):
        line = orjson.dumps({"doc_id": doc_id, "features": features})
        self._file.write(line + b"\n")
        self._count += 1

    def flush(self):
        self._file.flush()

    def save_metadata(self, meta: dict):
        meta["run_id"] = self.run_id
        meta["doc_count"] = self._count
        with open(self._meta_path, "w") as f:
            json.dump(meta, f, indent=2)

    def close(self):
        self._file.close()


def load_run(run_id: str) -> dict[str, dict]:
    """Load enrichment results from a run. Returns {doc_id: features}."""
    path = os.path.join(ENRICHMENTS_DIR, run_id, "enrichments.jsonl")
    if not os.path.exists(path):
        raise FileNotFoundError(f"Run not found: {path}")
    result = {}
    with open(path, "rb") as f:
        for line in f:
            rec = orjson.loads(line)
            result[rec["doc_id"]] = rec["features"]
    return result


def list_runs() -> list[dict]:
    """List all enrichment runs with their metadata."""
    runs = []
    if not os.path.exists(ENRICHMENTS_DIR):
        return runs
    for name in sorted(os.listdir(ENRICHMENTS_DIR)):
        meta_path = os.path.join(ENRICHMENTS_DIR, name, "metadata.json")
        if os.path.exists(meta_path):
            with open(meta_path) as f:
                runs.append(json.load(f))
    return runs


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------
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
- "sea_proximity" (bool): true if near sea/coast/beach is mentioned"""

IMAGE_FIELDS_SCHEMA = """
- "interior_score" (int 1-5): overall interior quality visible in photos
- "renovation_era" (string): "modern", "recent", "dated", or "unknown"
- "photo_view" (string): view visible in photos - "sea", "urban", "countryside", "none", or "unknown" """


def build_user_prompt(cur: dict, with_images: bool) -> str:
    listing_type = cur.get("listing_type", "unknown")
    locality = cur.get("locality", "unknown")
    bedrooms = cur.get("bedrooms", "?")
    price = cur.get("price_eur", 0)
    description = cur.get("description", "")

    prompt = (
        f"Property: {listing_type} | {locality} | {bedrooms} bed | EUR {price:,.0f}\n\n"
        f"Description:\n{description}\n\n"
    )
    if with_images:
        prompt += "Photos of the property are attached.\n\n"

    prompt += TEXT_FIELDS_SCHEMA
    if with_images:
        prompt += IMAGE_FIELDS_SCHEMA

    return prompt


# ---------------------------------------------------------------------------
# Provider adapters
# ---------------------------------------------------------------------------

def _load_images_base64(paths: list[str], max_images: int = 6) -> list[dict]:
    """Load local images as base64 dicts. Returns list of {data, media_type}."""
    results = []
    # Pick first + evenly spaced from rest
    if not paths:
        return results
    indices = [0]
    if len(paths) > 1:
        step = max(1, (len(paths) - 1) // (max_images - 1))
        indices += list(range(1, len(paths), step))
    indices = sorted(set(indices))[:max_images]

    for i in indices:
        path = paths[i]
        if not os.path.exists(path):
            continue
        try:
            with open(path, "rb") as f:
                data = base64.standard_b64encode(f.read()).decode("utf-8")
            ext = os.path.splitext(path)[1].lower()
            media_type = {
                ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                ".png": "image/png", ".webp": "image/webp",
            }.get(ext, "image/jpeg")
            results.append({"data": data, "media_type": media_type})
        except Exception as e:
            logger.warning(f"Failed to read image {path}: {e}")
    return results


def call_anthropic(client, model: str, user_prompt: str, images: list[dict]) -> str:
    content = []
    for img in images:
        content.append({
            "type": "image",
            "source": {"type": "base64", "media_type": img["media_type"], "data": img["data"]},
        })
    content.append({"type": "text", "text": user_prompt})

    resp = client.messages.create(
        model=model,
        max_tokens=400,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": content}],
    )
    return resp.content[0].text


def call_openai(client, model: str, user_prompt: str, images: list[dict]) -> str:
    content = []
    for img in images:
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:{img['media_type']};base64,{img['data']}"},
        })
    content.append({"type": "text", "text": user_prompt})

    resp = client.chat.completions.create(
        model=model,
        max_tokens=400,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": content},
        ],
    )
    return resp.choices[0].message.content


def call_google(client, model: str, user_prompt: str, images: list[dict]) -> str:
    from google.genai import types

    contents = []
    for img in images:
        contents.append(types.Part.from_bytes(
            data=base64.standard_b64decode(img["data"]),
            mime_type=img["media_type"],
        ))
    contents.append(user_prompt)

    resp = client.models.generate_content(
        model=model,
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            max_output_tokens=400,
        ),
    )
    return resp.text


CALL_FNS = {
    "anthropic": call_anthropic,
    "openai": call_openai,
    "google": call_google,
}


def init_client(provider: str):
    """Initialize the API client for the given provider."""
    cfg = PROVIDERS[provider]
    api_key = os.environ.get(cfg["env_key"])
    if not api_key:
        logger.error(
            f"{cfg['env_key']} not set. Add it to scripts/.env or export it.\n"
            f"  See scripts/.env.example for the format."
        )
        sys.exit(1)

    if provider == "anthropic":
        import anthropic
        return anthropic.Anthropic(api_key=api_key)
    elif provider == "openai":
        import openai
        return openai.OpenAI(api_key=api_key)
    elif provider == "google":
        from google import genai
        return genai.Client(api_key=api_key)


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------

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
}

IMAGE_FIELDS = {
    "interior_score": int,
    "renovation_era": str,
    "photo_view": str,
}


def parse_response(text: str, with_images: bool) -> dict | None:
    """Parse JSON from LLM response. Returns None on failure."""
    # Strip markdown code fences if present
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

    result = {}
    fields = dict(TEXT_FIELDS)
    if with_images:
        fields.update(IMAGE_FIELDS)

    for key, expected_type in fields.items():
        if key in data:
            result[key] = data[key]

    # Clamp condition to 1-5
    if "condition" in result and isinstance(result["condition"], int):
        result["condition"] = max(1, min(5, result["condition"]))
    if "interior_score" in result and isinstance(result["interior_score"], int):
        result["interior_score"] = max(1, min(5, result["interior_score"]))

    return result if result else None


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

def print_stats(coll):
    """Print LLM enrichment coverage stats and available runs."""
    # Show available runs
    runs = list_runs()
    if runs:
        print(f"\n{'=' * 70}")
        print(f"  Available enrichment runs ({len(runs)})")
        print(f"{'=' * 70}")
        for r in runs:
            mode = r.get("mode", "?")
            model = r.get("model", "?")
            count = r.get("doc_count", 0)
            ts = r.get("started_at", "?")[:16]
            print(f"  {r['run_id']:45s} | {model:30s} | {mode:6s} | {count:>6d} docs | {ts}")
    else:
        print("\nNo enrichment runs found.")

    # Show DocStore enrichment (legacy/in-progress)
    coll._ensure_loaded()
    docs = list(coll._docs.values())
    total = len(docs)
    with_llm = [d for d in docs if d.get("current", {}).get("llm_condition") is not None]

    print(f"\nDocStore: {len(with_llm)}/{total} docs with llm_ fields ({100 * len(with_llm) / total:.1f}%)")

    if not with_llm:
        return

    # Model distribution
    models = Counter(d["current"].get("llm_model", "unknown") for d in with_llm)
    print("\nBy model (DocStore):")
    for m, c in models.most_common():
        print(f"  {m}: {c}")

    # Condition distribution
    conditions = Counter(
        d["current"].get("llm_condition") for d in with_llm
        if d["current"].get("llm_condition") is not None
    )
    print("\nCondition distribution:")
    for c in sorted(conditions.keys()):
        label = {1: "shell", 2: "needs reno", 3: "good", 4: "excellent", 5: "luxury"}
        print(f"  {c} ({label.get(c, '?')}): {conditions[c]}")


# ---------------------------------------------------------------------------
# Single-doc processing (called from threads)
# ---------------------------------------------------------------------------

def _process_one(
    doc_id: str,
    doc: dict,
    client,
    call_fn,
    model: str,
    with_images: bool,
    http_client,
    now_str: str,
) -> tuple[str, dict | None, str | None]:
    """Process one doc. Returns (doc_id, parsed_result, error_msg)."""
    cur = doc["current"]

    # Download images if needed
    images = []
    if with_images:
        image_urls = cur.get("all_image_urls", [])
        if image_urls and http_client:
            ext_id = doc_id.split(":", 1)[1] if ":" in doc_id else doc_id
            local_paths = download_images(
                http_client, image_urls, "mt_remax", ext_id,
                max_images=20,
            )
            if local_paths:
                images = _load_images_base64(local_paths, max_images=6)

    user_prompt = build_user_prompt(cur, with_images=bool(images))

    # Call LLM with exponential backoff
    response_text = None
    max_retries = 6
    for attempt in range(max_retries):
        try:
            response_text = call_fn(client, model, user_prompt, images)
            break
        except Exception as e:
            err_str = str(e).lower()
            is_rate_limit = "429" in err_str or "rate" in err_str or "quota" in err_str or "resource_exhausted" in err_str
            is_server_error = "500" in err_str or "503" in err_str or "overloaded" in err_str

            if is_rate_limit or is_server_error:
                if attempt < max_retries - 1:
                    wait = min(2 ** attempt + 0.5 * attempt, 60)
                    logger.warning(
                        f"{'Rate limit' if is_rate_limit else 'Server error'} "
                        f"(attempt {attempt + 1}/{max_retries}): {e}. "
                        f"Retrying in {wait:.0f}s..."
                    )
                    time.sleep(wait)
                else:
                    return doc_id, None, f"Rate limit after {max_retries} retries: {e}"
            else:
                if attempt < 2:
                    wait = 2 ** attempt
                    logger.warning(f"API error (attempt {attempt + 1}): {e}. Retrying in {wait}s...")
                    time.sleep(wait)
                else:
                    return doc_id, None, f"API error after retries: {e}"

    if not response_text:
        return doc_id, None, "No response"

    parsed = parse_response(response_text, with_images=bool(images))
    if not parsed:
        return doc_id, None, f"JSON parse failed: {response_text[:200]}"

    return doc_id, parsed, None


# ---------------------------------------------------------------------------
# Main processing
# ---------------------------------------------------------------------------

def process_docs(
    coll,
    provider: str,
    model: str,
    with_images: bool,
    max_docs: int | None,
    reprocess: bool,
    delay: float,
    parallel: int = 1,
    run_name: str | None = None,
    write_docstore: bool = True,
):
    """Run LLM enrichment on docs in collection."""
    import threading
    from concurrent.futures import ThreadPoolExecutor, as_completed

    coll._ensure_loaded()

    # Build list of docs to process
    to_process = []
    for doc_id, doc in coll._docs.items():
        cur = doc.get("current", {})
        if not cur.get("description"):
            continue
        if not reprocess and cur.get("llm_condition") is not None:
            continue
        to_process.append((doc_id, doc))

    if max_docs:
        to_process = to_process[:max_docs]

    if not to_process:
        logger.info("No docs to process.")
        return

    # Set up run writer
    run_id = run_name or generate_run_id(provider, model, with_images)
    run_writer = RunWriter(run_id)
    logger.info(f"Run ID: {run_id}")
    logger.info(f"Output: {run_writer.run_dir}/")

    logger.info(
        f"Processing {len(to_process)} docs with {provider}/{model} "
        f"({'with images' if with_images else 'text-only'}, "
        f"parallel={parallel})"
    )

    global _start_time
    _start_time = time.time()

    # Initialize provider
    client = init_client(provider)
    call_fn = CALL_FNS[provider]
    http_client = get_client() if with_images else None

    now_str = datetime.now(timezone.utc).isoformat()
    processed = 0
    errors = 0
    stop_event = threading.Event()

    def _submit_and_store(doc_id, doc):
        """Thread worker: call LLM, return result for main thread to store."""
        if stop_event.is_set():
            return None
        return _process_one(
            doc_id, doc, client, call_fn, model,
            with_images, http_client, now_str,
        )

    try:
        with ThreadPoolExecutor(max_workers=parallel) as executor:
            futures = {}
            submitted = 0
            done_count = 0

            # Submit all tasks
            for doc_id, doc in to_process:
                if stop_event.is_set():
                    break
                fut = executor.submit(_submit_and_store, doc_id, doc)
                futures[fut] = (doc_id, doc)
                submitted += 1
                # Small stagger to avoid burst
                if delay > 0 and submitted <= parallel:
                    time.sleep(delay / parallel)

            # Collect results as they complete
            for fut in as_completed(futures):
                if stop_event.is_set():
                    break
                doc_id, doc = futures[fut]

                try:
                    result = fut.result()
                except Exception as e:
                    logger.warning(f"Unexpected error for {doc_id}: {e}")
                    errors += 1
                    done_count += 1
                    continue

                if result is None:
                    done_count += 1
                    continue

                ret_id, parsed, err_msg = result
                done_count += 1

                if err_msg:
                    logger.warning(f"{ret_id}: {err_msg}")
                    errors += 1
                elif parsed:
                    # Write to run file (always)
                    run_writer.write(doc_id, parsed)

                    # Write to DocStore (optional, for backward compat)
                    if write_docstore:
                        cur = doc["current"]
                        for key, value in parsed.items():
                            cur[f"llm_{key}"] = value
                        cur["llm_model"] = model
                        cur["llm_enriched_at"] = now_str
                        coll._mark_dirty()
                    processed += 1

                # Progress + periodic flush
                if done_count % 100 == 0:
                    run_writer.flush()
                    if write_docstore:
                        coll.flush()
                    elapsed = time.time() - _start_time
                    rate = done_count / elapsed if elapsed > 0 else 0
                    eta = (len(to_process) - done_count) / rate if rate > 0 else 0
                    logger.info(
                        f"Progress: {done_count}/{len(to_process)} "
                        f"(ok={processed}, err={errors}, "
                        f"{rate:.1f} docs/s, ETA {eta / 60:.0f}m)"
                    )

    except KeyboardInterrupt:
        logger.info("Interrupted -- stopping workers and flushing...")
        stop_event.set()
    finally:
        if write_docstore:
            coll.flush()
        run_writer.flush()
        if http_client:
            http_client.close()

    # Save run metadata
    run_writer.save_metadata({
        "provider": provider,
        "model": model,
        "mode": "with-images" if with_images else "text-only",
        "collection": coll.name,
        "started_at": now_str,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "processed": processed,
        "errors": errors,
        "total_submitted": len(to_process),
        "parallel": parallel,
        "wrote_to_docstore": write_docstore,
    })
    run_writer.close()

    logger.info(
        f"Done. Processed: {processed}, Errors: {errors}, "
        f"Total: {len(to_process)}"
    )
    logger.info(f"Run saved: {run_writer.run_dir}/")


# Timer for ETA calculation
_start_time = time.time()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="LLM feature extraction for property listings")
    parser.add_argument(
        "--provider", default="anthropic", choices=list(PROVIDERS.keys()),
        help="LLM provider (default: anthropic)",
    )
    parser.add_argument(
        "--model", default=None,
        help="Model ID (default: provider's default model)",
    )
    parser.add_argument("--with-images", action="store_true", help="Include property photos")
    parser.add_argument("--max", type=int, default=None, help="Max docs to process")
    parser.add_argument("--all", action="store_true", help="Re-process already enriched docs")
    parser.add_argument("--parallel", type=int, default=1, help="Number of parallel API calls (default: 1)")
    parser.add_argument("--delay", type=float, default=0.1, help="Delay between API calls (seconds)")
    parser.add_argument("--run-name", default=None, help="Custom run ID (auto-generated if not set)")
    parser.add_argument("--no-docstore", action="store_true", help="Don't write results to DocStore (run file only)")
    parser.add_argument("--collection", default="mt_remax", help="Collection name")
    parser.add_argument("--stats", action="store_true", help="Show enrichment runs and coverage stats")
    args = parser.parse_args()

    store = DocStore()
    coll = store.collection(args.collection)

    if args.stats:
        print_stats(coll)
        store.close()
        return

    model = args.model or PROVIDERS[args.provider]["default"]

    # Check SDK is available (only needed for actual processing)
    sdk = PROVIDERS[args.provider]["sdk"]
    try:
        __import__(sdk.replace("-", ".") if "-" in sdk else sdk)
    except ImportError:
        logger.error(f"SDK '{sdk}' not installed. Run: uv add {sdk}")
        sys.exit(1)

    try:
        process_docs(
            coll=coll,
            provider=args.provider,
            model=model,
            with_images=args.with_images,
            max_docs=args.max,
            reprocess=args.all,
            delay=args.delay,
            parallel=args.parallel,
            run_name=args.run_name,
            write_docstore=not args.no_docstore,
        )
    finally:
        store.close()


if __name__ == "__main__":
    main()
