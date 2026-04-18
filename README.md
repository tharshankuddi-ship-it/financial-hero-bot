# YouTube Shorts Autopilot

Generates and posts a YouTube Short twice a day using AI — fully automated via GitHub Actions.

## Pipeline

```
Scripter (g4f/GPT) → Narrator (edge-tts) → Editor (MoviePy) → Uploader (YouTube API)
```

## Setup

### 1. Get YouTube OAuth credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a project → Enable **YouTube Data API v3**
3. Create **OAuth 2.0 credentials** (Desktop app type)
4. Run the one-time auth flow locally to get a refresh token:

```bash
pip install google-auth-oauthlib
python scripts/get_refresh_token.py   # see below
```

### 2. Add GitHub Secrets

In your repo → Settings → Secrets → Actions:

| Secret | Value |
|--------|-------|
| `YT_CLIENT_ID` | From Google Cloud Console |
| `YT_CLIENT_SECRET` | From Google Cloud Console |
| `YT_REFRESH_TOKEN` | From the auth flow above |
| `OPENAI_API_KEY` | Optional — uses free g4f if absent |

### 3. Add a font

Drop any `.ttf` file into `fonts/` and name it `main.ttf`.
Free options: [Google Fonts](https://fonts.google.com/) (Roboto Bold is great).

### 4. Push and watch it run

The workflow fires automatically at **9 AM** and **9 PM UTC** every day.
Trigger it manually via **Actions → Run workflow** anytime.

---

## One-time refresh token script

Save as `scripts/get_refresh_token.py` and run it locally once:

```python
from google_auth_oauthlib.flow import InstalledAppFlow
import json

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
CLIENT_CONFIG = {
    "installed": {
        "client_id": "YOUR_CLIENT_ID",
        "client_secret": "YOUR_CLIENT_SECRET",
        "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob"],
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
    }
}

flow = InstalledAppFlow.from_client_config(CLIENT_CONFIG, SCOPES)
creds = flow.run_local_server(port=0)
print("Refresh token:", creds.refresh_token)
```

## Customising topics

Edit the `TOPIC_ROTATION` list in `main.py` to change what gets posted.
The topic is selected deterministically by day-of-week + AM/PM slot,
so you'll never get the same topic twice in a row.
