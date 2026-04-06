"""
Base scraper utilities: HTTP client, image downloading, document store helpers.
"""

import logging
import os
import time

import httpx

from docstore import DocStore, start_scrape_run, finish_scrape_run  # noqa: F401

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("scraper")

IMAGE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "images")

# BGN to EUR fixed rate
BGN_EUR_RATE = 1 / 1.95583

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}


def get_store() -> DocStore:
    return DocStore()


def get_client(**kwargs):
    hdrs = dict(HEADERS)
    if "headers" in kwargs:
        hdrs.update(kwargs.pop("headers"))
    return httpx.Client(
        headers=hdrs,
        timeout=30.0,
        follow_redirects=True,
        **kwargs,
    )


def download_images(
    client: httpx.Client,
    image_urls: list[str],
    source: str,
    external_id: str,
    max_images: int = 5,
) -> list[str]:
    """Download images to local storage. Returns list of local paths."""
    local_paths = []
    subdir = os.path.join(IMAGE_DIR, source)
    os.makedirs(subdir, exist_ok=True)

    for i, url in enumerate(image_urls[:max_images]):
        try:
            ext = ".jpg"
            if ".png" in url.lower():
                ext = ".png"
            elif ".webp" in url.lower():
                ext = ".webp"

            filename = f"{external_id}_{i}{ext}"
            filepath = os.path.join(subdir, filename)

            if os.path.exists(filepath):
                local_paths.append(filepath)
                continue

            resp = client.get(url)
            if resp.status_code == 200 and len(resp.content) > 1000:
                with open(filepath, "wb") as f:
                    f.write(resp.content)
                local_paths.append(filepath)
                time.sleep(0.3)
        except Exception as e:
            logger.warning(f"Failed to download image {url}: {e}")

    return local_paths
