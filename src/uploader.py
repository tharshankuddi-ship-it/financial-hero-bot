import os
import logging
import google.oauth2.credentials
import google.auth.transport.requests
import googleapiclient.discovery
import googleapiclient.http
import googleapiclient.errors

log = logging.getLogger(__name__)
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
CHUNK_SIZE = 4 * 1024 * 1024

def upload_video(file_path, title, description, tags=None, category_id="27", privacy="public"):
    if tags is None:
        tags = ["Shorts", "Facts", "LearnSomethingNew"]

    creds = google.oauth2.credentials.Credentials(
        token=None,
        refresh_token=os.getenv("YT_REFRESH_TOKEN"),
        client_id=os.getenv("YT_CLIENT_ID"),
        client_secret=os.getenv("YT_CLIENT_SECRET"),
        token_uri="https://oauth2.googleapis.com/token",
        scopes=SCOPES,
    )
    creds.refresh(google.auth.transport.requests.Request())

    youtube = googleapiclient.discovery.build("youtube", "v3", credentials=creds, cache_discovery=False)
    body = {
        "snippet": {"title": title[:100], "description": description[:5000], "tags": tags, "categoryId": category_id},
        "status": {"privacyStatus": privacy, "selfDeclaredMadeForKids": False},
    }
    media = googleapiclient.http.MediaFileUpload(file_path, mimetype="video/mp4", chunksize=CHUNK_SIZE, resumable=True)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    while response is None:
        try:
            status, response = request.next_chunk()
            if status:
                log.info(f"Upload progress: {int(status.progress() * 100)}%")
        except googleapiclient.errors.HttpError as e:
            if e.resp.status in (500, 502, 503, 504):
                continue
            raise

    log.info(f"✅ Uploaded! https://youtu.be/{response['id']}")
    return response["id"]