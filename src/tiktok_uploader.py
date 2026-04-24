"""
src/tiktok_uploader.py — Upload videos to TikTok via Content Posting API
"""
import os
import logging
import requests

log = logging.getLogger(__name__)

TIKTOK_API = "https://open.tiktokapis.com/v2"


def upload_to_tiktok(video_path: str, title: str) -> str:
    """
    Upload a video to TikTok using Content Posting API (Sandbox).
    Returns the TikTok video ID or raises on failure.
    """
    access_token = os.getenv("TIKTOK_ACCESS_TOKEN")
    if not access_token:
        log.warning("TIKTOK_ACCESS_TOKEN not set — skipping TikTok upload")
        return None

    file_size = os.path.getsize(video_path)
    log.info(f"Uploading to TikTok: {title[:50]} ({file_size/1024/1024:.1f}MB)")

    # Step 1 — Initialize upload
    init_resp = requests.post(
        f"{TIKTOK_API}/post/video/init/",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json; charset=UTF-8",
        },
        json={
            "post_info": {
                "title":          title[:150],
                "privacy_level":  "PUBLIC_TO_EVERYONE",
                "disable_duet":   False,
                "disable_comment": False,
                "disable_stitch": False,
                "video_cover_timestamp_ms": 1000,
            },
            "source_info": {
                "source":          "FILE_UPLOAD",
                "video_size":      file_size,
                "chunk_size":      file_size,
                "total_chunk_count": 1,
            },
        },
        timeout=30,
    )

    if init_resp.status_code != 200:
        log.error(f"TikTok init failed: {init_resp.status_code} {init_resp.text}")
        return None

    data        = init_resp.json().get("data", {})
    upload_url  = data.get("upload_url")
    publish_id  = data.get("publish_id")

    if not upload_url:
        log.error(f"No upload_url in TikTok response: {init_resp.json()}")
        return None

    log.info(f"TikTok upload URL received, publish_id={publish_id}")

    # Step 2 — Upload the video file
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

    if upload_resp.status_code not in (200, 201, 206):
        log.error(f"TikTok file upload failed: {upload_resp.status_code} {upload_resp.text}")
        return None

    log.info(f"✅ TikTok upload complete! publish_id={publish_id}")
    return publish_id
