"""
src/tiktok_uploader.py — Upload videos to TikTok via Content Posting API
Uses inbox/upload (draft) endpoint which works in Sandbox mode.
"""
import os
import logging
import requests

log = logging.getLogger(__name__)
TIKTOK_API = "https://open.tiktokapis.com/v2"


def _get_valid_token() -> str:
    """Return a fresh access token using refresh_token."""
    access_token  = os.getenv("TIKTOK_ACCESS_TOKEN")
    refresh_token = os.getenv("TIKTOK_REFRESH_TOKEN")
    client_key    = os.getenv("TIKTOK_CLIENT_KEY", "sbawgs3smrwhcdgcu8")
    client_secret = os.getenv("TIKTOK_CLIENT_SECRET", "RanP8eBukOuvSVyQrgGJxQL9pTpzvFwv")

    if not access_token:
        return None

    try:
        resp = requests.post(
            f"{TIKTOK_API}/oauth/token/",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={
                "client_key":    client_key,
                "client_secret": client_secret,
                "grant_type":    "refresh_token",
                "refresh_token": refresh_token,
            },
            timeout=15,
        )
        data = resp.json()
        if "access_token" in data:
            log.info("TikTok token refreshed ✅")
            return data["access_token"]
    except Exception as e:
        log.warning(f"Token refresh failed ({e}), using existing token")

    return access_token


def upload_to_tiktok(video_path: str, title: str) -> str:
    access_token = _get_valid_token()
    if not access_token:
        log.warning("TIKTOK_ACCESS_TOKEN not set — skipping TikTok upload")
        return None

    file_size = os.path.getsize(video_path)
    log.info(f"Uploading to TikTok: {title[:50]} ({file_size/1024/1024:.1f}MB)")

    # Step 1 — Initialize upload (inbox/draft endpoint)
    init_resp = requests.post(
        f"{TIKTOK_API}/post/publish/inbox/video/init/",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type":  "application/json; charset=UTF-8",
        },
        json={
            "source_info": {
                "source":            "FILE_UPLOAD",
                "video_size":        file_size,
                "chunk_size":        file_size,
                "total_chunk_count": 1,
            },
        },
        timeout=30,
    )

    log.info(f"TikTok init status: {init_resp.status_code} — {init_resp.text[:300]}")

    if init_resp.status_code != 200:
        log.error(f"TikTok init failed: {init_resp.status_code}")
        return None

    resp_data  = init_resp.json()
    data       = resp_data.get("data", {})
    upload_url = data.get("upload_url")
    publish_id = data.get("publish_id")

    if not upload_url:
        log.error(f"No upload_url: {resp_data}")
        return None

    log.info(f"TikTok upload URL received, publish_id={publish_id}")

    # Step 2 — Upload video file
    with open(video_path, "rb") as f:
        video_data = f.read()

    upload_resp = requests.put(
        upload_url,
        headers={
            "Content-Type":   "video/mp4",
            "Content-Range":  f"bytes 0-{file_size-1}/{file_size}",
            "Content-Length": str(file_size),
        },
        data=video_data,
        timeout=120,
    )

    log.info(f"TikTok upload response: {upload_resp.status_code}")

    if upload_resp.status_code not in (200, 201, 206):
        log.error(f"TikTok upload failed: {upload_resp.status_code} {upload_resp.text[:200]}")
        return None

    log.info(f"✅ TikTok upload complete! Video sent to inbox. publish_id={publish_id}")
    return publish_id
