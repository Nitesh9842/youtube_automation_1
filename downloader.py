import requests
import os
import time
import uuid
from urllib.parse import urlparse, urlunparse
from dotenv import load_dotenv
import logging

load_dotenv()

logger = logging.getLogger(__name__)

RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")

# ---------------------------------------------------------------------------
# Multiple API endpoints tried in order.  Each entry is:
#   (host, url_template, response_extractor)
# response_extractor receives the parsed JSON and returns a video URL or None.
# ---------------------------------------------------------------------------
def _extract_v4(data: dict):
    """instagram-stories-videos4 format: {media:[{url:...}]}"""
    media = data.get("media") or data.get("medias") or []
    if isinstance(media, list) and media:
        return media[0].get("url") or media[0].get("video_url")
    return None

def _extract_v2(data: dict):
    """instagram-reels-downloader / social-downloader format: {video:...} or {url:...}"""
    return (data.get("video") or data.get("url") or
            data.get("VideoURL") or data.get("video_url"))

def _extract_savefrom(data: dict):
    """savefrom / general format: {links:[{url:...}]} or {url:...}"""
    links = data.get("links") or data.get("urls") or []
    if isinstance(links, list) and links:
        item = links[0]
        if isinstance(item, dict):
            return item.get("url") or item.get("video")
        if isinstance(item, str):
            return item
    return _extract_v2(data)

ENDPOINTS = [
    # ── primary ────────────────────────────────────────────────────────────
    {
        "name": "instagram-stories-videos4",
        "host": "instagram-downloader-download-instagram-stories-videos4.p.rapidapi.com",
        "url":  "https://instagram-downloader-download-instagram-stories-videos4.p.rapidapi.com/convert",
        "method": "GET",
        "param_key": "url",
        "extractor": _extract_v4,
    },
    # ── fallback 1 ─────────────────────────────────────────────────────────
    {
        "name": "instagram-reels-downloader",
        "host": "instagram-reels-downloader.p.rapidapi.com",
        "url":  "https://instagram-reels-downloader.p.rapidapi.com/download",
        "method": "GET",
        "param_key": "url",
        "extractor": _extract_v2,
    },
    # ── fallback 2 ─────────────────────────────────────────────────────────
    {
        "name": "social-media-video-downloader",
        "host": "social-media-video-downloader.p.rapidapi.com",
        "url":  "https://social-media-video-downloader.p.rapidapi.com/smvd/get/all",
        "method": "GET",
        "param_key": "url",
        "extractor": _extract_savefrom,
    },
]


def _clean_instagram_url(url: str) -> str:
    """
    Strip query-string tracking parameters (igsh, igshid, etc.) that cause
    some API endpoints to return 400/502 errors.
    Keep only the clean canonical path.
    """
    parsed = urlparse(url)
    # Rebuild with no query string and no fragment
    clean = urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))
    # Ensure it ends with a single slash
    if not clean.endswith("/"):
        clean += "/"
    return clean


def _try_endpoint(ep: dict, url: str, retries: int = 2) -> str | None:
    """
    Call one API endpoint.  Returns the CDN video URL on success, None on failure.
    Retries on 429 / 5xx with exponential back-off.
    """
    headers = {
        "x-rapidapi-host": ep["host"],
        "x-rapidapi-key": RAPIDAPI_KEY,
    }
    for attempt in range(retries + 1):
        try:
            if ep["method"] == "GET":
                resp = requests.get(
                    ep["url"],
                    headers=headers,
                    params={ep["param_key"]: url},
                    timeout=30,
                )
            else:
                resp = requests.post(
                    ep["url"],
                    headers=headers,
                    json={ep["param_key"]: url},
                    timeout=30,
                )

            if resp.status_code in (429, 500, 502, 503, 504):
                wait = 2 ** attempt
                logger.warning(f"[{ep['name']}] HTTP {resp.status_code} – retry in {wait}s (attempt {attempt+1})")
                time.sleep(wait)
                continue

            resp.raise_for_status()
            data = resp.json()

            # Surface API-level errors
            if isinstance(data, dict) and (data.get("error") or data.get("errors")):
                logger.warning(f"[{ep['name']}] API error in response: {data.get('error') or data.get('errors')}")
                return None

            video_url = ep["extractor"](data)
            if video_url:
                logger.info(f"[{ep['name']}] ✅ Got video URL")
                return video_url

            logger.warning(f"[{ep['name']}] No video URL found. Keys: {list(data.keys()) if isinstance(data, dict) else type(data)}")
            return None

        except requests.exceptions.RequestException as exc:
            logger.warning(f"[{ep['name']}] Request exception (attempt {attempt+1}): {exc}")
            if attempt < retries:
                time.sleep(2 ** attempt)

    return None


def download_reel_with_audio(reel_url: str, output_folder: str = "downloads") -> str:
    """
    Download an Instagram reel/post using RapidAPI with automatic fallback.

    Args:
        reel_url: Instagram reel URL (tracking params are stripped automatically)
        output_folder: Folder to save the downloaded video

    Returns:
        Absolute path to the downloaded .mp4 file

    Raises:
        Exception: If all endpoints fail
    """
    if not RAPIDAPI_KEY:
        raise Exception("RAPIDAPI_KEY not set in .env")

    clean_url = _clean_instagram_url(reel_url)
    logger.info(f"Downloading: {clean_url}")

    video_cdn_url = None
    for ep in ENDPOINTS:
        logger.info(f"Trying endpoint: {ep['name']}")
        video_cdn_url = _try_endpoint(ep, clean_url)
        if video_cdn_url:
            break

    if not video_cdn_url:
        raise Exception(
            "All download endpoints failed. "
            "Check your RAPIDAPI_KEY and ensure at least one Instagram downloader "
            "subscription is active on RapidAPI."
        )

    # ── Stream the video to disk ───────────────────────────────────────────
    os.makedirs(output_folder, exist_ok=True)
    uid = str(uuid.uuid4())[:8]
    output_file = os.path.join(output_folder, f"reel_{uid}.mp4")

    logger.info(f"Saving video to: {output_file}")
    resp = requests.get(video_cdn_url, stream=True, timeout=120)
    resp.raise_for_status()

    with open(output_file, "wb") as f:
        for chunk in resp.iter_content(chunk_size=1024 * 1024):
            if chunk:
                f.write(chunk)

    size_mb = os.path.getsize(output_file) / 1024 / 1024
    logger.info(f"Downloaded {size_mb:.1f} MB → {output_file}")
    return output_file

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    url = input("Enter Instagram reel URL: ")
    try:
        video_path = download_reel_with_audio(url)
        print(f"✅ Saved to: {video_path}")
    except Exception as e:
        print(f"❌ {e}")
